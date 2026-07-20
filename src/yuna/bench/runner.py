"""Benchmark runner: ingest a conversation under a memory strategy, then
answer its QA set from that memory and score it.

The system under test is the same code the live app uses
(yuna.core.memory.MemoryStore + yuna.core.fact_extractor); the runner just
drives it headlessly:

    ingest   none/full_history: no memory writes (transcript kept in RAM)
             raw_rag:  every turn saved verbatim to the vector store
             agentic:  typed FACT/EVENT/SELF extraction per exchange (ours)
    qa       context assembled per strategy -> model answers -> token F1 / EM

Each (conversation, strategy) gets a fresh ChromaDB under the run directory,
so runs are isolated and reproducible. Results stream to a JSONL file.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

from yuna.bench.datasets import BenchConversation, load_locomo, parse_session_date
from yuna.bench.scoring import exact_match, is_abstain, token_f1
from yuna.core import fact_extractor, llm
from yuna.core.config import get_config
from yuna.core.logging import get_logger
from yuna.core.memory import MemoryStore

log = get_logger("bench")

FACT_PARTITION = "global"
RAW_PARTITION = "raw"

QA_PROMPT = (
    "You are answering questions about past conversations between {a} and {b}.\n"
    "Use ONLY the context below. If the context does not contain the answer, "
    'say "Not mentioned".\n\n'
    "Context:\n{context}\n\n"
    "Question: {question}\n"
    "Answer with just the answer, as short as possible:"
)

FULL_HISTORY_CHAR_CAP = 60_000  # ~15k tokens; needs a large num_ctx


@dataclass
class RunConfig:
    dataset: Path
    strategy: str  # none | full_history | raw_rag | agentic
    model: str  # extractor model (ingest); also answers QA unless qa_model set
    out_dir: Path
    conversations: int = 1  # 0 = all
    sessions: int = 0  # per conversation, 0 = all
    qa: int = 0  # per conversation, 0 = all
    qa_model: str = ""  # QA answerer; empty = same as model. The extractor
    # ladder (RQ1) varies `model` while holding qa_model fixed, so differences
    # are attributable to extraction quality, not the responder.


_DIA_ID = re.compile(r"D(\d+):")


def qa_within_sessions(qa: dict, max_session: int) -> bool:
    """True if all the QA's evidence turns fall within the ingested sessions.
    Questions without evidence (adversarial category) are always kept."""
    evidence = qa.get("evidence") or []
    if not evidence:
        return True
    nums = []
    for e in evidence:
        m = _DIA_ID.match(str(e))
        if m:
            nums.append(int(m.group(1)))
    return bool(nums) and max(nums) <= max_session


def _pair_exchanges(session, speaker_a: str) -> list[tuple[str, str]]:
    """Group a session's turns into (speaker_a_text, speaker_b_text) exchanges.
    Consecutive same-speaker turns are joined."""
    exchanges: list[tuple[str, str]] = []
    a_buf: list[str] = []
    b_buf: list[str] = []
    for turn in session.turns:
        if turn.speaker == speaker_a:
            if b_buf:  # previous exchange complete
                exchanges.append((" ".join(a_buf), " ".join(b_buf)))
                a_buf, b_buf = [], []
            a_buf.append(turn.text)
        else:
            b_buf.append(turn.text)
    if a_buf or b_buf:
        exchanges.append((" ".join(a_buf), " ".join(b_buf)))
    return exchanges


class BenchRun:
    def __init__(self, cfg: RunConfig):
        self.cfg = cfg
        self.run_dir = cfg.out_dir / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{cfg.strategy}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.results_path = self.run_dir / "results.jsonl"
        self._client = None

    def client(self):
        if self._client is None:
            import ollama

            self._client = ollama.AsyncClient(host=get_config().endpoints.ollama_url)
        return self._client

    # ── Ingest ──────────────────────────────────────────────────────────────

    async def ingest(self, conv: BenchConversation, store: MemoryStore) -> dict:
        """Feed the conversation into memory per strategy. Returns ingest stats."""
        import asyncio

        t0 = time.monotonic()
        sessions = conv.sessions[: self.cfg.sessions or None]
        n_exchanges = 0
        transcript: list[str] = []

        for session in sessions:
            header = f"[Session {session.index} — {session.date}]"
            transcript.append(header)
            for turn in session.turns:
                transcript.append(f"{turn.speaker}: {turn.text}")

            if self.cfg.strategy == "raw_rag":
                for turn in session.turns:
                    await asyncio.to_thread(
                        store.save,
                        RAW_PARTITION,
                        f"({session.date}) {turn.speaker}: {turn.text}",
                        "raw",
                    )
            elif self.cfg.strategy == "agentic":
                prev_exchange = ""
                session_ts = parse_session_date(session.date)
                for a_text, b_text in _pair_exchanges(session, conv.speaker_a):
                    recalled = await asyncio.to_thread(
                        store.search, FACT_PARTITION, f"{a_text} {b_text}"[:400]
                    )
                    await fact_extractor.extract_and_apply(
                        self.client(),
                        self.cfg.model,
                        conv.speaker_a,
                        a_text,
                        f"Session date: {session.date}\n{prev_exchange}",
                        recalled,
                        store,
                        partition=FACT_PARTITION,
                        assistant_reply=b_text,
                        assistant_name=conv.speaker_b,
                        today=session.date,
                        event_ts=session_ts,
                    )
                    prev_exchange = f"{conv.speaker_a}: {a_text}\n{conv.speaker_b}: {b_text}"
                    n_exchanges += 1
            log.info(
                "[%s/%s] ingested session %d (%d turns)",
                conv.id,
                self.cfg.strategy,
                session.index,
                len(session.turns),
            )

        self.transcript = "\n".join(transcript)
        self.max_session = max((s.index for s in sessions), default=0)
        return {
            "ingest_s": round(time.monotonic() - t0, 1),
            "sessions": len(sessions),
            "exchanges": n_exchanges,
            "memories": len(store.all()) if self.cfg.strategy in ("raw_rag", "agentic") else 0,
        }

    # ── QA ──────────────────────────────────────────────────────────────────

    async def _qa_context(self, conv: BenchConversation, store: MemoryStore, question: str) -> str:
        import asyncio

        if self.cfg.strategy == "none":
            return "(no memory available)"
        if self.cfg.strategy == "full_history":
            return self.transcript[-FULL_HISTORY_CHAR_CAP:]
        if self.cfg.strategy == "raw_rag":
            return await asyncio.to_thread(store.search, RAW_PARTITION, question, 8)
        # agentic: extracted facts + the other speaker's self-facts
        facts, self_facts = await asyncio.gather(
            asyncio.to_thread(store.search, FACT_PARTITION, question, 8),
            asyncio.to_thread(store.search, conv.speaker_b.lower(), question, 4),
        )
        return " | ".join(p for p in (facts, self_facts) if p)

    async def answer_qa(self, conv: BenchConversation, store: MemoryStore) -> list[dict]:
        records = []
        qa_set = conv.qa
        # When ingestion is limited to N sessions, only ask questions whose
        # evidence lies within those sessions (adversarial ones always kept).
        if self.cfg.sessions:
            qa_set = [q for q in qa_set if qa_within_sessions(q, self.max_session)]
        qa_set = qa_set[: self.cfg.qa or None]
        options = {"temperature": 0.1}
        if self.cfg.strategy == "full_history":
            options["num_ctx"] = 16384
        with self.results_path.open("a", encoding="utf-8") as out:
            for i, qa in enumerate(qa_set):
                context = await self._qa_context(conv, store, qa["question"])
                prompt = QA_PROMPT.format(
                    a=conv.speaker_a,
                    b=conv.speaker_b,
                    context=context or "(nothing recalled)",
                    question=qa["question"],
                )
                t0 = time.monotonic()
                pred = await llm.chat(
                    self.client(),
                    self.cfg.qa_model or self.cfg.model,
                    [{"role": "user", "content": prompt}],
                    **options,
                )
                pred = pred.strip().split("\n")[0]
                # Adversarial (cat 5) questions are unanswerable: correct means
                # abstaining. Token overlap with varied gold phrasings is
                # meaningless there, so score abstention instead.
                if qa["category"] == 5:
                    f1 = em = float(is_abstain(pred))
                else:
                    f1, em = round(token_f1(pred, qa["answer"]), 3), exact_match(pred, qa["answer"])
                rec = {
                    "conv": conv.id,
                    "strategy": self.cfg.strategy,
                    "model": self.cfg.model,
                    "qa_model": self.cfg.qa_model or self.cfg.model,
                    "category": qa["category"],
                    "question": qa["question"],
                    "gold": qa["answer"],
                    "pred": pred,
                    "f1": f1,
                    "em": em,
                    "context_chars": len(context),
                    "qa_s": round(time.monotonic() - t0, 1),
                }
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                records.append(rec)
                log.info(
                    "[%s/%s] QA %d/%d f1=%.2f  %s",
                    conv.id,
                    self.cfg.strategy,
                    i + 1,
                    len(qa_set),
                    rec["f1"],
                    qa["question"][:60],
                )
        return records


async def run(cfg: RunConfig) -> dict:
    """Run the benchmark; returns (and writes) a summary dict."""
    conversations = load_locomo(cfg.dataset)
    if cfg.conversations:
        conversations = conversations[: cfg.conversations]
    bench = BenchRun(cfg)
    log.info(
        "Bench start: strategy=%s model=%s convs=%d -> %s",
        cfg.strategy,
        cfg.model,
        len(conversations),
        bench.run_dir,
    )

    all_records: list[dict] = []
    ingest_stats: list[dict] = []
    for conv in conversations:
        store = MemoryStore(bench.run_dir / "memdb" / f"{conv.id}")
        stats = await bench.ingest(conv, store)
        ingest_stats.append({"conv": conv.id, **stats})
        all_records.extend(await bench.answer_qa(conv, store))

    by_cat: dict = {}
    for r in all_records:
        by_cat.setdefault(r["category"], []).append(r["f1"])
    summary = {
        "strategy": cfg.strategy,
        "model": cfg.model,
        "qa_model": cfg.qa_model or cfg.model,
        "conversations": len(conversations),
        "questions": len(all_records),
        "f1_mean": round(sum(r["f1"] for r in all_records) / max(len(all_records), 1), 3),
        "em_mean": round(sum(r["em"] for r in all_records) / max(len(all_records), 1), 3),
        "f1_by_category": {
            str(cat): round(sum(v) / len(v), 3) for cat, v in sorted(by_cat.items())
        },
        "ingest": ingest_stats,
        "results_file": str(bench.results_path),
    }
    (bench.run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info(
        "Bench done: f1=%.3f em=%.3f (%d questions)",
        summary["f1_mean"],
        summary["em_mean"],
        summary["questions"],
    )
    return summary
