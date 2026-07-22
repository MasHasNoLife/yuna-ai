# Abstract (draft)

Conversational agents forget: once a dialogue outgrows the context window, a
model must either be reminded through retrieval or have its history truncated.
Recent memory systems address this with extraction and retrieval, but they
assume a large, often API-hosted model as the memory manager — an assumption
that rules out private, local deployment. We ask whether a *small local* model,
on a single consumer GPU, can manage long-term memory well, and how the answer
depends on model size. We evaluate four memory strategies — no memory, full-
history stuffing, raw-turn retrieval, and an agentic protocol that extracts
typed, dated, deduplicated facts — on LoCoMo (1,986 questions over 10 long
multi-session conversations), scored by an independent LLM judge. Full-context
stuffing wins aggregate accuracy when the answer still lies inside the window,
but its advantage is an artifact of conversation length: split by whether a
question's evidence survives truncation, stuffing collapses by 76% beyond the
window while agentic memory stays flat, outperforming stuffing 2.0× on the third
of questions that already exceed it. Agentic memory further gives the best
temporal reasoning of any strategy (via absolute-date grounding at write time)
using ~67× less context. Varying the extractor from 3B to 14B, we find quality
scales with size and that temporal grounding is the first capability to break
under compression, setting a minimum viable memory-manager size of ~7–14B —
comfortably within a 12 GB GPU. We release the system and benchmark harness.

---

# 1. Introduction (draft)

A conversational agent that cannot remember is not a companion; it is a
sequence of strangers. Yet remembering is bounded by the context window: a model
can only attend to what fits, and a relationship that spans weeks does not fit.
The standard response is retrieval-augmented memory — extract what matters, store
it, retrieve it on demand — and a growing line of work (MemGPT, Mem0, Generative
Agents) has shown this can give agents durable, useful memory.

That work shares an assumption we want to remove: **the memory manager is a
large, capable model**, usually reached through an API. For a companion that
runs on a user's own machine — private, offline, always-available — this is
exactly the wrong dependency. The open question is not whether memory helps (it
does), but whether the *management* of memory — deciding what to store, how to
date it, when to update or forget — can be done by a small model on consumer
hardware, and if so, how small.

We study this concretely on a single 12 GB GPU, with the chat model held fixed
and only the memory pathway varied. We compare an **agentic** memory protocol —
which extracts typed facts (durable facts, dated events, the agent's own
self-facts), absolutizes relative dates at write time, deduplicates on insert,
and retrieves age-aware — against three baselines: no memory, stuffing the full
transcript into the window, and retrieving raw dialogue turns without extraction.

Our findings reframe how these strategies should be compared. Judged on
aggregate accuracy, full-history stuffing wins — but we show this win is
**contingent on conversation length**. Splitting questions by whether their
evidence still fits in the window, stuffing's accuracy collapses 76% once the
evidence is truncated, while retrieval-based memory is **length-invariant**,
and overtakes stuffing 2.0× in exactly the long-conversation regime a persistent
companion lives in. Separately, extracting and *dating* memories at write time
yields the best temporal reasoning of any strategy, at ~67× less context — the
result that makes local deployment practical. Finally, sweeping the extractor
from 3B to 14B, we find a **minimum viable size**: below ~7B the typed protocol
fails, and temporal grounding is the first thing lost.

**Contributions.**
1. A reproducible benchmark of an agentic FACT/EVENT/SELF/UPDATE/FORGET memory
   protocol against no-memory, full-history, and raw-retrieval baselines, judged
   and released with raw outputs.
2. The **length-invariance** result: context-stuffing's accuracy advantage
   expires as conversations grow, while retrieval-based memory does not — with a
   direct measurement of the crossover.
3. An answer to **how small the memory manager can be** (≈7–14B), identifying
   temporal grounding as the capability that breaks first under compression.
4. An open-source system running the full recall–generate–extract loop in real
   time on a single 12 GB consumer GPU.

---

### Notes for revision
- Opening line ("sequence of strangers") is a stylistic bet — keep only if a
  coauthor agrees it lands; safe fallback: plain problem statement.
- Abstract numbers must match final judged tables exactly on last pass.
- Fill MemGPT/Mem0/Generative Agents citations once §2 is verified.
- Consider moving the temporal result ahead of length-invariance if reviewers
  read temporal as the more novel mechanism; current order leads with the
  strongest (length-invariance).
