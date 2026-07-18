# Research Paper Plan — INT4 Expressive TTS on Consumer GPUs

Target: arXiv preprint by **mid-October 2026**, conference/workshop submission after,
citable in fall 2027 Masters applications (EM LCT, Sweden, Finland, Saarland, DTU).

---

## 1. The paper

**Working title:** *"4-bit Voice Cloning: NF4 Quantization of Expressive TTS for
Consumer GPUs"*

**Research questions:**

- **RQ1 (quality):** How much does NF4 4-bit quantization degrade intelligibility,
  speaker similarity, and perceived quality of a voice-cloning TTS model
  (Fish Speech S2-pro) versus FP16 and 8-bit baselines?
- **RQ2 (efficiency):** What are the gains in VRAM footprint, real-time factor
  (RTF), and time-to-first-audio?
- **RQ3 (system):** Does the quantized model enable a full local conversational
  agent (LLM + TTS + avatar) to run interactively within 12 GB — and what
  orchestration does that require? *(short case-study section, not the core)*

**Contributions:**
1. An open-source NF4 quantization patch for Fish Speech with export/reload of
   quantized checkpoints (already built — `fish-speech-int4-patch/`).
2. A systematic quality/efficiency evaluation across quantization levels on a
   single RTX 3060, with a reproducible benchmark harness.
3. A case study: VRAM orchestration for a fully local multimodal agent (Yuna).

**Why this angle wins:** the quantization work already exists and produces *hard
numbers* (no user-study logistics required for the core claims), it fits speech
venues that accept solo empirical work, and "local/private AI on consumer
hardware" is a currently fashionable framing.

---

## 2. Experimental design

**Conditions (the independent variable):**

| Condition | Notes |
|---|---|
| FP16 / BF16 | baseline — measure whether it even fits alongside an LLM in 12 GB |
| INT8 (bitsandbytes LLM.int8) | mid-point — needs a flag added to the server |
| NF4 (bnb4) | the contribution — already implemented |
| NF4 + double quantization | optional extra point on the curve |

**Metrics (the dependent variables):**

| Axis | Metric | Tool |
|---|---|---|
| Intelligibility | WER / CER via ASR round-trip | Whisper large-v3 as judge (extend existing `tools/correlate_with_whisper.py`) |
| Speaker fidelity | speaker-embedding cosine similarity (reference vs. output) | ECAPA-TDNN (speechbrain) or Resemblyzer |
| Perceived quality | UTMOS automatic MOS prediction | `speechmos` / UTMOS22 |
| Perceived quality (optional) | small human MOS study, N≥15 | Discord community, simple A/B web page |
| Speed | RTF, time-to-first-audio (p50/p95) | extend existing `tools/rtf_benchmark.py` |
| Memory | peak + steady-state VRAM | pynvml sampling thread |

**Test material:**
- ~100 fixed sentences: Harvard sentences + a set of emotion-tagged sentences from
  the Yuna corpus (tests the expressive/tag-driven angle).
- 3 runs per condition with fixed seeds; report mean ± std.
- English + Spanish (the fork already has Spanish autodetection — free second
  language axis and it uses existing `fish_corr_es.json` infrastructure).

**Voices — ETHICS, non-negotiable:**
- ❌ The current `voice_reference/` clips (game/anime voice actors) must NOT be
  used in anything published.
- ✅ Use: (a) your own recorded voice (10–30 s clean reference), and
  (b) 3–5 speakers from VCTK or LibriTTS (open licenses, standard in TTS papers).
- The paper needs an ethics statement covering voice-cloning misuse; using
  consented/open voices is what makes it writable.

---

## 3. Engineering work (in this repo / the fork)

Ordered; items 1–4 are the critical path.

1. **Benchmark harness** — one config-driven script: spins up the server in each
   quantization mode, runs the full sentence set, collects all metrics into JSON,
   generates the tables/plots for the paper. No manual steps.
2. **Instrumentation** — time-to-first-audio and RTF per request, VRAM sampler
   (pynvml), latency percentiles. Add to the fork's server.
