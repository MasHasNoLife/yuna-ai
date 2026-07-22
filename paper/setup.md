# 4. Experimental Setup

## 4.1 Benchmark

We evaluate on **LoCoMo** (Maharana et al., 2024), the standard benchmark for
very long-term conversational memory: 10 multi-session conversations between two
speakers (≈4,000 turns total across up to 30+ sessions each, spanning simulated
weeks to months), each with a QA set probing recall over the full history. The
1,986 questions are labelled into five categories: **multi-hop** (reasoning over
several facts), **temporal** (dates, ordering, durations), **open-domain**,
**single-hop** (one fact, often verbatim), and **adversarial** (unanswerable —
the correct response is to decline).

Image-only turns are represented by their captions. To keep the QA fair under
partial ingestion, a question is only asked when the evidence it depends on
falls within the ingested sessions; adversarial questions, which have no
evidence, are always asked. We plan a second benchmark, **MSC** (Multi-Session
Chat), to test persona consistency and generalise the findings beyond LoCoMo.

## 4.2 Conditions

- **Memory strategy** (§3.6): none / full_history / raw_rag / agentic.
- **Extractor model** (RQ1): qwen2.5 at 3B, 7B, and 14B, to test how small the
  memory manager can be.
- **Chat/answerer model held fixed:** Gemma4-12B-QAT (Q4_K_M) throughout, so all
  differences are attributable to the memory pathway rather than the responder.
  In the strategy experiment the same model also performs extraction; in the
  ladder experiment the extractor is varied while the answerer stays fixed,
  cleanly isolating extraction quality.

Each (conversation, condition) pair gets a fresh vector store, so runs are
independent and reproducible.

## 4.3 Metrics

- **Token-F1 and exact match** (SQuAD-style normalisation): fast, deterministic
  first-pass scoring.
- **Abstain-aware scoring for the adversarial category.** A correct answer to an
  unanswerable question is a refusal, which token overlap cannot credit against
  varied gold phrasings of "no answer"; we instead detect abstention directly.
  Because a memory-less model abstains on everything, this category lifts every
  strategy's floor, so we report it separately rather than folding it into a
  single headline number.
- **LLM-as-judge** (primary): an independent model (qwen2.5-14b, temperature 0)
  grades each prediction against the gold answer as correct/incorrect, crediting
  rephrasings and partial-date matches that token-F1 penalises. The judge differs
  from the answerer; any judge bias applies uniformly across conditions, since
  every strategy's answers face the same judge. The adversarial category remains
  scored deterministically by abstention.
- **Extraction precision/recall** (RQ, pending): a hand-annotated gold set of
  ~200 sampled extraction operations, labelled for faithfulness, attribution,
  and usefulness, to measure the quality of what the extractor stores
  independently of downstream QA.
- **Cost:** time-to-first-token, generation throughput, and peak VRAM, emitted
  per turn by the system's own instrumentation.

Judge prompts, seeds, and raw per-question outputs are published with the repo.

## 4.4 Implementation and hardware

All models run locally through **Ollama**; memories are stored in **ChromaDB**
with **nomic-embed-text** embeddings. Sampling for the chat model: temperature
0.8, top-p 0.9, repeat-penalty 1.15, context window 8192 tokens. The chat model
runs with hidden "thinking" tokens disabled (the Gemma-4 family otherwise emits
several seconds of silent reasoning per turn, harming interactivity without
improving these tasks). full_history uses a 16k-token window to accommodate the
stuffed transcript.

All experiments run on a **single NVIDIA RTX 4070 (12 GB)**. The chat model is
7.6 GB quantised, leaving headroom for the KV cache and the embedding model; TTS
and other auxiliary components are kept off the GPU so the language models are
not starved of VRAM. This hardware — a mid-range consumer card — is the point:
the entire persistent-memory pipeline is designed to run on what an enthusiast
already owns, with no cloud dependency.
