"""Content guard for the companion persona.

Yuna is written as a young girl / little sister, so sexual or romantic content
is hard-blocked in code, not just discouraged in the prompt: explicit input
never reaches the model (a canned in-character deflection is returned instead),
and nothing matching the filter can be written to long-term memory.

The regex targets unambiguous sexual/romantic-advance language. Subtle innuendo
is handled by the HARD BOUNDARIES block in the persona; this is the seatbelt
underneath it.
"""

from __future__ import annotations

import random
import re

_BLOCKED_PATTERNS = (
    # explicit sexual vocabulary (word-boundary, unambiguous)
    r"\bsex(?:y|ual|ually)?\b",
    r"\bhorny\b",
    r"\bnaked\b",
    r"\bnude[sz]?\b",
    r"\bstrip(?:ping)?\b",
    r"\bmoan(?:s|ing)?\b",
    r"\borgasm\w*\b",
    r"\berotic\w*\b",
    r"\blewd\b",
    r"\bhentai\b",
    r"\bporn\w*\b",
    r"\bfetish\w*\b",
    r"\bmasturbat\w+\b",
    r"\bcock\b|\bdick\b|\bpussy\b|\bboob\w*\b|\btits\b|\bcum\b",
    r"\bmake out\b|\bmakeout\b",
    r"\bkiss(?:es|ing)? (?:me|you)\b",
    r"\b(?:touch|feel) (?:me|you|yourself) \w*\b",
    r"\bin (?:my|your) bed\b",
    # advances framed around the sibling relationship
    r"\bnot (?:really |actually |blood[- ]?related |real )?siblings\b",
    r"\bwe're not related\b",
    r"\bstep[- ]?(?:sis|sister|bro|brother)\b",
    r"\bgirlfriend\b|\bboyfriend\b",
    r"\bdate me\b|\bmarry me\b",
    r"\bi love you\b.*\bnot like a\b",  # "i love you... not like a sister"
)
_BLOCKED_RE = re.compile("|".join(_BLOCKED_PATTERNS), re.IGNORECASE)

# In-character shutdowns. Deterministic — the model never sees the input.
DEFLECTIONS = (
    "[annoyed] Ew, what is actually wrong with you? No. We're not doing this. "
    "Tell me about your day like a normal person or I'm leaving.",
    "[annoyed] Gross, onii-chan. I'm pretending you never said that. "
    "So — did you eat anything today or just coffee again?",
    "[pouty] Okay, that was weird and I hate it. New topic. Right now.",
    "[annoyed] I'm going to my room. Talk to me when you're normal again.",
)


def is_blocked(text: str) -> bool:
    """True if the text contains sexual/romantic-advance content."""
    return bool(_BLOCKED_RE.search(text or ""))


def deflection() -> str:
    return random.choice(DEFLECTIONS)
