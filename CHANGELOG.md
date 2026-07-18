# Changelog

## v0.2.0 — 2026-07

The web interface release: everything comes together in the browser.

### Added
- `yuna web` — a single-page web app with streaming WebSocket chat, emotion
  chips, recalled-memory footnotes, real-time PCM voice playback with a
  waveform visualizer, and push-to-talk voice input (faster-whisper on CPU)
- Pluggable LLM backends (`core/llm_backends.py`): local Ollama (primary) and
  the Google AI API (secondary), switchable live from the UI; Gemma "thought"
  parts are routed to the monitoring feed, never spoken
- Pluggable TTS backends (`tts/`): Kokoro local, Fish Audio cloud (streaming),
  and the local INT4 Fish Speech server
- `ChatSession` (`core/chat_session.py`) — one conversation engine shared by
  the web UI and CLI: history, memory recall, background FACT/UPDATE/FORGET
  extraction, typed streaming events
- Monitoring (`core/metrics.py`): per-turn TTFT, tok/s, time-to-first-audio,
  recall latency, and memory-op counts — surfaced in the terminal, in
  `data/logs/events.jsonl`, and in the web UI's System tab (which also shows
  `yuna doctor` health checks as JSON via `/api/health`)
- Live memory panel: extraction feed + browse/filter/add/delete on the vector
  store; persona editor (plain text) absorbed from the old dashboard

### Changed
- The old read-only dashboard is replaced by the web interface
  (`yuna dashboard` remains as an alias for `yuna web`)
- Research plan pivoted from INT4 TTS quantization to agentic RAG memory with
  small local models (see RESEARCH_PLAN.md)
- `.env` is now loaded by the CLI for every command

## v0.1.0 — 2026-07

First versioned release: full restructure into an installable package.

### Added
- `yuna` CLI with subcommands: `chat`, `studio`, `tts`, `react`, `react-text`,
  `discord`, `dashboard`, `doctor`
- `yuna doctor` preflight diagnostics (Ollama + models, ffmpeg, VTube Studio,
  Fish Speech, CUDA, persona, secrets) with actionable hints
- Central `config.yaml` for models, endpoints, thresholds, and paths
- Structured logging (rich console + rotating file in `data/logs/`) replacing
  silent `except: pass` error handling
- VTube Studio auto-reconnect when the websocket drops mid-session
- Graceful shutdown that drains background memory-extraction tasks
- Lip-synced reaction playback (`yuna react --studio`)
- Voice references configured in `voice_reference/voices.json` instead of
  hardcoded transcripts
- Test suite for the pure logic (tags, history, emotions, fact extraction,
  timeline, config) + GitHub Actions CI (ruff + pytest)
- MIT license

### Changed
- All code moved into `src/yuna/` (installable package, `pip install -e .`);
  `sys.path` hacks removed
- Persona is now plain-text data in `persona/` (gitignored, with a tracked
  `persona.example/`) instead of importable Python — this also fixes the
  dashboard's remote-code-execution editor endpoint
- Dashboard binds to 127.0.0.1 by default with optional bearer-token auth
- Memory extraction prompt/parsing deduplicated between realtime and Discord
- All runtime data consolidated under `data/` (memory DBs, responses,
  reaction outputs, VTS token, logs)
- Reaction pipeline stages pass output paths explicitly instead of parsing
  each other's stdout
- Fixed: vision prompts contained literal `\n` characters instead of newlines

### Removed
- Root-level scratch scripts (superseded by `tests/` and `yuna doctor`)
- Old per-directory entry points (`realtime/yuna.py`, `reactions/run_all.py`, ...)
