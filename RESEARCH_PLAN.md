# Research Paper Plan — Agentic RAG Memory for Small Local LLMs

Target: arXiv preprint by **mid-October 2026**, conference/workshop submission after,
citable in fall 2027 Masters applications (EM LCT, Sweden, Finland, Saarland, DTU).

This replaces the earlier INT4-TTS plan (kept in git history). The memory angle fits
the **generative-AI / NLP Masters programmes** being applied to far better than a
speech-efficiency paper, and the system under test is already running in this repo.

---

## 1. The paper

**Working title:** *"Remember Cheaply: Agentic Long-Term Memory for Conversational
Agents with Small Local LLMs"*

**Research questions:**

- **RQ1 (extraction quality):** How well can small local models (3B–14B) perform
  agentic memory management — deciding what to store, update, and forget
  (FACT/UPDATE/FORGET) — compared to large API models, measured on long
  multi-session dialogues?
- **RQ2 (end-to-end benefit):** How much does RAG-based memory improve a small
  chat model's long-horizon consistency and factual recall versus (a) no memory,
  (b) naive full-history stuffing, and (c) plain semantic retrieval over raw
  dialogue turns (no extraction)?
- **RQ3 (cost):** What are the latency/VRAM costs, and does asynchronous
  background extraction keep the interactive experience real-time on a single
  consumer GPU (12 GB)?

**Contributions:**
1. A reproducible benchmark of the **FACT/UPDATE/FORGET agentic memory protocol**
   across small open models (e.g. qwen2.5 3B/7B/14B, llama3.1 8B, gemma family)
   with a large API model as ceiling.
2. An **ablation of the memory pipeline**: extraction vs. raw-turn RAG vs. full
   history vs. no memory, on public long-conversation benchmarks.
3. An open-source **live system** (Yuna, this repo): async extraction that never
   blocks the reply, ChromaDB recall, and per-turn instrumentation (recall ms,
   TTFT, memory-op counts) already built into the web interface.

**Why this angle wins:** memory/personalization for LLM agents is an active,
citable research conversation (MemGPT, Mem0, generative agents); the "small local
models" constraint is a genuine gap (most memory papers assume GPT-4-class
extractors); and the working system + metrics pipeline already exists here, so the
engineering lift is mostly evaluation, not construction.

---

## 2. Experimental design

**Benchmarks (the test material):**

| Dataset | What it gives |
|---|---|
| **LoCoMo** (Maharana et al. 2024) | very long multi-session conversations + QA pairs — the standard long-term-memory eval |
| **MSC** (Multi-Session Chat, Xu et al. 2022) | multi-session persona consistency |
| Yuna live logs (small, appendix) | ecological validity: real usage traces from the web UI's `events.jsonl` |

**Conditions (the independent variables):**

- *Memory strategy:* none · full-history · raw-turn RAG · agentic FACT/UPDATE/FORGET (ours)
- *Extractor model:* qwen2.5-3B → 14B ladder + one large API model (ceiling)
- *Chat model held fixed* (one small local model) so differences are attributable
  to memory, not the responder.

**Metrics (the dependent variables):**

| Axis | Metric | Tool |
|---|---|---|
| Recall QA | answer accuracy / F1 on LoCoMo QA (LLM-as-judge with fixed rubric + spot-check) | eval script |
| Extraction quality | precision/recall of stored facts vs. gold annotations; contradiction rate after UPDATE/FORGET | manual gold set on a LoCoMo subset (~200 ops) |
| Consistency | persona-consistency score on MSC | LLM-as-judge, dual-judge agreement reported |
| Cost | extraction latency, recall latency, TTFT impact, peak VRAM | already emitted by `yuna.core.metrics` |

3 seeds where sampling is involved; report mean ± std. Judge prompts, seeds, and
raw outputs all published.

**Ethics/logistics notes:**
- Public benchmark data only for headline claims — no user-study approval needed.
- Live-log appendix uses the author's own conversations (self-consent, stated).
- LLM-as-judge bias addressed with two judge models + human spot-check of 10%.

---

## 3. Engineering work (in this repo)

Ordered; items 1–4 are the critical path. Most infrastructure already exists:
`fact_extractor.py` (protocol + parser, unit-tested), `memory.py` (ChromaDB),
`llm_backends.py` (local + API), `metrics.py` (per-turn JSONL).

1. **Benchmark harness** (`bench/`): replay LoCoMo/MSC sessions through
   ChatSession headlessly, per condition, dumping per-turn JSON. Config-driven,
   no manual steps.
2. **Condition switches**: memory strategy flag (none / full-history / raw-RAG /
   agentic) and extractor-model flag — thin additions to existing config.
3. **Eval scripts**: QA scoring (LLM-as-judge + exact-match where possible),
   fact precision/recall against the gold subset, plots/tables generation.
