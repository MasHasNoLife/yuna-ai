"""LLM-based long-term memory extraction, shared by realtime chat and Discord.

A background model call turns a user message into structured memory operations:
[FACT] new fact / [UPDATE] old -> new / [FORGET] fact. Parsing is pure
(`parse_operations`) so it's unit-testable without any model.
"""

from __future__ import annotations

from dataclasses import dataclass

from yuna.core.logging import get_logger

log = get_logger("fact_extractor")

PROMPT_TEMPLATE = """You are a STRICT memory curator for a long-term companion. Extract ONLY information worth remembering weeks from now.

OPERATION TYPES:
[FACT] durable truth about {username} or the world ("{username}'s favorite dish is carbonara")
[EVENT] something that happened, tied to now ("{username} started learning to cook pasta")
[SELF] durable detail Yuna revealed about herself in her reply ("Yuna has been into lo-fi music lately")
[UPDATE] old fact -> corrected fact (only when a Known Database Fact is organically corrected)
[FORGET] fact to delete (see rules 6-7)

CRITICAL RULES:
1. Extract ONLY from the "New Exchange". Never re-extract Known Database Facts or Recent Chat Context.
2. If there is nothing genuinely worth remembering, reply NONE. Most small-talk exchanges are NONE.
3. NEVER store conversation states or meta-talk. FORBIDDEN examples (all must be NONE):
   - "{username} is asking about X" / "is unsure what Yuna means" / "believes Yuna said something"
   - "{username} is doing well" / "is in a good mood" (moods are not memories)
   - anything describing the conversation itself rather than the people
4. DENIALS ARE NOT FACTS. If {username} denies something ("there is no such project", "I never said that",
   "that didn't happen"):
   - If a Known Database Fact matches the denied thing -> [FORGET] that fact.
   - Otherwise -> NONE. NEVER store the denial itself ("There is no robot project" is FORBIDDEN).
5. PRONOUNS: "I/me/my" = {username}. "you/your" = Yuna. Third parties by name from context.
6. [FORGET] only when rule 4 applies or {username} explicitly says to forget.
7. Corrections use [UPDATE] old -> new, not FORGET+FACT.
8. [SELF] only for concrete, durable details Yuna stated about her own life/tastes — not feelings of the moment.

Example 1:
{username}: "my favorite color is neon green" / Yuna: "ooh bold choice!"
Response: [FACT] {username} loves the color neon green.

Example 2:
{username}: "actually it's red now" (DB has: {username} loves neon green)
Response: [UPDATE] {username} loves the color neon green -> {username} loves the color red.

Example 3:
{username}: "there is no such project like that" (DB has: {username} is building a robot game)
Response: [FORGET] {username} is building a robot game.

Example 4:
{username}: "there is no robot project, what are you on about" (DB has nothing about it)
Response: NONE

Example 5:
{username}: "what are you up to?" / Yuna: "Just sketching — I've gotten really into charcoal drawing this month."
Response: [SELF] Yuna has gotten into charcoal drawing recently.

Known Database Facts:
{recalled_facts}

Recent Chat Context:
{recent_context}

New Exchange:
{username}: "{user_input}"
Yuna: "{assistant_reply}"
Response:"""

# Backstop patterns for junk the model still lets through: denials stored as
# facts, and conversation-state meta observations. Pure + unit-tested.
_JUNK_PATTERNS = (
    r"\bthere (?:is|are|was|were) no\b",
    r"\b(?:does not|doesn't|did not|didn't) exist\b",
    r"\bnever happened\b",
    r"\bis (?:unsure|uncertain|confused|unclear)\b",
    r"\bis referring to\b",
    r"\basked (?:yuna|about)\b",
    r"\bis asking\b",
    r"\bbelieves? yuna\b",
    r"\bmay have summoned\b",
    r"\bis (?:doing well|in a good mood|in a bad mood)\b",
    r"\bwants? to know\b",
    r"\bis (?:curious|wondering) (?:about|what|if)\b",
    r"\bis open to discussing\b",
)
_JUNK_RE = None  # compiled lazily


def is_junk_fact(fact: str) -> bool:
    """True if the fact is conversational noise that must never be stored."""
    global _JUNK_RE
    if _JUNK_RE is None:
        import re

        _JUNK_RE = re.compile("|".join(_JUNK_PATTERNS), re.IGNORECASE)
    return bool(_JUNK_RE.search(fact))


@dataclass
class MemoryOp:
    kind: str  # "fact" | "event" | "self" | "update" | "forget"
    fact: str
    new_fact: str | None = None  # only for "update"


def build_prompt(
    username: str,
    user_input: str,
    recent_context: str,
    recalled_facts: str,
    assistant_reply: str = "",
) -> str:
    return PROMPT_TEMPLATE.format(
        username=username,
        user_input=user_input,
        assistant_reply=assistant_reply or "(no reply yet)",
        recent_context=recent_context or "None",
        recalled_facts=recalled_facts or "None",
    )


_TAG_KINDS = {"[FACT]": "fact", "[EVENT]": "event", "[SELF]": "self", "[FORGET]": "forget"}


def parse_operations(response: str) -> list[MemoryOp]:
    """Parse the extractor model's reply into memory operations. Pure function.

    Junk (denials, conversation meta-states) is filtered here so no caller can
    accidentally store it.
    """
    content = (response or "").strip()
    if not content or "NONE" in content or len(content) <= 5:
        return []

    ops: list[MemoryOp] = []
    for line in content.split("\n"):
        clean = line.strip(" -*•")
        if clean.startswith("[UPDATE]"):
            parts = clean.removeprefix("[UPDATE]").split("->")
            if len(parts) == 2:
                old, new = parts[0].strip(), parts[1].strip()
                if old and new and not is_junk_fact(new):
                    ops.append(MemoryOp("update", old, new))
            continue
        for tag, kind in _TAG_KINDS.items():
            if clean.startswith(tag):
                fact = clean.removeprefix(tag).strip()
                # FORGET targets existing facts, so the junk filter must not block it
                if fact and (kind == "forget" or not is_junk_fact(fact)):
                    ops.append(MemoryOp(kind, fact))
                break
    return ops


def is_worth_extracting(user_input: str) -> bool:
    """Skip the background model call for short messages that can't hold facts."""
    return len(user_input.split()) >= 4


SELF_PARTITION = "yuna"  # Yuna's own autobiography lives in its own partition


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
    assistant_reply: str = "",
) -> list[MemoryOp]:
    """Run the extractor model and apply the resulting ops to `store`
    (a yuna.core.memory.MemoryStore) under `partition`.

    Designed to run as a background task; errors are logged, never raised.
    `on_op(op)` is called after each applied operation (live UI feeds).
    """
    import asyncio

    from yuna.core import llm

    try:
        prompt = build_prompt(username, user_input, recent_context, recalled_facts, assistant_reply)
        response = await llm.chat(client, model, [{"role": "user", "content": prompt}])
        ops = parse_operations(response)
        applied: list[MemoryOp] = []
        for op in ops:
            if op.kind in ("fact", "event"):
                log.info("[memory] + (%s) %s", op.kind, op.fact)
                await asyncio.to_thread(store.save, partition, op.fact, op.kind)
            elif op.kind == "self":
                log.info("[memory] + (self) %s", op.fact)
                await asyncio.to_thread(store.save, SELF_PARTITION, op.fact, "fact")
            elif op.kind == "update":
                log.info("[memory] %s -> %s", op.fact, op.new_fact)
                await asyncio.to_thread(store.delete, partition, op.fact)
                await asyncio.to_thread(store.save, partition, op.new_fact, "fact")
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
