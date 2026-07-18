"""LLM-based long-term memory extraction, shared by realtime chat and Discord.

A background model call turns a user message into structured memory operations:
[FACT] new fact / [UPDATE] old -> new / [FORGET] fact. Parsing is pure
(`parse_operations`) so it's unit-testable without any model.
"""

from __future__ import annotations

from dataclasses import dataclass

from yuna.core.logging import get_logger

log = get_logger("fact_extractor")

PROMPT_TEMPLATE = """You are a STRICT memory extractor. Your ONLY job is to extract permanent, long-term facts.
CRITICAL RULES:
1. You must ONLY extract BRAND NEW facts explicitly stated in the "New Message to Extract".
2. DO NOT extract facts that are ONLY found in the "Known Database Facts" or "Recent Chat Context" blocks.
3. If the new message does not contain a new fact, or is just a question/action, reply NONE.
4. NEVER extract conversational intents (e.g., "User is asking...", "User is searching...").
5. If there is ANY fact about a person or the world, prefix it with [FACT].
6. PRONOUN RESOLUTION:
   - "I", "me", "my", "mine" ALWAYS refers to {username} (the user speaking).
   - "You", "your", "yours" ALWAYS refers to YUNA (the AI receiving the message).
   - "He", "she", "they" refers to third parties mentioned in the Recent Chat Context.
7. ONLY use [FORGET] if the user EXPLICITLY commands you to forget something (e.g. "forget that"). Do NOT use it to correct facts.
8. IF the user organically corrects a past fact (found in Known Database Facts), use [UPDATE] followed by the old fact, a " -> ", and the new fact. Example: [UPDATE] Mas likes red -> Mas likes blue.

Example 1:
Message: "my favorite color is neon green"
Response: [FACT] {username} loves the color neon green.

Example 2:
Message: "actually my favorite color isn't neon green, it's red"
Response: [UPDATE] {username} loves the color neon green -> {username} loves the color red.

Example 3:
Message: "your nickname is tuna"
Response: [FACT] Yuna's nickname is tuna.

Known Database Facts:
{recalled_facts}

Recent Chat Context:
{recent_context}

New Message to Extract: "{user_input}"
Response:"""


@dataclass
class MemoryOp:
    kind: str  # "fact" | "update" | "forget"
    fact: str
    new_fact: str | None = None  # only for "update"


def build_prompt(username: str, user_input: str, recent_context: str, recalled_facts: str) -> str:
    return PROMPT_TEMPLATE.format(
        username=username,
        user_input=user_input,
        recent_context=recent_context or "None",
        recalled_facts=recalled_facts or "None",
    )


def parse_operations(response: str) -> list[MemoryOp]:
    """Parse the extractor model's reply into memory operations. Pure function."""
    content = (response or "").strip()
    if not content or "NONE" in content or len(content) <= 5:
        return []

    ops: list[MemoryOp] = []
    for line in content.split("\n"):
        clean = line.strip(" -*•")
        if clean.startswith("[FACT]"):
            fact = clean.removeprefix("[FACT]").strip()
            if fact:
                ops.append(MemoryOp("fact", fact))
        elif clean.startswith("[UPDATE]"):
            parts = clean.removeprefix("[UPDATE]").split("->")
            if len(parts) == 2:
                old, new = parts[0].strip(), parts[1].strip()
                if old and new:
                    ops.append(MemoryOp("update", old, new))
        elif clean.startswith("[FORGET]"):
            fact = clean.removeprefix("[FORGET]").strip()
            if fact:
                ops.append(MemoryOp("forget", fact))
    return ops


def is_worth_extracting(user_input: str) -> bool:
    """Skip the background model call for short messages that can't hold facts."""
    return len(user_input.split()) >= 4


async def extract_and_apply(
    client,
    model: str,
    username: str,
    user_input: str,
    recent_context: str,
    recalled_facts: str,
    store,
    partition: str,
    allow_forget: bool = True,
    on_op=None,
) -> list[MemoryOp]:
    """Run the extractor model and apply the resulting ops to `store`
    (a yuna.core.memory.MemoryStore) under `partition`.

    Designed to run as a background task; errors are logged, never raised.
    `on_op(op)` is called after each applied operation (live UI feeds).
    """
    import asyncio

    from yuna.core import llm

    try:
        prompt = build_prompt(username, user_input, recent_context, recalled_facts)
        response = await llm.chat(client, model, [{"role": "user", "content": prompt}])
        ops = parse_operations(response)
        applied: list[MemoryOp] = []
        for op in ops:
            if op.kind == "fact":
                log.info("[memory] + %s", op.fact)
                await asyncio.to_thread(store.save, partition, op.fact)
            elif op.kind == "update":
                log.info("[memory] %s -> %s", op.fact, op.new_fact)
                await asyncio.to_thread(store.delete, partition, op.fact)
                await asyncio.to_thread(store.save, partition, op.new_fact)
            elif op.kind == "forget":
                if not allow_forget:
                    log.warning("[memory] forget rejected for partition %s", partition)
                    continue
                log.info("[memory] - %s", op.fact)
                await asyncio.to_thread(store.delete, partition, op.fact)
            applied.append(op)
            if on_op is not None:
                try:
                    on_op(op)
                except Exception:
                    log.exception("on_op callback failed")
        return applied
    except Exception:
        log.exception("Memory extraction failed")
        return []