4. **Gold annotation**: hand-label FACT/UPDATE/FORGET decisions for ~200
   operations on a LoCoMo subset (2–3 evenings of work, do early).
5. **Reproducibility**: pinned eval requirements, seeds, `REPRODUCE.md`,
   published raw results.
6. **Repo hygiene**: keep CI green; the repo *is* the artifact reviewers open.

---

## 3.5 Pilot findings — July 19, 2026 (1 conv × 2 sessions × 6 QA, qwen2.5-14b)

First end-to-end run of the harness (`yuna bench`), token-F1 on LoCoMo conv-26:

| strategy | F1 | EM | memories stored | ingest |
|---|---|---|---|---|
| none | 0.000 | 0.000 | 0 | — |
| raw_rag | 0.320 | 0.167 | 35 raw turns | 9 s |
| agentic | 0.208 | 0.167 | 17 typed facts | 30 s |

Sanity checks pass (none = 0; memory > none). Two findings that shape the work:

1. **Temporal grounding is the agentic pipeline's weak spot.** Extraction stores
   relative time ("last Saturday", "last year") anchored to nothing, and memory
   timestamps are wall-clock at ingest, not the session date — so every temporal
   (category-2) question failed while raw_rag (whose docs carry the session-date
   prefix) got partial credit. Fix: pass the session/conversation date into
   extraction and store it as the memory timestamp; normalize relative dates.
   This becomes a clean before/after ablation.
2. **Extraction misses implied facts** (e.g. identity implied across several
   stored facts but never stated as one) — motivates the consolidation pass.

Extraction quality itself was high: typed facts clean, [SELF] facts correctly
routed to the speaker's partition, zero junk stored.

### Full-conversation run — July 19 (conv-26: 19 sessions, 419 turns, 199 QA,
### Gemma4-12B-QAT, think disabled, temporal grounding ON)

| strategy | F1 | EM | c1 multi-hop | c2 temporal | c3 open | c4 single-hop | avg ctx (chars) | ingest |
|---|---|---|---|---|---|---|---|---|
| none | 0.003 | 0.000 | 0.00 | 0.00 | 0.03 | 0.00 | 21 | — |
| raw_rag | 0.201 | 0.085 | 0.21 | 0.19 | 0.06 | 0.36 | 1,439 | 22 s |
| **agentic (ours)** | 0.244 | 0.101 | 0.26 | **0.43** | 0.13 | 0.31 | **927** | 259 s |
| full_history | **0.297** | 0.121 | 0.29 | 0.15 | 0.13 | **0.59** | 60,000 | — |

**Headline findings:**

1. **Temporal grounding works — and beats everything.** After the fix (absolute
   dates inlined at extraction), agentic scores **0.43 on temporal questions —
   ~3× full-history (0.15) and ~2× raw RAG (0.19)**. Reading "(on 20 May 2023)"
   from a distilled fact beats date arithmetic over a 60k-char transcript.
   Before the fix (pilot): agentic temporal was 0.00. Clean before/after ablation.
2. **Context efficiency:** agentic reaches 82% of full-history's F1 using
   **65× less context** (927 vs 60,000 chars/question) — the small-local-model
   story: full-history needs a 16k+ window; agentic fits any 4k model.
3. Full-history's edge is single-hop copy extraction (0.59) — expected; it
   degrades as conversations outgrow the window (this conv already truncated
   at 60k chars).
4. Adversarial (c5) ≈ 0 for all strategies — scoring artifact (gold phrasing
   of "no answer" varies); needs an answerability-aware scorer or LLM judge.

**Next:** extractor-model ladder (3B→14B), all 10 conversations, 3 seeds,
LLM-as-judge scoring alongside F1, consolidation-pass condition.

### FULL BENCHMARK — July 19 (all 10 conversations, 1,986 QA, Gemma4-12B-QAT,
### think disabled, temporal grounding ON) — the definitive table

| strategy | F1 | EM | c1 multi-hop | c2 temporal | c3 open | c4 single-hop | avg ctx (chars) | QA lat |
|---|---|---|---|---|---|---|---|---|
| none | 0.001 | 0.000 | 0.00 | 0.00 | 0.01 | 0.00 | 21 | 0.5 s |
| raw_rag | 0.201 | 0.095 | 0.23 | 0.16 | 0.05 | 0.33 | 1,428 | 0.8 s |
| full_history | **0.308** | **0.158** | **0.35** | 0.14 | **0.12** | **0.54** | 59,585 | 0.7 s |
| **agentic (ours)** | 0.226 | 0.100 | 0.31 | **0.33** | 0.10 | 0.29 | **889** | 0.7 s |

**The honest story at full scale (this is what goes in the paper):**

