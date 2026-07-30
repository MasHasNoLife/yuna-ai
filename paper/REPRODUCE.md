# Reproducing *Memory That Doesn't Expire*

Every number in the paper regenerates from this repository with the commands
below. The system under test is the same code path the live application uses;
the benchmark drives it headlessly.

Runtime on the paper's hardware (single RTX 4070, 12 GB): a full four-strategy
sweep plus the ladder and the ablation is roughly one overnight run. Nothing
here needs more than 12 GB of VRAM.

---

## 1. Environment

```bash
git clone https://github.com/MasHasNoLife/yuna-ai
cd yuna-ai
python -m venv .venv && .venv/bin/pip install -e .
```

Models run locally through [Ollama](https://ollama.com). Pull the exact tags
used in the paper:

```bash
# chat + extractor (held fixed as the answerer in every condition)
ollama pull hf.co/HauhauCS/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M
# extractor ladder (RQ1)
ollama pull qwen2.5:3b
ollama pull qwen2.5:7b
ollama pull qwen2.5:14b   # also the LLM judge
# embeddings
ollama pull nomic-embed-text
```

Versions the paper's numbers were produced on: Python 3.12, torch 2.8 (CUDA
12.8), Ollama 0.30, ChromaDB 1.5, judge model `qwen2.5:14b` at temperature 0.

## 2. Data

LoCoMo is not redistributed here. Fetch the official 10-conversation release:

```bash
mkdir -p data/benchmarks
curl -L -o data/benchmarks/locomo10.json \
  https://raw.githubusercontent.com/snap-research/locomo/main/data/locomo10.json
```

Expected: 10 conversations, 1,986 QA pairs across 5 categories.

## 3. Table 1 — memory strategies

Each strategy over all 10 conversations. `--conversations 0` means "all".

```bash
for s in none raw_rag full_history agentic; do
  .venv/bin/python -m yuna.cli bench --strategy "$s" --conversations 0 \
    --out data/bench_results
done
```

Each run writes `data/bench_results/run_<timestamp>_<strategy>/results.jsonl`
and a `summary.json` (raw token-F1/EM). Judge every run (§6) for the accuracy
numbers in the paper.

## 4. Table 3 — extractor ladder (RQ1)

Vary the extractor, hold the answerer fixed at Gemma4-12B with `--qa-model`, so
differences reflect extraction quality alone:

```bash
GEMMA=hf.co/HauhauCS/Gemma4-12B-QAT-Uncensored-HauhauCS-Balanced:Q4_K_M
for m in qwen2.5:3b qwen2.5:7b qwen2.5:14b; do
  .venv/bin/python -m yuna.cli bench --strategy agentic --conversations 0 \
    --model "$m" --qa-model "$GEMMA" --out data/bench_results/ladder
done
```

## 5. Figure 3 — temporal grounding ablation

The matched on/off pair, same extractor, only grounding toggled:

```bash
# grounding ON (this is just the agentic run from §3, reused)
.venv/bin/python -m yuna.cli bench --strategy agentic --conversations 0 \
  --out data/bench_results/fig3/on
# grounding OFF
.venv/bin/python -m yuna.cli bench --strategy agentic --conversations 0 \
  --no-grounding --out data/bench_results/fig3/off
```

`--no-grounding` disables both date absolutization and the session-date context,
so stored events carry no absolute date except where the source turn stated one.

## 6. Judging (primary metric)

Every accuracy number in the paper is LLM-as-judge, not raw F1. Rescore each run:

```bash
.venv/bin/python -m yuna.bench.judge \
  data/bench_results/run_<timestamp>_<strategy>/results.jsonl \
  --model qwen2.5:14b
```

This writes `results_judged.jsonl` and `summary_judged.json` beside the input.
Adversarial (category 5) questions are scored deterministically by abstention,
not by the judge.

## 7. Table 2 and §5.7 — length split and confidence intervals

Once the four strategy runs and both Figure 3 legs are judged, one script
regenerates the length-invariance split, all bootstrap CIs, and the paired
significance tests:

```bash
.venv/bin/python scripts/robustness_ci.py
```

It reconstructs each conversation's transcript exactly as the runner does, marks
each question in-window or truncated against the 60k-character cap, and prints
the numbers behind Table 2, Figure 1, and §5.7. If you moved the run
directories, edit the `RUNS` / `FIG3` paths at the top of the script.

## 8. Figures

```bash
.venv/bin/python paper/figures/make_fig1.py   # length-invariance
.venv/bin/python paper/figures/make_fig2.py   # architecture
# Figure 3 is rendered inline by the ablation analysis; see the script header
```

Figure 1's numbers are hard-coded from `robustness_ci.py` output; re-run that
first and update the two-point series if any run changes.

## 9. Extraction precision (§5.5b)

The 200-item audit is a static, human-labelled file, not a script:
`data/gold/annotation_sheet.tsv` (columns: id, conv, speaker, kind, memory,
verdict, notes). Count the verdicts:

```bash
cut -f6 data/gold/annotation_sheet.tsv | tail -n +2 | sort | uniq -c
# -> 198 OK, 1 BAD, 1 VAGUE  = 199/200 faithful, 198/200 strict
```

Per-conversation transcripts for tracing each memory to its source turn are in
`data/gold/transcripts/`.

## 10. What is and isn't in the repository

Released here: the benchmark harness (`src/yuna/bench/`), the judge prompt
(`src/yuna/bench/judge.py`), the analysis script (`scripts/robustness_ci.py`),
the precision audit (`data/gold/`), and figure scripts (`paper/figures/`).

The raw per-question run outputs (`data/bench_results/**/results_judged.jsonl`,
~120 MB) are **not** git-tracked — `data/` is gitignored. To let others verify
without re-running the models, publish them as a GitHub release asset or a
Zenodo deposit and link it from the paper. Until that is done, the paper should
not claim the raw outputs are released (only the harness that regenerates them).
