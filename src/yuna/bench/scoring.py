"""Answer scoring: SQuAD-style normalized token F1 and exact match.

Pure functions, unit-tested. LLM-as-judge comes later as a second scorer;
F1 gives a fast, deterministic first signal for pilots.
"""

from __future__ import annotations

import re
import string

_ARTICLES = re.compile(r"\b(a|an|the)\b")


def normalize_answer(text: str) -> str:
    """Lowercase, strip punctuation/articles, collapse whitespace (SQuAD norm)."""
    text = (text or "").lower()
    text = "".join(c for c in text if c not in string.punctuation)
    text = _ARTICLES.sub(" ", text)
    return " ".join(text.split())


_ABSTAIN = re.compile(
    r"not (?:mentioned|specified|stated|provided|available|in the context)"
    r"|no (?:information|answer|mention)"
    r"|(?:don't|do not|doesn't) know"
    r"|cannot (?:be )?(?:determined|answered)|unanswerable|unknown",
    re.IGNORECASE,
)


def is_abstain(prediction: str) -> bool:
    """True if the model declined to answer — the correct response to an
    unanswerable (adversarial) question."""
    return bool(_ABSTAIN.search(prediction or ""))


def exact_match(prediction: str, gold: str) -> float:
    return float(normalize_answer(prediction) == normalize_answer(gold))


def token_f1(prediction: str, gold: str) -> float:
    """Token-overlap F1 between normalized prediction and gold answer."""
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(gold).split()
    if not pred_tokens or not gold_tokens:
        return float(pred_tokens == gold_tokens)
    common: dict[str, int] = {}
    for t in pred_tokens:
        common[t] = common.get(t, 0) + 1
    overlap = 0
    for t in gold_tokens:
        if common.get(t, 0) > 0:
            overlap += 1
            common[t] -= 1
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred_tokens)
    recall = overlap / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)
