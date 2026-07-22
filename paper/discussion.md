# 6. Discussion and Limitations

## 6.1 What the results do and do not claim

We do **not** claim agentic memory is universally superior at recall. On our
main benchmark, full-context stuffing achieves the highest overall judged
accuracy (§5.1), because when the answer to a question sits verbatim inside the
context window, providing the raw text beats providing a distilled summary of
it. Our claims are narrower and, we argue, more consequential for real
deployment:

1. **Temporal reasoning.** Distilling and *dating* memories at write time beats
   date arithmetic over raw text (§5.2).
2. **Length-invariance.** Retrieval-based memory is indifferent to conversation
   length, whereas context-stuffing degrades sharply once the conversation
   outgrows the window (§5.3). full_history's overall win is contingent on the
   answer surviving truncation; agentic memory has no such dependency.
3. **Efficiency.** Competitive accuracy at ~67× less context, within a 4k-token
   window on a 12 GB GPU (§5.4).

The length-invariance result reframes the overall-accuracy comparison. A
benchmark is a snapshot at one conversation length; a *companion* accumulates
history indefinitely. As the truncated fraction of relevant history approaches
100%, full_history trends toward its truncated-region floor (§5.3, 0.163) while
agentic memory holds constant (0.330). The regime where stuffing wins is
precisely the regime a persistent agent grows out of.

## 6.2 Where agentic memory loses, and why

full_history's advantage is concentrated in single-hop (0.66 vs. 0.35) and
multi-hop (0.39 vs. 0.31) questions whose evidence remains in-window. Two causes:
(i) extraction is lossy — a distilled fact can omit a detail the raw turn
preserved; (ii) multi-hop questions may require facts the extractor stored
separately but that were never retrieved together. This motivates a
**consolidation pass** (§6.4) that periodically merges related memories and
surfaces facts implied across several stored items but never stated as one — a
gap we observed qualitatively in the extraction output.

## 6.3 Threats to validity

- **Judge bias.** LLM-as-judge can favour certain phrasings. We mitigate this by
  using a judge distinct from the answerer and by scoring the adversarial
  category deterministically; any residual bias applies uniformly across
  conditions, since all are judged identically. Token-F1 is reported alongside
  as a deterministic cross-check.
- **The abstain floor.** Abstain-aware scoring credits a memory-less model for
  correctly declining unanswerable questions, so category 5 inflates every
  strategy's aggregate. We therefore report it separately and read the
  discriminating signal from the other four categories.
- **Single benchmark, single answerer.** Results are on LoCoMo with one fixed
  chat model; MSC replication (planned) and additional answerers would
  strengthen generality.
- **Extraction cost at ingest.** Building agentic memory is a per-exchange model
  call — offline and one-time, and asynchronous at chat time (§3.5), but not
  free. The extractor ladder (§5.5) quantifies the quality one buys per
  parameter.

## 6.4 Future work

- **Consolidation / maintenance.** A periodic pass to merge near-duplicates and
  materialise implied facts — the natural remedy for the single-hop and
  multi-hop gaps, and a further "agentic maintenance" contribution.
- **MSC and persona consistency.** A second benchmark measuring long-horizon
  persona stability, not just factual recall.
- **Extraction precision.** Completing the gold-annotation evaluation (§4.3) to
  characterise *what* the extractor stores, decoupled from downstream QA.
- **Persona distillation.** Fine-tuning the chat model on curated in-character
  dialogue to reduce assistant-like behaviour that prompting only partly
  suppresses — orthogonal to the memory contribution, and a candidate for
  separate work.
