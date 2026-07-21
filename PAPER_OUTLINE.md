# Paper Outline — "Remember Cheaply" (working title)

Full title candidate: **"Memory That Doesn't Expire: Agentic Long-Term Memory
for Conversational Agents on a Single Consumer GPU"**

Target: 6–8 pages (short/workshop paper), arXiv by mid-October 2026.
Everything here is the skeleton to write into — status tags: ✅ done data /
🟡 infra ready, run pending / ⬜ not started.

---

## The one-sentence spine (every section serves this)

> A small local model (12B, 12 GB GPU) can run *agentic* long-term memory that
> **beats full-context stuffing on temporal reasoning** and uses **~67× less
> context**, making a persistent, consistent companion feasible on consumer
> hardware — where naive context-stuffing collapses the moment a conversation
> outgrows the window.

If a sentence in the paper doesn't support that spine, it gets cut.

---

## 0. Title + Abstract (~150 words) ⬜
- Problem: chatbots forget; memory papers assume GPT-4-class extractors.
- What we do: agentic FACT/EVENT/SELF memory on a 12B local model + a benchmark.
- Headline numbers: temporal 0.33 vs 0.14 (2×); 67× less context; length-invariant.
- One-line takeaway: memory beats stuffing where it matters, at a fraction of cost.

## 1. Introduction (~1 page) ⬜
- The forgetting problem, why it matters for companions/agents.
- The gap: existing memory systems (MemGPT, Mem0) assume big API models; nobody
  asks "can a small *local* model be the memory manager on consumer hardware?"
- Our contributions, as a bullet list (see below).
- A teaser figure (Figure 1) up front.
- **Contributions:**
  1. A reproducible benchmark of the FACT/UPDATE/FORGET agentic protocol on
     small open models (3B–14B), with an ablation vs none / full-history / raw-RAG.
  2. The finding that agentic memory is **length-invariant** and wins temporal
     reasoning, while context-stuffing degrades past its window.
  3. An open-source live system (Yuna) with async extraction that never blocks
     the reply — real-time on a single 12 GB GPU.

## 2. Related Work (~1 page) ⬜
- Agent memory: MemGPT, Mem0, Generative Agents, Reflexion, LongMem.
- Long-conversation benchmarks: LoCoMo, MSC, MemoryBank, PerLTQA.
- RAG foundations: RAG, Self-RAG, retrieval for dialogue.
- Small-model capability gap (grounds "can a 7B do the memory job?").
- ~15 papers, 2–3 sentences each, each ending in "unlike them, we …".

## 3. Method / System (~1.5 pages) ✅ mostly (system exists)
- 3.1 Architecture overview + pipeline diagram (Figure 2).
- 3.2 The typed memory protocol: FACT / EVENT / SELF / UPDATE / FORGET,
  denial handling, junk filter. This is the core mechanism.
- 3.3 **Temporal grounding** — absolutize relative dates at extraction time,
  stamp memories with session dates. (Our key positive result rides on this.)
- 3.4 Recall: contextual embedding query, age-aware annotation, self-partition.
- 3.5 Async design: extraction runs after the reply → never delays TTFT.
- 3.6 The four strategies as experimental conditions.

## 4. Experimental Setup (~1 page) ✅ mostly
- 4.1 Benchmark: LoCoMo (10 convs, ~4k turns, 1,986 QA, 5 categories). MSC as
  second benchmark. ⬜ MSC
- 4.2 Conditions: strategy {none, full_history, raw_rag, agentic} ✅;
  extractor ladder {qwen2.5 3B/7B/14B} 🟡; chat model held fixed (Gemma4-12B).
- 4.3 Metrics: token-F1 + EM ✅; abstain-aware scoring for adversarial ✅;
  LLM-as-judge (qwen2.5-14b) 🟡; extraction precision vs gold set ⬜.
- 4.4 Hardware/cost: RTX 4070 12 GB, quant, TTFT, tok/s, VRAM. ✅

## 5. Results (~2 pages — the heart) 
- 5.1 **Main table**: 4 strategies × F1/EM × 5 categories × context cost. ✅
- 5.2 **Temporal result**: agentic 0.33 vs 0.14/0.16 (~2×). Before/after
  grounding ablation (0.00 → 0.33). ✅ → Figure 3.
- 5.3 **Length-invariance** (the money figure): F1 vs evidence-in-window.
  full_history 0.406→0.110 (−73%); agentic 0.215→0.249 flat; agentic 2.3× on
  truncated-evidence questions. ✅ → **Figure 1** (flat line crossing falling line).
- 5.4 **Context efficiency**: 889 vs 59,585 chars/question (67×) for 73% of F1. ✅
- 5.5 **Extractor ladder** (RQ1): quality vs extractor size. 🟡 run pending.
- 5.6 **Extraction quality**: precision/recall vs gold annotations. ⬜
- 5.7 **Cost**: TTFT ~0.9 s, 40+ tok/s, +~2 GB VRAM, async non-blocking. ✅
- 5.8 Judge-rescored versions of 5.1 (fairer, fixes c5 artifact). 🟡

## 6. Discussion & Limitations (~0.5 page) ⬜
- Where agentic loses: single-hop copy questions (full_history 0.54 vs 0.29) —
  stuffing wins when the literal answer is in-window. State it plainly.
- Extraction latency at ingest (offline, acceptable; async at chat time).
- Single embedding model, single chat model — scope.
- Consolidation of near-duplicate memories = future work.
- LLM-judge bias (mitigated: different judge model, cat-5 deterministic).

## 7. Conclusion (~0.25 page) ⬜
- Three sentences: memory beats stuffing where it counts, cheaply, locally.

## Appendices ⬜
- A: prompts (extractor, QA, judge) verbatim.
- B: gold-annotation protocol + agreement.
- C: full per-category tables, all seeds.
- D: live-system notes (Yuna), ecological validity.

---

## Figures/tables checklist
- Figure 1 (length-invariance) ✅ data — the paper's signature figure.
- Figure 2 (architecture) ⬜ draw.
- Figure 3 (temporal before/after) ✅ data.
- Table 1 (main 4-strategy) ✅.
- Table 2 (extractor ladder) 🟡.
- Table 3 (extraction precision vs gold) ⬜.

## Writing order (do NOT write front-to-back)
1. Results section from the tables we already have (5.1–5.4, 5.7). ← start here, data exists.
2. Method (system already built — describe what's in the repo).
3. Experimental setup.
4. Related work (read in parallel, references.bib from day one).
5. Intro (write last — it's a summary of the finished paper).
6. Abstract + conclusion (very last).

## What still gates a complete draft
- 🟡 Extractor ladder run (5.5, Table 2).
- 🟡 Judge rescoring run (5.8).
- ⬜ Gold annotation → extraction precision (5.6, Table 3) — human task.
- ⬜ MSC second benchmark (4.1) — strengthens generality.
- ⬜ Figure 2 (architecture diagram).