3. **INT8 condition** — add a `--bnb8` path next to the existing `--bnb4` so the
   comparison isn't just FP16-vs-NF4.
4. **Metric runners** — WER round-trip (extend `correlate_with_whisper.py`),
   speaker-similarity script, UTMOS script.
5. **Reproducibility** — pinned `requirements.txt` for the eval environment,
   fixed seeds, a `REPRODUCE.md`, ideally a Dockerfile.
6. **Repo hygiene** — fix IMPROVEMENTS.md P0 items (reviewers and professors will
   open the repo), add CI badge.
7. **Upstream PR** — open the NF4 patch as a PR to `fishaudio/fish-speech`.
   Independent CV value even if it stalls in review.

---

## 4. Related work to read (for §2 of the paper)

- **Quantization:** LLM.int8, GPTQ, AWQ, QLoRA/NF4 (Dettmers et al.), SmoothQuant.
- **Efficient/on-device TTS:** Kokoro-82M notes, VITS variants, distillation work,
  any published Fish Speech / codec-LM TTS papers (grounds the architecture).
- **Quantized speech models:** existing work on quantizing Whisper/codec models —
  establishes what's known and what your gap is (quantizing *voice-cloning
  autoregressive TTS* end-to-end on consumer HW).
- **Embodied conversational agents:** IVA/SIGDIAL systems papers, for the case
  study section.

~15 papers, skim-read in week 2–3. Zotero or a `references.bib` from day one.

---

## 5. Venues & timeline

| When (2026) | Milestone |
|---|---|
| Jul 16 – Jul 31 | Harness + instrumentation built; INT8 flag; consented voices recorded; sentence set frozen |
| Aug 1 – Aug 15 | Pilot run end-to-end (1 seed, all conditions); related-work reading; **supervisor outreach emails go out** |
| Aug 16 – Sep 15 | Full experiment matrix (3 seeds × 4 conditions × 2 languages); draft intro/method |
| Sep | **ICASSP 2027 deadline (~mid-Sep — verify!)** — submit if results are in; it's the best-fit venue (speech + efficiency, 4-page format) |
| Sep 16 – Oct 10 | Full draft; optional human MOS; supervisor feedback round |
| Mid–late Oct | **arXiv preprint live** — this is the hard deadline; it gets cited in every SOP |
| Nov–Dec | Workshop submissions (NeurIPS/ICML workshops on efficient ML — verify calls); applications season starts |
| Feb–Mar 2027 | **Interspeech 2027** submission as the second/backup venue — acceptance news (~June) can still be forwarded to universities before enrollment |

Fallback logic: even if every peer-reviewed venue rejects, the arXiv preprint +
public benchmark repo + upstream PR is the portfolio. Peer review acceptance is
upside, not the foundation.

---

## 6. Supervisor / co-author outreach (do not skip)

The paper's biggest application value is converting into a **recommendation
letter from an academic**. In parallel with week 3–4:

- Shortlist 5–10 targets: speech/NLP faculty at local universities + authors of
  the efficient-TTS papers you cite + LCT-consortium-adjacent researchers
  (Saarland, Groningen — strategic overlap with your applications).
- Email = 5 sentences + repo link + benchmark report PDF. Ask for feedback and
  mention openness to collaboration/supervision. Attach nothing bigger than 1 page.
- Best case: co-author + letter. Good case: feedback + letter. Even silence
  costs nothing.

---

## 7. Definition of done

- [ ] Benchmark harness runs all conditions unattended and outputs paper-ready tables
- [ ] Results: quality (WER, speaker-sim, UTMOS) and efficiency (RTF, TTFA, VRAM) across FP16/INT8/NF4, EN+ES, 3 seeds
- [ ] Consented voices only; ethics statement written
- [ ] 4–5 page paper (ICASSP/Interspeech format) + arXiv preprint live
- [ ] Upstream PR opened to fishaudio/fish-speech
- [ ] At least one academic has read it and agreed to write a letter
- [ ] Repo: P0 fixes done, REPRODUCE.md, CI green
