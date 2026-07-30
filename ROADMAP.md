# Yuna AI — Improvement & Feature Roadmap

Goals, in order: (1) a codebase a stranger can run in 10 minutes, (2) professional
engineering signals (tests, CI, packaging, docs), (3) features that make the
project genuinely usable and demoable, (4) instrumentation the research paper
needs anyway. Bug-level findings live in `IMPROVEMENTS.md`; this is the
architecture + feature plan.

---

## Phase 0 — Foundation refactor (~1 week)

The prerequisite for everything else. No new features, but every later phase
gets cheaper.

### 0.1 Real Python package
- Rename the venv `yuna/` → `.venv/` (it currently squats on the package name).
- Create `src/yuna/` package: `yuna/core/` (config, logging, memory, llm client),
  `yuna/realtime/`, `yuna/reactions/`, `yuna/discord_bot/`, `yuna/dashboard/`.
- `pyproject.toml` with `pip install -e .`; delete every `sys.path.append` hack.
- Console entry points: `yuna chat`, `yuna react <video>`, `yuna studio`,
  `yuna discord`, `yuna dashboard`, `yuna tts "text"`.

### 0.2 Central configuration
- One `config.yaml` (+ `.env` for secrets) loaded via pydantic-settings:
  model names, Ollama/Fish/VTS endpoints, memory thresholds, TTS voices,
  emotion→speed maps, directories.
- Kills the scattered constants: `MODEL` in two files, `FISH_URL`,
  `/usr/local/bin/ollama`, hardcoded voice transcripts (`voices.json` per
  IMPROVEMENTS #8).

### 0.3 Logging
- `logging` + rich console handler replacing raw ANSI prints; per-module loggers;
  `--verbose` / `-q` flags; rotating file log in `logs/`.
- Eliminates every silent `except: pass` (IMPROVEMENTS #3) — errors get logged,
  fatal ones get actionable messages.

### 0.4 Shared LLM/memory utilities
- One `fact_extractor.py` (the duplicated FACT/UPDATE/FORGET prompt + parsing),
  one `history.py` (trim logic), one thin Ollama client wrapper with
  retry/backoff and a startup model check.

---

## Phase 1 — Reliability & professional signals (~1 week)

### 1.1 `yuna doctor` — preflight diagnostics
One command that checks: Ollama reachable + required models pulled, ffmpeg/ffplay
on PATH, VTube Studio API reachable, Fish Speech server up, CUDA visible,
config valid — with a ✅/❌ table and fix hints. This is the single biggest
"usable by strangers" win.

### 1.2 Error-handling policy
- Connection retries with backoff (Ollama, VTS websocket, Fish API).
- VTS auto-reconnect if the websocket drops mid-session (currently the physics
  loop just dies silently).
- Graceful shutdown: track background tasks (memory extraction), drain on exit
  so facts aren't dropped (IMPROVEMENTS #15).

### 1.3 Tests + CI
- pytest for the pure logic: tag parsing/segmentation (`tts.parse_tags`), history
  trimming, emotion blueprint resolution + fuzzy match, fact-extractor output
  parsing, memory dedup thresholds (mocked embeddings), vision timeline merging.
- GitHub Actions: ruff (lint+format) + pytest on push. Badge in README.
- Pre-commit hooks locally.

### 1.4 Repo polish
- `LICENSE` (MIT), `CONTRIBUTING.md`, `CHANGELOG.md`, tagged `v0.1.0` release.
- Pinned dependency lockfile (`uv` or `pip-tools`).
- Demo GIF/video at the top of the README (record with `--test` mode — the
  canned emotion showcase exists exactly for this).
- Root scratch files (`test_*.py`) → `scripts/` or deleted.
- Dashboard security fix: bind localhost, persona as data file not executable
  Python (IMPROVEMENTS #1 — this is the P0).

---

## Phase 2 — Core usability features (~2–3 weeks, highest product value)

### 2.1 Voice input — talk to Yuna, not type 🎤
The single biggest usability leap: mic → VAD (silero-vad) → faster-whisper →
chat loop. Push-to-talk hotkey first (simple, reliable), open-mic with VAD
second. Turns the realtime pipeline into an actual voice companion and makes
every demo 10× better.

### 2.2 Streaming sentence-level TTS ⚡
Today: full LLM response → then TTS → then playback. Change to: as tokens
stream, split on sentence boundaries, synthesize sentence N+1 while sentence N
plays. Cuts time-to-first-audio from "whole response time" to "first sentence
time". Directly measurable → feeds the paper's latency story too.

### 2.3 TTS backend abstraction
One `TTSBackend` interface with `KokoroBackend` (fast, realtime default) and
`FishSpeechBackend` (cloned voice, quality) selectable in config — realtime
Yuna can finally speak with *her* voice when the INT4 server is running, with
Kokoro as automatic fallback if it isn't.

### 2.4 Lip-synced reaction playback
`vts_playback.py` currently plays audio with a frozen avatar (IMPROVEMENTS #9).
Reuse the realtime `play_audio` RMS→`vts_link` path so recorded reactions have
a moving, lip-synced avatar. Combined with 2.5 this completes the content
pipeline.

### 2.5 Reaction video rendering
Final missing stage: composite the source video + Yuna's audio into an actual
output file (ffmpeg overlay layout, or OBS scene + guide for recording), so
`yuna react video.mp4` ends with a shareable artifact instead of a live-only
performance.

---

## Phase 3 — Product & wow features (pick à la carte, post-paper)

- **3.1 Live chat ingestion (Twitch/YouTube):** read chat, select/queue messages,
  respond in voice — the "actual AI VTuber" milestone. Twitch IRC is trivial;
  message selection policy is the interesting part.
- **3.2 Discord voice channels:** Yuna joins a VC and speaks her replies
  (discord.py voice + the TTS backend abstraction from 2.3).
- **3.3 OBS caption overlay:** tiny websocket + browser-source page showing her
  words as she speaks — needed for streaming, great in demos.
- **3.4 Dashboard v2:** live service health (builds on `yuna doctor`), start/stop
  pipelines, streaming logs, TTS test box, memory browser (exists), safe persona
  editor. Auth token + localhost by default.
- **3.5 Memory v2:** episodic session summaries alongside atomic facts, memory
  aging/decay, export/import, `yuna memory` CLI (list/search/forget).
- **3.6 Interruption handling:** stop TTS mid-sentence when the user starts
  talking (needs 2.1 + 2.2) — the feature that makes conversation feel real.

---

## Phase 4 — Research instrumentation (see RESEARCH_PLAN.md)

Shared foundation with the paper: latency metrics (TTFT, time-to-first-audio,
RTF), VRAM sampling, the benchmark harness in `fish-speech-int4-patch/`, INT8
condition flag, `REPRODUCE.md`. Phase 0's config/logging work is a direct
prerequisite, which is why it comes first.

---

## Sequencing vs. the paper timeline

The paper (arXiv by mid-Oct) outranks features. Recommended order:

| Window | Work |
|---|---|
| Late July | Phase 0 (foundation) + 1.4's P0 security fix — one week, serves everything |
| August | Phase 4 paper harness + experiments (critical path), Phase 1 items in gaps |
| September | Paper writing; 2.2 streaming TTS if time (it feeds the paper's latency numbers) |
| October | Preprint out → then Phase 2 features (2.1 voice input first) |
| Nov–Dec | Phase 3 picks + demo video |

## Non-goals (scope control)

- No rewrite in another language/framework; asyncio Python is fine.
- No multi-user/SaaS/auth systems — this is a single-operator tool.
- No custom model training — inference systems engineering is the identity.
- Windows support: document as untested; don't chase it now.