1. **Temporal grounding is the headline, and it holds at scale.** Agentic wins
   temporal questions **0.33 — ~2× full-history (0.14) and ~2× raw RAG (0.16)**.
   The single-conversation run showed 0.43; across all 10 it settles at 0.33,
   still the decisive winner. Distilled absolute dates beat date arithmetic over
   a 60k-char transcript, every time. This is the paper's central positive claim.
2. **Extreme context efficiency — the small-local-model argument.** Agentic
   reaches **73% of full-history's F1 using 67× less context** (889 vs 59,585
   chars/question). full-history needs a 16k+ window and is already truncating
   these conversations at 60k chars; agentic fits any 4k-context model on a 12 GB
   GPU. This is RQ3 answered: the memory pays for itself in context budget.
3. **Where agentic loses, and why (state it plainly):** full-history wins overall
   F1 (0.308 vs 0.226), driven by single-hop copy questions (0.54 vs 0.29) — if
   the literal answer sits verbatim in the window, stuffing beats distillation.
   Agentic is competitive on multi-hop (0.31 vs 0.35). The takeaway is NOT "ours
   wins everything" — it's "ours wins temporal reasoning and wins efficiency by
   ~2 orders of magnitude, at a modest overall-F1 cost that shrinks as
   conversations outgrow any fixed window."
4. **Adversarial (c5) ≈ 0 everywhere — a scoring artifact, not a finding.** Token
   F1 can't credit "Not mentioned" vs varied gold phrasings of unanswerable.
   Fix before publication: LLM-as-judge / answerability-aware scorer.

**Why this is still a strong paper:** the framing is efficiency + temporal
competence for small local models, not beating GPT-4-style context stuffing on
raw recall. Both surviving claims (2× temporal, 67× context) are clean,
measurable, and reproducible from this repo.

### The window-truncation analysis (July 19) — the result that completes the story

full_history keeps the LAST 60k chars, so early sessions of long conversations
get cut. Splitting the 1,986 questions by whether their evidence survived:

| strategy | evidence in window (n=1332) | evidence truncated (n=650) |
|---|---|---|
| full_history | **0.406** | 0.110 (**−73%**) |
| agentic (ours) | 0.215 | **0.249** (flat) |
| raw_rag | 0.183 | 0.240 (flat) |

- full_history's overall win comes ENTIRELY from questions whose answer still
  sits verbatim in the window; beyond it, it collapses to near-none levels.
- Agentic (and raw_rag) are invariant to conversation length — retrieval doesn't
  care how old the fact is. On the third of the benchmark that already exceeds
  the window, **agentic beats full_history 2.3×** (0.249 vs 0.110).
- As conversations grow, the truncated fraction → 100%: context stuffing
  degrades toward zero while memory stays flat. This is the paper's Figure 1:
  F1 vs evidence age, flat line (ours) crossing a falling line (stuffing).

### LLM-judge rescoring + extractor ladder — July 22 (all 1,986 QA, judged by
### qwen2.5-14b; c5 scored by abstention)

**Table 1 — strategies (judged accuracy, extractor=answerer=Gemma4-12B):**

| strategy | judged acc | c1 multihop | c2 **temporal** | c3 open | c4 single-hop | c5 abstain |
|---|---|---|---|---|---|---|
| none | 0.228 | 0.00 | 0.01 | 0.00 | 0.00 | 1.00 |
| raw_rag | 0.434 | 0.18 | 0.29 | 0.10 | 0.39 | 0.85 |
| full_history | **0.544** | **0.39** | 0.24 | **0.22** | **0.66** | 0.72 |
| agentic (ours) | 0.457 | 0.31 | **0.37** | 0.16 | 0.35 | 0.88 |

**Table 2 — extractor ladder (judged, answerer fixed = Gemma4-12B):**

| extractor | judged acc | c1 | c2 **temporal** | c3 | c4 |
|---|---|---|---|---|---|
| qwen2.5:3b | 0.309 | 0.12 | **0.06** | 0.05 | 0.16 |
| qwen2.5:7b | 0.348 | 0.15 | **0.19** | 0.12 | 0.21 |
| qwen2.5:14b | 0.470 | 0.29 | **0.34** | 0.12 | 0.40 |

**What the judge confirms (and refines):**
1. **Temporal win holds under the fairer metric.** agentic c2 = 0.37 vs
   full_history 0.24 and raw_rag 0.29 — still the top temporal strategy
   (~1.5× full_history). The judge narrows the F1 gap (was 2×) but the
   direction is robust.
2. **full_history wins overall judged acc (0.544)** on single-hop copy (0.66)
   and multi-hop (0.39). Same honest story: stuffing wins when the answer sits
   in-window. The **length-invariance analysis is the rebuttal, now confirmed on
   judged scores** (excl. c5): full_history 0.671 in-window → **0.163 truncated
   (−76%)**; agentic 0.337 → **0.330 (flat)**; raw_rag 0.305 → 0.334 (flat). On
   truncated-evidence questions agentic beats full_history **2.0×**. Figure 1 ✅.
