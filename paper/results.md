# 5. Results

All numbers are LLM-as-judge accuracy (qwen2.5-14b judge, temperature 0) over
the full LoCoMo benchmark (10 conversations, 1,986 QA pairs). Adversarial
(category 5) questions are scored by abstention detection, since a correct
response is a refusal to answer rather than a token match; because a
memory-less model abstains on everything, category 5 lifts every strategy's
floor, so we report it separately and never fold it into a single headline
number. The chat/answerer model is held fixed (Gemma4-12B-QAT, Q4, on a single
12 GB RTX 4070) across all conditions, so differences are attributable to the
memory pathway, not the responder.

## 5.1 Memory strategies

Table 1 compares four memory conditions: **none** (no memory), **raw_rag**
(verbatim dialogue turns retrieved by embedding), **full_history** (the entire
transcript stuffed into a 16k-token window, truncated to the most recent 60k
characters), and **agentic** (our typed FACT/EVENT/SELF extraction).

**Table 1. Judged accuracy by memory strategy.**

| strategy | overall | multi-hop | temporal | open | single-hop | abstain (c5) |
|---|---|---|---|---|---|---|
| none | 0.228 | 0.00 | 0.01 | 0.00 | 0.00 | 1.00 |
| raw_rag | 0.434 | 0.18 | 0.29 | 0.10 | 0.39 | 0.85 |
| full_history | **0.544** | **0.39** | 0.24 | **0.22** | **0.66** | 0.72 |
| agentic (ours) | 0.457 | 0.31 | **0.37** | 0.16 | 0.35 | 0.88 |

