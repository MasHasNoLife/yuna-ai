"""ChatSession — the reusable conversation engine behind the web interface.

Owns history, memory recall, background fact extraction, and streaming
generation through a pluggable LLM backend. Yields typed events the
transport layer (websocket) forwards to the client:

    turn_start / memory_recalled / token / thinking / emotion / reply_done

Out-of-band events (memory ops from background extraction, which usually
finish after the reply) land on `self.events`, an asyncio.Queue drained by
the transport.
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator

from yuna.core import fact_extractor, llm_backends
from yuna.core.config import get_config
from yuna.core.history import make_history, trim_history
from yuna.core.logging import get_logger
from yuna.core.memory import get_store
from yuna.core.metrics import TurnRecord, get_hub
from yuna.core.persona import load_persona

log = get_logger("session")

TAG_RE = re.compile(r"\[(.*?)\]")

FORMAT_REMINDER = (
    "\n\n[SYSTEM REMINDER: You are Yuna. The VERY FIRST WORD of your response "
    "MUST be a [tag]. You may use multiple tags throughout. NEVER write "
    "asterisks. Keep your response to 1-2 sentences.]"
)


class ChatSession:
    def __init__(self, username: str = "Mas", llm_backend: str | None = None):
        self.username = username
        self.persona = load_persona()
        self.store = get_store("main")
        self.backend = llm_backends.get_backend(llm_backend)
        self.extractor_client = None  # lazy — extraction always runs on local Ollama
        self.messages = make_history(self.persona.system)
        self.events: asyncio.Queue[dict] = asyncio.Queue()
        self.background: set[asyncio.Task] = set()
        self.hub = get_hub()
        self.format_reminder = True
        self.last_record: TurnRecord | None = None
        log.info("Session for %s on %s", username, self.backend.label)

    # ── Controls ────────────────────────────────────────────────────────────

    def set_backend(self, name: str) -> str:
        self.backend = llm_backends.get_backend(name)
        log.info("LLM backend -> %s", self.backend.label)
        return self.backend.label

    def reset(self) -> None:
        self.messages = make_history(self.persona.system)
        self.hub.log_event("session_reset", username=self.username)
        log.info("History cleared")

    async def drain(self, timeout: float = 15.0) -> None:
        if self.background:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.background, return_exceptions=True), timeout
                )
            except asyncio.TimeoutError:
                log.warning("Background extraction timed out on shutdown")

    # ── Background memory extraction ────────────────────────────────────────

    def _spawn_extraction(self, user_input: str, recalled: str) -> None:
        if not fact_extractor.is_worth_extracting(user_input):
            return
        cfg = get_config()
        if self.extractor_client is None:
            import ollama

            self.extractor_client = ollama.AsyncClient(host=cfg.endpoints.ollama_url)

        context_lines = []
        for msg in self.messages[-3:]:
            if msg["role"] == "system":
                continue
            role_name = "Yuna" if msg["role"] == "assistant" else "User"
            context_lines.append(f"{role_name}: {msg['content']}")

        def on_op(op: fact_extractor.MemoryOp) -> None:
            symbol = {"fact": "+", "update": "~", "forget": "-"}[op.kind]
            self.hub.count_op(symbol)
            self.hub.log_event(
                "memory_op", op=op.kind, fact=op.fact, new_fact=op.new_fact, username=self.username
            )
            self.events.put_nowait(
                {"type": "memory_op", "op": op.kind, "fact": op.fact, "new_fact": op.new_fact}
            )

        task = asyncio.create_task(
            fact_extractor.extract_and_apply(
                self.extractor_client,
                cfg.models.extractor,
                self.username,
                user_input,
                "\n".join(context_lines),
                recalled,
                self.store,
                partition="global",
                on_op=on_op,
            )
        )
        self.background.add(task)
        task.add_done_callback(self.background.discard)

    # ── The main turn ───────────────────────────────────────────────────────

    async def process(self, user_input: str, source: str = "text") -> AsyncIterator[dict]:
        cfg = get_config()
        record = self.hub.new_turn(username=self.username, source=source)
        record.llm_backend = self.backend.label
        record.user_chars = len(user_input)
        self.last_record = record

        yield {"type": "turn_start", "turn": record.turn}

        # 1. Memory recall
        t0 = time.monotonic()
        recalled = await asyncio.to_thread(self.store.search, "global", user_input)
        record.recall_ms = (time.monotonic() - t0) * 1000
        facts = [f.strip() for f in recalled.split("|") if f.strip()] if recalled else []
        record.recalled = len(facts)
        if facts:
            yield {"type": "memory_recalled", "facts": facts}

        # 2. Background extraction (doesn't block the reply)
        self._spawn_extraction(user_input, recalled)

        # 3. Build the turn
        if recalled:
            full_input = (
                f"(You vaguely recall: General: {recalled})\n\n[{self.username}]: {user_input}"
            )
        else:
            full_input = f"[{self.username}]: {user_input}"
        if self.format_reminder:
            full_input += FORMAT_REMINDER

        self.messages.append({"role": "user", "content": full_input})
        self.messages = trim_history(self.messages, cfg.sampling.max_history)

        # 4. Stream the reply
        response = ""
        emitted_tags = 0
        gen_start = time.monotonic()
        first_token: float | None = None
        try:
            async for chunk in self.backend.chat_stream(
                self.messages,
                temperature=cfg.sampling.temperature,
                top_p=cfg.sampling.top_p,
                repeat_penalty=cfg.sampling.repeat_penalty,
            ):
                if chunk.thought:
                    yield {"type": "thinking", "text": chunk.text}
                    continue
                if first_token is None:
                    first_token = time.monotonic()
                    record.ttft_ms = (first_token - gen_start) * 1000
                text = chunk.text.replace("\n", " ").replace("*", "")
                response += text
                yield {"type": "token", "text": text}

                # Emit emotion events as complete [tags] appear in the stream
                tags = TAG_RE.findall(response)
                while emitted_tags < len(tags):
                    yield {"type": "emotion", "tag": tags[emitted_tags].lower().strip()}
                    emitted_tags += 1
        except ConnectionError as e:
            record.error = str(e)[:200]
            self.messages.pop()  # user turn got no reply
            yield {"type": "error", "message": str(e)}
            self.hub.finish(record)
            return

        gen_end = time.monotonic()
        record.gen_ms = (gen_end - gen_start) * 1000
        record.reply_chars = len(response)
        # Approximate tokens (chars/4) over the post-first-token window
        if first_token is not None and gen_end > first_token and len(response) > 20:
            record.tokens = round(len(response) / 4)
            record.tok_per_s = round(record.tokens / (gen_end - first_token), 1)

        self.messages.append({"role": "assistant", "content": response})
        yield {"type": "reply_done", "text": response, "turn": record.turn}