3. **c5 caveat:** abstain scoring lifts every floor (none = 0.228 is *entirely*
   c5 credit — a memoryless model correctly abstains on unanswerables). The
   discriminating signal is c1–c4; report c5 separately, not folded into a
   single headline number.
4. **RQ1 answer — the memory manager cannot be too small.** Judged acc scales
   monotonically 3B→7B→14B (0.309 → 0.348 → 0.470), and **temporal grounding is
   the first capability to break**: c2 = 0.06 (3B) → 0.19 (7B) → 0.34 (14B). A
   3B extractor essentially cannot do dated memory; competence arrives ~7–14B.
   A 14B extractor (0.470) slightly *beats* the 12B (agentic 0.457), so ~12–14B
   is the sweet spot on a 12 GB card.

**Next:** redo length-invariance split on judged scores; gold extraction
annotation (~200 ops) → precision; consolidation pass for single-hop recovery;
MSC second benchmark.

## 4. Related work to read (for §2 of the paper)

- **Agent memory systems:** MemGPT (Packer et al.), Mem0, Generative Agents
  (Park et al.), Reflexion, LongMem, RecurrentGPT.
- **Benchmarks:** LoCoMo, MSC, MemoryBank, PerLTQA — pick two, justify.
- **RAG foundations:** RAG (Lewis et al.), Self-RAG, retrieval for dialogue
  (BlenderBot 2/3 memory).
- **Small-model capability:** work on task gaps between small open models and
  frontier APIs (grounds the "can a 7B do this job?" framing).

~15–18 papers, skim-read in weeks 1–3. `references.bib` from day one.

---

## 5. Venues & timeline

**Compressed to an August finish (revised July 21).** Most of the original
Jul–Sep engineering is already done (system, harness, 4-strategy results,
length-invariance finding, outline), so the schedule pulls in ~6 weeks.

| When (2026) | Milestone |
|---|---|
| **Jul 21 – Jul 27 (wk 1)** | Extractor ladder + judge rescore run (pausable, self-serve); gold annotation (2–3 evenings); draft Results §5 from existing tables; references.bib started |
| **Jul 28 – Aug 3 (wk 2)** | MSC second benchmark run; architecture diagram (Fig 2); draft Method §3 + Setup §4; **supervisor outreach emails go out** with the results table |
| **Aug 4 – Aug 10 (wk 3)** | Draft Related Work §2 + Discussion §6; assemble all figures/tables; full internal draft end-to-end |
| **Aug 11 – Aug 17 (wk 4)** | Write Intro §1 + Abstract (last, as summaries); self-review + tighten; incorporate any early supervisor feedback |
| **Aug 18 – Aug 24 (wk 5)** | Polish pass, reproducibility (REPRODUCE.md, seeds, raw results published); proofread |
| **Aug 25 – Aug 31 (wk 6)** | **arXiv preprint live** — hard deadline; buffer week for slippage |
| Sep onward | Workshop/venue submissions (NeurIPS/ICLR/EMNLP workshops; SIGDIAL 2027) as upside — verify calls when announced |

Critical path (the only strict ordering): ladder+judge run → Results draft →
full draft → arXiv. Gold annotation and MSC run in parallel and gate only the
extraction-precision table and the second-benchmark section respectively — if
either slips, the paper still ships with LoCoMo + the judged main results.

Fallback logic unchanged: arXiv preprint + public benchmark repo is the
portfolio; peer-review acceptance is upside, not the foundation.

---

## 6. Supervisor / co-author outreach (do not skip)

The paper's biggest application value is converting into a **recommendation
letter from an academic**. In parallel with weeks 3–4:

- Shortlist 5–10 targets: dialogue/NLP faculty + authors of the memory papers
  cited + LCT-consortium-adjacent researchers (Saarland, Groningen — strategic
  overlap with the applications).
- Email = 5 sentences + repo link + 1-page benchmark report PDF. Ask for
  feedback, mention openness to collaboration/supervision.
- Best case: co-author + letter. Good case: feedback + letter. Silence costs
  nothing.

---

## 7. Definition of done

- [ ] Harness replays LoCoMo/MSC through all memory conditions unattended, outputs paper-ready tables
- [ ] Results: QA accuracy, fact precision/recall, consistency, and cost across 4 strategies × extractor ladder
- [ ] Gold-annotated extraction subset published with the repo
- [ ] 4–8 page paper + arXiv preprint live by late October 2026
- [ ] At least one academic has read it and agreed to write a letter
- [ ] Repo: CI green, REPRODUCE.md, raw results published
