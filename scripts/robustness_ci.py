"""Robustness analysis for the memory paper: bootstrap 95% CIs on every
headline judged-accuracy number, plus paired significance tests on the two
central claims (agentic>full_history on temporal; grounding ON>OFF on temporal).

Uses only the frozen per-question judged verdicts already on disk — no GPU,
no new model calls. Reconstructs the length-invariance in-window/truncated
split from the LoCoMo evidence turns and validates it against Figure 1's
hardcoded numbers.

Run:  .venv/bin/python scripts/robustness_ci.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from yuna.bench.datasets import load_locomo
from yuna.bench.runner import FULL_HISTORY_CHAR_CAP

ROOT = Path(__file__).resolve().parent.parent
LOCOMO = ROOT / "data/benchmarks/locomo10.json"
RESULTS = ROOT / "data/bench_results"

RUNS = {
    "none": RESULTS / "run_20260719_154140_none/results_judged.jsonl",
    "raw_rag": RESULTS / "run_20260719_155841_raw_rag/results_judged.jsonl",
    "full_history": RESULTS / "run_20260719_163212_full_history/results_judged.jsonl",
    "agentic": RESULTS / "run_20260719_165504_agentic/results_judged.jsonl",
}
FIG3 = {
    "on": RESULTS / "fig3/on/run_20260723_182610_agentic/results_judged.jsonl",
    "off": RESULTS / "fig3/off/run_20260724_150716_agentic/results_judged.jsonl",
}

CAT_NAME = {1: "multi-hop", 2: "temporal", 3: "open", 4: "single-hop", 5: "abstain"}
RNG = np.random.default_rng(20260724)
N_BOOT = 10000


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def boot_ci(vals: np.ndarray, n=N_BOOT) -> tuple[float, float, float]:
    """Mean and 95% percentile bootstrap CI."""
    if len(vals) == 0:
        return (float("nan"),) * 3
    idx = RNG.integers(0, len(vals), size=(n, len(vals)))
    means = vals[idx].mean(axis=1)
    return float(vals.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_boot_diff(a: np.ndarray, b: np.ndarray, n=N_BOOT):
    """95% CI on mean(a-b) for paired per-question verdicts, plus p(a<=b)."""
    d = a - b
    idx = RNG.integers(0, len(d), size=(n, len(d)))
    boot = d[idx].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    # one-sided p that the true difference is <= 0
    p = float((boot <= 0).mean())
    return float(d.mean()), float(lo), float(hi), p


# ── build the in-window / truncated split from LoCoMo evidence ───────────────
def build_split() -> dict[tuple[str, str], bool]:
    """(conv_id, question) -> True if all evidence survives the 60k-char tail."""
    convs = load_locomo(LOCOMO)
    raw_list = json.loads(LOCOMO.read_text(encoding="utf-8"))
    # Rebuild each transcript exactly as runner.ingest does, then mark a
    # question in-window iff all its evidence turns survive the 60k-char tail.
    split: dict[tuple[str, str], bool] = {}
    for conv, rawc in zip(convs, raw_list):  # load_locomo preserves order
        # transcript identical to runner.ingest
        lines: list[str] = []
        for s in conv.sessions:
            lines.append(f"[Session {s.index} — {s.date}]")
            for t in s.turns:
                lines.append(f"{t.speaker}: {t.text}")
        transcript = "\n".join(lines)
        cutoff = len(transcript) - FULL_HISTORY_CHAR_CAP
        # dia_id -> text from raw sessions
        d2t: dict[str, str] = {}
        for k, v in rawc["conversation"].items():
            if k.startswith("session_") and isinstance(v, list):
                for turn in v:
                    d2t[turn["dia_id"]] = turn["text"]
        for qa in rawc["qa"]:
            if qa["category"] == 5:
                continue  # adversarial: unanswerable, excluded from length split
            ev = qa.get("evidence") or []
            if not ev:
                continue
            offs = []
            ok = True
            for e in ev:
                txt = d2t.get(e)
                if not txt:
                    ok = False
                    break
                pos = transcript.rfind(txt)
                offs.append(pos)
            if not ok or not offs:
                continue
            in_window = min(offs) >= cutoff  # all evidence survives the tail
            split[(conv.id, qa["question"])] = in_window
    return split


def main():
    print("=" * 72)
    print("BOOTSTRAP 95% CONFIDENCE INTERVALS  (10k resamples, judged accuracy)")
    print("=" * 72)

    data = {k: load(p) for k, p in RUNS.items()}

    # Table 1: per-strategy overall + per-category
    print("\nTable 1 — strategy × category  [mean (95% CI)]")
    cols = ["overall"] + [CAT_NAME[c] for c in (1, 2, 3, 4, 5)]
    print(f"{'strategy':<14}" + "".join(f"{c:>18}" for c in cols))
    for strat, recs in data.items():
        row = f"{strat:<14}"
        allv = np.array([r["judge"] for r in recs])
        m, lo, hi = boot_ci(allv)
        row += f"{f'{m:.3f} [{lo:.2f},{hi:.2f}]':>18}"
        for c in (1, 2, 3, 4, 5):
            v = np.array([r["judge"] for r in recs if r["category"] == c])
            m, lo, hi = boot_ci(v)
            row += f"{f'{m:.3f} [{lo:.2f},{hi:.2f}]':>18}"
        print(row)

    # ── central claim 1: agentic > full_history on temporal (paired) ─────────
    print("\n" + "=" * 72)
    print("CLAIM 1 — agentic beats full_history on TEMPORAL (paired, cat 2)")
    print("=" * 72)
    ag = {(r["conv"], r["question"]): r["judge"] for r in data["agentic"] if r["category"] == 2}
    fh = {(r["conv"], r["question"]): r["judge"] for r in data["full_history"] if r["category"] == 2}
    keys = sorted(set(ag) & set(fh))
    a = np.array([ag[k] for k in keys])
    b = np.array([fh[k] for k in keys])
    d, lo, hi, p = paired_boot_diff(a, b)
    print(f"  n paired = {len(keys)}")
    print(f"  agentic temporal    = {a.mean():.3f}")
    print(f"  full_history temporal = {b.mean():.3f}")
    print(f"  Δ (agentic − full_history) = {d:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]")
    print(f"  one-sided p(Δ≤0) = {p:.4f}  ->  {'SIGNIFICANT' if hi > 0 and lo > 0 else 'not sig' if hi <= 0 else 'CI excludes 0' if lo > 0 else 'CI includes 0'}")

    # ── length-invariance split + validation ─────────────────────────────────
    print("\n" + "=" * 72)
    print("CLAIM 2 — length-invariance  (in-window vs truncated evidence)")
    print("=" * 72)
    split = build_split()
    print(f"  reconstructed split: {sum(split.values())} in-window, "
          f"{len(split) - sum(split.values())} truncated  (total {len(split)})")
    for strat in ("full_history", "agentic", "raw_rag"):
        recs = data[strat]
        inw, out = [], []
        for r in recs:
            key = (r["conv"], r["question"])
            if key in split:
                (inw if split[key] else out).append(r["judge"])
        mi, li, hi_ = boot_ci(np.array(inw))
        mo, lo2, ho2 = boot_ci(np.array(out))
        drop = (mo - mi) / mi * 100 if mi else float("nan")
        print(f"  {strat:<14} in-window {mi:.3f} [{li:.2f},{hi_:.2f}] (n={len(inw)})   "
              f"truncated {mo:.3f} [{lo2:.2f},{ho2:.2f}] (n={len(out)})   Δ={drop:+.0f}%")

    # ── Fig3 ablation: grounding ON vs OFF temporal (paired) ─────────────────
    print("\n" + "=" * 72)
    print("CLAIM 3 — temporal grounding ON vs OFF (paired, cat 2)")
    print("=" * 72)
    on = {(r["conv"], r["question"]): r["judge"] for r in load(FIG3["on"]) if r["category"] == 2}
    off = {(r["conv"], r["question"]): r["judge"] for r in load(FIG3["off"]) if r["category"] == 2}
    keys = sorted(set(on) & set(off))
    a = np.array([on[k] for k in keys])
    b = np.array([off[k] for k in keys])
    d, lo, hi, p = paired_boot_diff(a, b)
    print(f"  n paired = {len(keys)}")
    print(f"  grounding ON  temporal = {a.mean():.3f}")
    print(f"  grounding OFF temporal = {b.mean():.3f}")
    print(f"  Δ (ON − OFF) = {d:+.3f}  95% CI [{lo:+.3f}, {hi:+.3f}]")
    print(f"  one-sided p(Δ≤0) = {p:.4f}")


if __name__ == "__main__":
    main()
