# 2. Related Work — SKELETON (citations & specifics require verification)

> ⚠️ This is a scaffold, not finished prose. Every paper below is real and
> relevant, but exact claims, dates, numbers, and venue details MUST be checked
> against the source before this goes in the paper. Do NOT trust any specific
> figure or quote written here — none are filled in for that reason. Build
> references.bib as each is verified; replace each ⟨verify⟩ with a checked claim.

The section makes one argument: memory for LLM agents is an active area, but the
existing systems assume a large (often API-hosted) model as the memory manager,
and the long-conversation benchmarks are scored in ways that miss the
length-dependence we highlight. Our gap: **a small, local memory manager on
consumer hardware, evaluated for length-invariance.**

## 2.1 Agent memory systems
- **MemGPT** (Packer et al.) — OS-inspired tiered memory / virtual context
  paging for LLMs. ⟨verify: mechanism, model used⟩. Contrast: assumes a strong
  controller model; we ask how small the controller can be.
- **Mem0** — extraction-based memory layer for agents. ⟨verify: extraction
  approach, whether local or API⟩. Closest in spirit to our typed protocol;
  contrast on the small-local-model constraint and the length-invariance eval.
- **Generative Agents** (Park et al.) — memory stream + retrieval scored by
  recency/importance/relevance + reflection. ⟨verify: scoring formula, model⟩.
  Our age-aware retrieval and consolidation (future work) relate here.
- **Reflexion; LongMem; RecurrentGPT** — reflection / long-context augmentation
  lines. ⟨verify each contribution⟩. Position as complementary, not memory-store
  competitors.

## 2.2 Long-conversation benchmarks
- **LoCoMo** (Maharana et al., 2024) — our primary benchmark. ⟨verify: exact
  size, category definitions, original metrics⟩. Note we add abstain-aware +
  judged scoring and the length-invariance split.
- **MSC / Multi-Session Chat** (Xu et al.) — persona consistency over sessions;
  our planned second benchmark. ⟨verify⟩.
- **MemoryBank; PerLTQA** — other long-term memory QA sets. ⟨verify; justify why
  we chose LoCoMo(+MSC)⟩.

## 2.3 Retrieval-augmented generation
- **RAG** (Lewis et al.) — foundational retrieve-then-generate. ⟨verify⟩.
- **Self-RAG** — retrieval with self-critique/gating. ⟨verify⟩. Relates to our
  agentic write-time decisions (what is worth storing).
- Dialogue-memory retrieval (e.g. BlenderBot 2/3 memory). ⟨verify⟩.

## 2.4 Small-model capability
- Work on the capability gap between small open models and frontier APIs, and on
  quantisation quality. ⟨verify specific refs⟩. Grounds the framing question:
  "can a 3B–14B model do the memory-management job?" — which §5.5 answers with a
  floor of ~7–14B.

## Positioning sentence (for the intro too)
Unlike prior memory systems, which assume a capable (often API) model as the
memory manager and report aggregate accuracy at a fixed length, we (i) constrain
the manager to a small *local* model and quantify the minimum viable size, and
(ii) evaluate *length-invariance* directly, showing where retrieval-based memory
overtakes context-stuffing as conversations grow.

---

### Reading checklist (wk-1/2 of the compressed timeline)
- [ ] MemGPT — mechanism, controller model, what it stores
- [ ] Mem0 — extraction method, local vs API, dedup/update handling
- [ ] Generative Agents — retrieval scoring, reflection, consolidation
- [ ] LoCoMo — original metrics + category defs (to state what we changed)
- [ ] MSC — setup, persona-consistency metric
- [ ] RAG, Self-RAG — one sentence each, precise contribution
- [ ] 2–3 small-model / quantisation references
- Target: ~15 papers, 2–3 sentences each, each ending in "unlike them, we …".
