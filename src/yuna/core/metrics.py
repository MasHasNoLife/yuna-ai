"""Per-turn monitoring for Yuna.

One source of truth, three surfaces:
  1. Terminal — a compact one-line summary per turn via the yuna logger
     (plus DEBUG detail with -v), so the server terminal is the ops console.
  2. data/logs/events.jsonl — append-only records for later analysis
     (this doubles as the research paper's instrumentation).
  3. /api/metrics — ring buffer + aggregates for the web UI's System tab.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import asdict, dataclass, field

from yuna.core.config import get_config
from yuna.core.logging import get_logger

log = get_logger("metrics")


@dataclass
class TurnRecord:
    turn: int = 0
    ts: float = field(default_factory=time.time)
    username: str = ""
    source: str = "text"  # text | voice
    user_chars: int = 0

    llm_backend: str = ""
    ttft_ms: float | None = None  # time to first LLM token
    gen_ms: float | None = None  # full generation time
    reply_chars: int = 0
    tokens: int | None = None  # provider-reported, when available
    tok_per_s: float | None = None

    recall_ms: float | None = None
    recalled: int = 0  # facts injected into the prompt
    memory_ops: list[str] = field(default_factory=list)  # "+fact" / "~update" / "-forget"
    extract_ms: float | None = None

    tts_backend: str = ""
    ttfa_ms: float | None = None  # time to first audio chunk
    tts_ms: float | None = None
    audio_bytes: int = 0

    stt_ms: float | None = None
    error: str = ""

    def summary(self) -> str:
        parts = [f"turn#{self.turn}", f"[{self.username or '?'}]", self.llm_backend]
        if self.ttft_ms is not None:
            parts.append(f"ttft={self.ttft_ms / 1000:.2f}s")
        if self.tok_per_s:
            parts.append(f"{self.tok_per_s:.0f}tok/s")
        elif self.gen_ms is not None:
            parts.append(f"gen={self.gen_ms / 1000:.2f}s")
        if self.recalled:
            parts.append(f"recall={self.recalled}")
        if self.memory_ops:
            parts.append(f"mem[{','.join(self.memory_ops)}]")
        if self.tts_backend:
            ttfa = f" ttfa={self.ttfa_ms / 1000:.2f}s" if self.ttfa_ms is not None else ""
            parts.append(f"tts={self.tts_backend}{ttfa}")
        if self.stt_ms is not None:
            parts.append(f"stt={self.stt_ms / 1000:.2f}s")
        if self.error:
            parts.append(f"ERROR={self.error}")
        return "  ".join(parts)


class MetricsHub:
    def __init__(self, history: int = 200):
        self.turns: deque[TurnRecord] = deque(maxlen=history)
        self._counter = 0
        self.started_at = time.time()
        self.totals = {
            "turns": 0,
            "errors": 0,
            "memory_facts": 0,
            "memory_updates": 0,
            "memory_forgets": 0,
            "tts_chars": 0,
            "voice_turns": 0,
        }

    def new_turn(self, username: str = "", source: str = "text") -> TurnRecord:
        self._counter += 1
        return TurnRecord(turn=self._counter, username=username, source=source)

    def finish(self, record: TurnRecord) -> None:
        self.turns.append(record)
        self.totals["turns"] += 1
        if record.error:
            self.totals["errors"] += 1
        if record.source == "voice":
            self.totals["voice_turns"] += 1
        for op in record.memory_ops:
            if op.startswith("+"):
                self.totals["memory_facts"] += 1
            elif op.startswith("~"):
                self.totals["memory_updates"] += 1
            elif op.startswith("-"):
                self.totals["memory_forgets"] += 1
        if record.tts_backend:
            self.totals["tts_chars"] += record.reply_chars

        log.info("%s", record.summary())
        self._append_jsonl(record)

    def count_op(self, op: str) -> None:
        """Account a memory op that completed after its turn was finished
        (background extraction usually outlives the reply)."""
        if op.startswith("+"):
            self.totals["memory_facts"] += 1
        elif op.startswith("~"):
            self.totals["memory_updates"] += 1
        elif op.startswith("-"):
            self.totals["memory_forgets"] += 1

    def log_event(self, kind: str, **data) -> None:
        """Append a non-turn event (memory op, error, session event) to the
        JSONL research log."""
        self._write_jsonl({"kind": kind, "ts": time.time(), **data})

    def _append_jsonl(self, record: TurnRecord) -> None:
        self._write_jsonl({"kind": "turn", **asdict(record)})

    def _write_jsonl(self, payload: dict) -> None:
        try:
            logs = get_config().paths.logs
            logs.mkdir(parents=True, exist_ok=True)
            with open(logs / "events.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(payload) + "\n")
        except OSError as e:
            log.warning("Could not write events.jsonl: %s", e)

    # ── Aggregates for the web UI ───────────────────────────────────────────

    def snapshot(self, last: int = 50) -> dict:
        recent = list(self.turns)[-last:]

        def avg(values: list[float]) -> float | None:
            return round(sum(values) / len(values), 1) if values else None

        return {
            "uptime_s": round(time.time() - self.started_at),
            "totals": dict(self.totals),
            "averages": {
                "ttft_ms": avg([t.ttft_ms for t in recent if t.ttft_ms is not None]),
                "tok_per_s": avg([t.tok_per_s for t in recent if t.tok_per_s]),
                "recall_ms": avg([t.recall_ms for t in recent if t.recall_ms is not None]),
                "ttfa_ms": avg([t.ttfa_ms for t in recent if t.ttfa_ms is not None]),
                "stt_ms": avg([t.stt_ms for t in recent if t.stt_ms is not None]),
            },
            "turns": [asdict(t) for t in recent],
        }


_hub: MetricsHub | None = None


def get_hub() -> MetricsHub:
    global _hub
    if _hub is None:
        _hub = MetricsHub()
    return _hub
