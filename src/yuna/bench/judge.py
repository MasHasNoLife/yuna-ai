"""LLM-as-judge rescoring for bench results.

Token F1 punishes correct-but-rephrased answers ("her mom" vs "Caroline's
mother"). This rescorer replays a results.jsonl through a judge model that
sees question + gold + prediction and votes CORRECT/WRONG. Adversarial
(category 5) rows are scored deterministically via is_abstain — no judge call.

Usage:
    python -m yuna.bench.judge data/bench_results/run_X/results.jsonl \
        [--model qwen2.5:14b] [--out same-dir]

Writes results_judged.jsonl (adds "judge" field) and summary_judged.json
next to the input. Judge calls are temperature-0; the judge model should
differ from the answerer where possible (bias is uniform across conditions
either way, since every strategy's answers face the same judge).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from yuna.core import llm
from yuna.core.config import get_config
from yuna.core.logging import get_logger, setup_logging

from yuna.bench.scoring import is_abstain  # isort: skip

log = get_logger("bench.judge")

JUDGE_PROMPT = (
    "You are grading a question-answering system about past conversations.\n"
    "Question: {question}\n"
    "Gold answer: {gold}\n"
    "System's answer: {pred}\n\n"
    "Does the system's answer convey the same information as the gold answer? "
    "Minor wording differences, extra detail, or partial dates that match are CORRECT. "
    "Missing, contradictory, or evasive answers are WRONG.\n"
    "Reply with exactly one word: CORRECT or WRONG."
)

CONCURRENCY = 4


async def judge_file(results_path: Path, model: str) -> dict:
    import ollama

    client = ollama.AsyncClient(host=get_config().endpoints.ollama_url)
    rows = [json.loads(line) for line in results_path.open(encoding="utf-8")]
    sem = asyncio.Semaphore(CONCURRENCY)

    async def judge_row(r: dict) -> None:
        if r["category"] == 5:
            r["judge"] = float(is_abstain(r["pred"]))
            return
        prompt = JUDGE_PROMPT.format(question=r["question"], gold=r["gold"], pred=r["pred"])
        async with sem:
            verdict = await llm.chat(
                client, model, [{"role": "user", "content": prompt}], temperature=0.0
            )
        r["judge"] = float("CORRECT" in verdict.strip().upper()[:20])

    for i in range(0, len(rows), 50):
        await asyncio.gather(*(judge_row(r) for r in rows[i : i + 50]))
        log.info("[judge] %d/%d rows", min(i + 50, len(rows)), len(rows))

    by_cat: dict = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r["judge"])
    summary = {
        "source": str(results_path),
        "judge_model": model,
        "questions": len(rows),
        "judge_mean": round(sum(r["judge"] for r in rows) / max(len(rows), 1), 3),
        "judge_by_category": {
            str(cat): round(sum(v) / len(v), 3) for cat, v in sorted(by_cat.items())
        },
    }
    out_dir = results_path.parent
    with (out_dir / "results_judged.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (out_dir / "summary_judged.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("Judge done: acc=%.3f (%d questions) -> %s", summary["judge_mean"], len(rows), out_dir)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="path to a run's results.jsonl")
    parser.add_argument("--model", default="qwen2.5:14b", help="judge model")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    setup_logging(args.verbose, log_dir=get_config().paths.logs)
    summary = asyncio.run(judge_file(args.results, args.model))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