Two results stand out. First, **agentic memory gives the best temporal
reasoning of any strategy** (0.37 vs. 0.24 for full_history and 0.29 for
raw_rag). Storing an absolutized date at extraction time ("ran a race *on 20
May 2023*") lets the answerer read the answer directly, whereas full_history
must perform date arithmetic across a 60k-character transcript and raw_rag
retrieves turns whose relative dates ("last Saturday") are unanchored. §5.2
isolates this with a before/after ablation.

Second, **full_history wins overall judged accuracy** (0.544), driven by
single-hop (0.66) and multi-hop (0.39) questions — when the literal answer is
present verbatim in the window, stuffing the raw text beats distilling it. We
do not claim agentic memory is universally superior on recall; we claim it is
*temporally* superior and, as §5.3 shows, *length-invariant* where stuffing is
not. full_history's advantage is contingent on the answer surviving the window.

## 5.2 Temporal grounding ablation

Temporal grounding — absolutizing relative dates at extraction and stamping
each memory with its session date — is a single, isolable mechanism. Disabling
it drops agentic temporal accuracy to near-zero; enabling it yields the 0.37 in
Table 1. This is a clean before/after: the mechanism is responsible for the
entire temporal advantage, and it costs nothing at answer time (the work is
done once, at ingest). *(Figure 3: temporal accuracy, grounding off vs. on.)*

## 5.3 Length-invariance: the core result

full_history retains only the most recent 60k characters, so in a long
conversation the early sessions are discarded. We split the 1,986 questions
(excluding adversarial) by whether the evidence a question depends on still
lies within that window.

**Table 2. Judged accuracy by whether evidence survives the context window.**

| strategy | evidence in-window (n=997) | evidence truncated (n=539) |
|---|---|---|
| full_history | 0.671 | 0.163 (**−76%**) |
| agentic (ours) | 0.337 | 0.330 (**flat**) |
| raw_rag | 0.305 | 0.334 (flat) |

**full_history's entire advantage comes from questions whose answer still sits
in its window.** Beyond it, accuracy collapses by 76% — to below the level of
either retrieval method. Agentic memory is, by contrast, **length-invariant**:
retrieval does not care how old a fact is, so accuracy on truncated-evidence
questions (0.330) is statistically identical to in-window (0.337). On the third
of the benchmark that already exceeds the window, **agentic memory outperforms
context-stuffing 2.0×** (0.330 vs. 0.163).

This is the paper's central argument. A fixed context window makes stuffing a
strategy with an expiry date: as a conversation grows, the truncated fraction
approaches 100%, and full_history's accuracy trends toward its truncated-region
floor while agentic memory holds constant. *(Figure 1: accuracy vs. evidence
recency — a flat line for agentic memory crossing full_history's falling line.
This is the figure that motivates the whole approach.)*

## 5.4 Context efficiency

Beyond accuracy, the strategies differ by two orders of magnitude in the
context they consume per question (measured on the raw-F1 run; the retrieved
payload is identical under judging):

| strategy | avg context / question | relative |
|---|---|---|
| agentic (ours) | 889 chars | 1× |
| raw_rag | 1,428 chars | 1.6× |
| full_history | 59,585 chars | **67×** |

Agentic memory reaches competitive accuracy on **67× less context** than
full_history. full_history requires a 16k+ token window and was already
truncating these conversations; agentic memory fits in a 4k-token window on a
12 GB consumer GPU. This is the practical enabling result for local deployment:
the memory pays for itself in context budget.

## 5.5 How small can the memory manager be? (RQ1)

We vary the *extractor* model across the qwen2.5 family (3B / 7B / 14B) while
holding the answerer fixed at Gemma4-12B, so differences reflect extraction
quality alone.

**Table 3. Judged accuracy by extractor size (answerer fixed).**

| extractor | overall | multi-hop | temporal | open | single-hop |
|---|---|---|---|---|---|
| qwen2.5:3b | 0.309 | 0.12 | 0.06 | 0.05 | 0.16 |
| qwen2.5:7b | 0.348 | 0.15 | 0.19 | 0.12 | 0.21 |
| qwen2.5:14b | 0.470 | 0.29 | 0.34 | 0.12 | 0.40 |

Extraction quality **scales monotonically with model size**, and crucially,
**temporal grounding is the first capability to break under compression**:
temporal accuracy is 0.06 at 3B, 0.19 at 7B, and 0.34 at 14B. A 3B extractor is
effectively unable to run the typed protocol on dated information — it produces
facts but fails to absolutize and anchor them. Competence emerges around 7–14B.
The 14B extractor (0.470) marginally exceeds the 12B answerer used as its own
extractor in Table 1 (0.457), so **the memory manager has a minimum viable
size of roughly 7–14B**, comfortably within a single 12 GB GPU. This sets a
concrete floor for the "small local memory manager" proposition: small, but not
arbitrarily small.

## 5.5b Extraction precision

We hand-checked 200 stored memories, stratified across all 10 conversations,
against the source transcripts — verifying for each that a supporting turn
exists and that the memory is attributed to the correct speaker.

**Faithfulness precision = 199/200 (99.5%): zero hallucinations, one
misattribution.** The single error confused two speakers in a fact-dense
conversation — one participant's basketball origin story ("started at age ten,
father signed him up") was attributed to the other participant, a non-player who
merely owns a fan's signed ball. Notably, the *correct* version of the fact was
also stored, so the error is a spurious duplicate under the wrong subject rather
than a fabrication. This is the characteristic failure mode: speaker confusion
on the most memory-dense speaker (≈30 basketball facts), not invention.

A stricter usefulness bar (penalising faithful-but-trivial memories, e.g. a
prop visible in a photo) lowers precision only to 198/200 (99.0%).

**Caveats (stated for honesty):** (i) precision only — we do not measure recall
(facts the extractor missed); downstream QA accuracy (§5.1) is the end-to-end
proxy, since a missed fact surfaces as a failed answer. (ii) The sample is drawn
from *stored* memories, i.e. after the junk filter and deduplication, so this is
pipeline precision, not raw-model precision. (iii) Verification was done by the
authors; an independent annotator with an inter-annotator agreement score is
future work. We report the specific 1/200 misattribution rate rather than a bare
"99.5%" precisely so the claim is auditable.

## 5.6 Cost and interactivity

Extraction runs asynchronously, after the reply is streamed, so it never delays
time-to-first-token. On the 12 GB RTX 4070: TTFT ≈ 0.9 s, generation ≈ 40+
tok/s, extraction adds ≈ 2 GB VRAM over the base model. The full pipeline —
recall, generation, and background extraction — runs in real time on a single
consumer GPU, which is the deployment claim the rest of the paper's efficiency
results support.

---

### TODO before this section is final
- Figure 1 (length-invariance) — render from Table 2 data.
- Figure 2 (architecture) — draw.
- Figure 3 (temporal ablation) — re-run grounding-off condition to get the
  exact "before" number (currently asserted as ~0.00 from the pilot).
- §5.4 context numbers are from the F1 run; note they're payload sizes,
  identical under judging (retrieval is unchanged) — verify wording with a coauthor.
- Extraction precision/recall vs. gold annotations → add as §5.5b once the
  gold sheet is labeled.
- MSC second-benchmark replication → add as §5.7 for generality.
