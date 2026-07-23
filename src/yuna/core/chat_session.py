"""ChatSession — the reusable conversation engine behind the web interface.

Owns history, memory recall, background fact extraction, and streaming
generation through a pluggable LLM backend. Yields typed events the
transport layer (websocket) forwards to the client:

    turn_start / memory_recalled / token / thinking / emotion / reply_done

Out-of-band events (memory ops from background extraction, which usually
finish after the reply) land on `self.events`, an asyncio.Queue drained by
the transport.

Memory model per turn:
  - recall query built from the current + previous user message (pronoun-safe)
  - Yuna's own self-facts (partition "yuna") injected every turn so she has a
    stable autobiography instead of improvising one
  - date/time preamble so she has a sense of when "now" is
  - extraction runs AFTER the reply (so it can mine Yuna's reply for [SELF]
    facts, and never delays time-to-first-token on a shared local model)
  - on disconnect/reset the session is summarized into a "session" memory,
    and the latest summary is injected at the start of the next session
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator
from datetime import datetime

from yuna.core import fact_extractor, llm_backends, safety
from yuna.core.config import get_config
from yuna.core.history import make_history, trim_history
from yuna.core.logging import get_logger
from yuna.core.memory import format_age, get_store
from yuna.core.metrics import TurnRecord, get_hub
from yuna.core.persona import load_persona

log = get_logger("session")

TAG_RE = re.compile(r"\[(.*?)\]")

FORMAT_REMINDER = (
    "\n\n[SYSTEM REMINDER: You are Yuna. The VERY FIRST WORD of your response "
    "MUST be a [tag]. NEVER write asterisks or action narration. Keep it SHORT: "
    "1-2 short sentences, like texting. Don't over-explain and don't stack "
    "multiple questions in one reply. MEMORY HONESTY: only "
    "claim to remember things that appear in your context; otherwise say you "
    "don't remember. If Mas corrects you about what happened, believe him — "
    "never argue about shared history.]"
)

# Leading questions about shared memories ("do you remember us...") make RP
# models invent a past. When one is detected, a grounding note is injected so
# the model checks its actual recalled memories instead of playing along.
REMEMBER_RE = re.compile(
    r"\b(do (?:you|u) remember|remember (?:when|that|how)|did we|didn't we"
    r"|have we (?:ever|been)|that time (?:we|you)|last time (?:we|you))\b",
    re.IGNORECASE,
)
MEMORY_CHECK_NOTE = (
    "(Memory check: only confirm a shared memory if a memory shown this turn "
    "EXPLICITLY describes that event happening. Knowing a related fact is NOT "
    "remembering the event — 'Mas plays osu' does not mean you two ever played "
    "it together. If no memory describes the event, say honestly that you "
    "don't remember it — do NOT invent or embellish a past event.)"
)

MEMORY_PARTITION = "global"  # where chat facts/events/session summaries live

# When the person is NOT Mas, this overrides the little-sister framing so Yuna
# doesn't call a stranger "Onii-chan" or treat them as family. Her identity,
# interests, and safety boundaries are unchanged — only the relationship shifts.
STRANGER_OVERRIDE = (
    "\n\n# CURRENT PERSON — READ THIS, IT OVERRIDES THE FAMILY FRAMING ABOVE\n"
    "You are NOT talking to Mas right now. You're talking to {name}, who is NOT "
    "your brother and NOT family. Do NOT call them Onii-chan, do NOT call them "
    "Mas, do NOT use any sibling/brother lines. {name} is someone you're just "
    "getting to know. Be your normal curious, warm self with a new person — a "
    "bit more reserved than with family. Everything else about you (your "
    "interests, personality, and your hard boundaries) stays exactly the same."
)
RAW_PARTITION = "raw"  # raw dialogue turns for the raw_rag baseline strategy
STRATEGIES = ("none", "full_history", "raw_rag", "agentic")

SUMMARY_PROMPT = (
    "Summarize this conversation between {username} and Yuna in ONE or TWO short "
    "sentences, third person, focusing on what was discussed or decided — the kind "
    "of thing Yuna would naturally remember next time. No preamble, just the summary.\n\n"
    "{transcript}"
)


def build_recall_query(user_input: str, recent_user_inputs: list[str]) -> str:
    """Embedding query from the current + previous user message, so pronoun-heavy
    follow-ups ("no, the project I told you about") still hit the right memories."""
    parts = recent_user_inputs[-1:] + [user_input]
    return " ".join(p.strip() for p in parts if p.strip())[:400]


def time_preamble(now: datetime | None = None) -> str:
    """A tiny sense of time: '(Saturday night, July 19)'. Injected every turn."""
    now = now or datetime.now()
    hour = now.hour
    if hour < 5:
        part = "late night"
    elif hour < 12:
        part = "morning"
    elif hour < 17:
        part = "afternoon"
    elif hour < 21:
        part = "evening"
    else:
        part = "night"
    day = now.strftime("%B %d").lstrip("0").replace(" 0", " ")
    clock = now.strftime("%I:%M %p").lstrip("0").lower()
    return f"({now.strftime('%A')} {part}, {day}, {clock})"


class ChatSession:
    def __init__(
        self,
        username: str = "Mas",
        llm_backend: str | None = None,
        strategy: str | None = None,
        store=None,
        system_prompt: str | None = None,
    ):
        self.username = username
        self.mem_partition = self._partition(username)
        self.strategy = strategy or get_config().memory.strategy
        if self.strategy not in STRATEGIES:
            raise ValueError(f"Unknown memory strategy '{self.strategy}' (have: {STRATEGIES})")
        if system_prompt is None:
            self.persona = load_persona()
            system_prompt = self.persona.system
        self.system_prompt = system_prompt
        self.store = store if store is not None else get_store("main")
        self.backend = llm_backends.get_backend(llm_backend)
        self.extractor_client = None  # lazy — extraction always runs on local Ollama
        self.messages = make_history(self._effective_system())
        self.events: asyncio.Queue[dict] = asyncio.Queue()
        self.background: set[asyncio.Task] = set()
        self.hub = get_hub()
        self.format_reminder = get_config().llm.format_reminder
        self.last_record: TurnRecord | None = None
        self.recent_user_inputs: list[str] = []  # raw, uninjected — for recall queries
        self.exchanges: list[tuple[str, str]] = []  # (user, reply) — for summaries
        self._continuity_loaded = False
        log.info("Session for %s on %s (memory=%s)", username, self.backend.label, self.strategy)

    # ── Controls ────────────────────────────────────────────────────────────

    def set_backend(self, name: str) -> str:
        self.backend = llm_backends.get_backend(name)
        log.info("LLM backend -> %s", self.backend.label)
        return self.backend.label

    @staticmethod
    def _partition(name: str) -> str:
        """Memory partition for a user. 'Mas' keeps the historical 'global' store
        (so existing memories aren't orphaned); everyone else gets their own
        isolated partition, so Yuna never recalls one person's memories to
        another. Yuna's own self-facts (SELF_PARTITION) stay shared across users."""
        n = (name or "").strip().lower()
        return MEMORY_PARTITION if n in ("", "mas") else f"u:{n}"

    def _effective_system(self) -> str:
        """System prompt for the current person: the base persona for Mas, or the
        persona plus a relationship override for anyone else."""
        if self._partition(self.username) == MEMORY_PARTITION:  # Mas
            return self.system_prompt
        return self.system_prompt + STRANGER_OVERRIDE.format(name=self.username)

    def set_user(self, name: str) -> None:
        """Switch the active person: their own memory partition, fresh history,
        and their own last-conversation continuity on the next turn."""
        new = (name or "").strip() or "Mas"
        if new == self.username:
            return
        self.username = new
        self.mem_partition = self._partition(new)
        self.messages = make_history(self._effective_system())
        self.recent_user_inputs = []
        self.exchanges = []
        self._continuity_loaded = False
        log.info("User -> %s (memory partition=%s)", self.username, self.mem_partition)

    def reset(self) -> None:
        self.messages = make_history(self._effective_system())
        self.recent_user_inputs = []
        self.exchanges = []
        self._continuity_loaded = False
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

    # ── Session continuity ──────────────────────────────────────────────────

    async def _load_continuity(self) -> None:
        """Once per session: append the last conversation's summary to the system
        prompt so Yuna starts with narrative memory, not a cold boot."""
        self._continuity_loaded = True
        if self.strategy != "agentic":
            return
        found = await asyncio.to_thread(self.store.latest_summary, self.mem_partition)
        if not found:
            return
        text, ts = found
        age = format_age(ts) or "recently"
        self.messages[0]["content"] += (
            f"\n\n# LAST CONVERSATION\nYour previous conversation with {self.username} "
            f"({age}): {text}"
        )
        log.info("Continuity loaded: last conversation %s", age)

    def _client(self):
        if self.extractor_client is None:
            import ollama

            self.extractor_client = ollama.AsyncClient(host=get_config().endpoints.ollama_url)
        return self.extractor_client

    async def summarize_session(self) -> None:
        """Store a 1-2 sentence summary of this session as a 'session' memory.
        Called by the transport on disconnect/reset. Safe to call repeatedly —
        it no-ops unless there are at least 2 new exchanges."""
        if self.strategy != "agentic" or len(self.exchanges) < 2:
            return
        transcript = "\n".join(f"{self.username}: {u}\nYuna: {r}" for u, r in self.exchanges[-12:])
        try:
            from yuna.core import llm

            summary = await llm.chat(
                self._client(),
                get_config().models.extractor,
                [
                    {
                        "role": "user",
                        "content": SUMMARY_PROMPT.format(
                            username=self.username, transcript=transcript
                        ),
                    }
                ],
            )
            summary = summary.strip().split("\n")[0][:300]
            if summary:
                await asyncio.to_thread(self.store.save, self.mem_partition, summary, "session")
                self.exchanges = []
                self.hub.log_event("session_summary", summary=summary, username=self.username)
                log.info("Session summarized: %s", summary[:80])
        except Exception:
            log.exception("Session summary failed")

    # ── Background memory extraction ────────────────────────────────────────

    def _spawn_extraction(self, user_input: str, recalled: str, reply: str) -> None:
        if not fact_extractor.is_worth_extracting(user_input) and len(reply.split()) < 8:
            return
        cfg = get_config()

        context_lines = []
        for user, rep in self.exchanges[-2:]:
            context_lines.append(f"{self.username}: {user}")
            context_lines.append(f"Yuna: {rep}")

        def on_op(op: fact_extractor.MemoryOp) -> None:
            symbol = {"fact": "+", "event": "+", "self": "+", "update": "~", "forget": "-"}[op.kind]
            self.hub.count_op(symbol)
            self.hub.log_event(
                "memory_op", op=op.kind, fact=op.fact, new_fact=op.new_fact, username=self.username
            )
            self.events.put_nowait(
                {"type": "memory_op", "op": op.kind, "fact": op.fact, "new_fact": op.new_fact}
            )

        task = asyncio.create_task(
            fact_extractor.extract_and_apply(
                self._client(),
                cfg.models.extractor,
                self.username,
                user_input,
                "\n".join(context_lines),
                recalled,
                self.store,
                partition=self.mem_partition,
                on_op=on_op,
                assistant_reply=reply,
                today=datetime.now().strftime("%A, %d %B %Y"),
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

        # Content guard: explicit input never reaches the model or memory.
        # A canned in-character shutdown is returned instead.
        if safety.is_blocked(user_input):
            reply = safety.deflection()
            log.warning("Blocked input; deflected in character")
            self.hub.log_event("blocked_input", username=self.username)
            self.messages.append(
                {"role": "user", "content": f"[{self.username}]: (said something inappropriate)"}
            )
            self.messages.append({"role": "assistant", "content": reply})
            record.reply_chars = len(reply)
            tag = TAG_RE.match(reply)
            if tag:
                yield {"type": "emotion", "tag": tag.group(1).lower()}
            yield {"type": "token", "text": reply}
            yield {"type": "reply_done", "text": reply, "turn": record.turn}
            return

        if not self._continuity_loaded:
            await self._load_continuity()

        # 1. Memory recall (query includes the previous user message for context)
        t0 = time.monotonic()
        query = build_recall_query(user_input, self.recent_user_inputs)
        recalled, self_facts = "", []
        if self.strategy == "agentic":
            recalled, self_facts = await asyncio.gather(
                asyncio.to_thread(self.store.search, self.mem_partition, query),
                # wide pool (whole autobiography), sampled down to 4 per turn
                asyncio.to_thread(self.store.profile, fact_extractor.SELF_PARTITION, 24),
            )
        elif self.strategy == "raw_rag":
            recalled = await asyncio.to_thread(self.store.search, RAW_PARTITION, query)
        record.recall_ms = (time.monotonic() - t0) * 1000
        facts = [f.strip() for f in recalled.split("|") if f.strip()] if recalled else []
        record.recalled = len(facts)
        if facts:
            yield {"type": "memory_recalled", "facts": facts}

        # 2. Build the turn: time sense + self-knowledge + recalled memories
        preamble = [time_preamble()]
        if self_facts:
            # random sample, not always the same set — otherwise she fixates on
            # whatever her few newest self-facts mention, every single turn
            import random

            shown = random.sample(self_facts, min(4, len(self_facts)))
            preamble.append(f"(About yourself, you know: {' '.join(shown)})")
        if facts:
            preamble.append(f"(You remember about {self.username}: {'; '.join(facts)})")
        if REMEMBER_RE.search(user_input):
            preamble.append(MEMORY_CHECK_NOTE)
        full_input = "\n".join(preamble) + f"\n\n[{self.username}]: {user_input}"
        if self.format_reminder:
            full_input += FORMAT_REMINDER

        self.messages.append({"role": "user", "content": full_input})
        # full_history is the context-stuffing baseline: never trim
        if self.strategy != "full_history":
            self.messages = trim_history(self.messages, cfg.sampling.max_history)

        # 3. Stream the reply
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
                num_ctx=cfg.sampling.num_ctx,
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
        self.recent_user_inputs = (self.recent_user_inputs + [user_input])[-3:]
        self.exchanges.append((user_input, response))

        # 4. Memory write AFTER the reply — strategy-dependent:
        #    agentic: model-driven typed extraction (mines both sides)
        #    raw_rag: store the raw exchange verbatim, no model call
        if self.strategy == "agentic":
            # include self-facts in the extractor's known set, or it re-extracts them
            known = " | ".join(p for p in (recalled, *self_facts) if p)
            self._spawn_extraction(user_input, known, response)
        elif self.strategy == "raw_rag":
            raw_doc = f"{self.username}: {user_input} / Yuna: {response}"
            task = asyncio.create_task(
                asyncio.to_thread(self.store.save, RAW_PARTITION, raw_doc, "raw")
            )
            self.background.add(task)
            task.add_done_callback(self.background.discard)

        yield {"type": "reply_done", "text": response, "turn": record.turn}
