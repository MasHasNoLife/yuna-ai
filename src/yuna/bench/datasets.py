"""Benchmark dataset loaders.

LoCoMo (Maharana et al. 2024): very long multi-session conversations between
two speakers with QA pairs. Get the data file with:

    mkdir -p data/benchmarks
    curl -L -o data/benchmarks/locomo10.json \
        https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json

QA categories: 1 multi-hop, 2 temporal, 3 open-domain, 4 single-hop,
5 adversarial (unanswerable — the model should say it doesn't know).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_SESSION_KEY = re.compile(r"^session_(\d+)$")


@dataclass
class BenchTurn:
    speaker: str
    text: str


@dataclass
class BenchSession:
    index: int
    date: str
    turns: list[BenchTurn] = field(default_factory=list)


@dataclass
class BenchConversation:
    id: str
    speaker_a: str
    speaker_b: str
    sessions: list[BenchSession] = field(default_factory=list)
    qa: list[dict] = field(default_factory=list)

    @property
    def n_turns(self) -> int:
        return sum(len(s.turns) for s in self.sessions)


def _turn_text(raw: dict) -> str:
    """Turn text; image-only turns fall back to their caption."""
    text = (raw.get("text") or raw.get("clean_text") or "").strip()
    caption = (raw.get("blip_caption") or "").strip()
    if caption:
        shared = f"[shares a photo: {caption}]"
        text = f"{text} {shared}".strip() if text else shared
    return text


def load_locomo(path: Path | str) -> list[BenchConversation]:
    """Parse locomo10.json into conversations with ordered sessions."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    conversations: list[BenchConversation] = []
    for i, sample in enumerate(raw):
        conv_data = sample.get("conversation") or {}
        conv = BenchConversation(
            id=str(sample.get("sample_id") or f"conv-{i}"),
            speaker_a=conv_data.get("speaker_a", "SpeakerA"),
            speaker_b=conv_data.get("speaker_b", "SpeakerB"),
        )
        # sessions are top-level keys "session_1", "session_2", ... in conv_data
        indexed = []
        for key, value in conv_data.items():
            m = _SESSION_KEY.match(key)
            if m and isinstance(value, list):
                indexed.append((int(m.group(1)), value))
        for idx, turns in sorted(indexed):
            session = BenchSession(
                index=idx, date=str(conv_data.get(f"session_{idx}_date_time", ""))
            )
            for t in turns:
                text = _turn_text(t)
                if text:
                    session.turns.append(BenchTurn(speaker=t.get("speaker", "?"), text=text))
            if session.turns:
                conv.sessions.append(session)
        for q in sample.get("qa") or []:
            conv.qa.append(
                {
                    "question": str(q.get("question", "")),
                    "answer": str(q.get("answer", "")),
                    "category": q.get("category"),
                    "evidence": q.get("evidence"),
                }
            )
        if conv.sessions:
            conversations.append(conv)
    return conversations
