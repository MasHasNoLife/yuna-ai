# Code Review Findings & Roadmap

Full-project review, 2026-07-07. Ordered by priority. Items marked ✅ were already
applied alongside this review; everything else is a recommendation.

> This file is for internal use — convert entries to GitHub issues or keep it out
> of the public repo if you prefer.

---

## P0 — Security & correctness

### 1. Dashboard allows remote code execution and is exposed to the LAN
[dashboard/server.py:80](dashboard/server.py) — `POST /api/prompt` writes arbitrary
text into `yuna_prompt.py`, which is then **imported and executed as Python** by
every pipeline. Combined with `uvicorn.run(..., host="0.0.0.0")` and no
authentication, anyone on your network can inject code that runs the next time any
Yuna script starts.

**Fix:** bind to `127.0.0.1`; store the persona as plain text/JSON (e.g.
`yuna_prompt.txt`) loaded with `open()` instead of `import`; add a simple bearer
token if LAN access is ever needed. Also drop `reload=True` outside development.

### 2. Vision prompts contain literal `\n` characters
[reactions/vision.py:158-163](reactions/vision.py) — the injected context strings
use `"\\n\\n"` inside normal (non-raw) strings, which produces the two characters
`\` + `n`, not newlines. The model receives `...action.\n\n[AUDIO CONTEXT]...` as
literal backslash-n text. Replace `\\n` with `\n`.

### 3. Errors are silently swallowed project-wide
`except Exception: pass` (sometimes with an unused `e`) appears in
[memory.py](memory.py) (save/search/delete), [realtime/yuna.py:157](realtime/yuna.py),
[realtime/vts_link.py:171](realtime/vts_link.py), and
[discord/discord_bot.py:117](discord/discord_bot.py). A dead Ollama embedding
endpoint means memory writes silently no-op forever. Add a `logging` setup and log
at least at debug/warning level in every handler.

### 4. requirements.txt was missing over half the real dependencies ✅
`chromadb`, `discord.py`, `python-dotenv`, `aiohttp`, `emoji`, `Pillow`, `httpx`,
`torch`, `fastapi`, `uvicorn`, `numpy` were all imported but not listed. Fixed —
`requirements.txt` now covers every import, grouped by module.

### 5. Binary media committed to git
`reactions/reference_videos/1.mp4` and `2.mp4` plus generated
`reactions/reactions_scripts/*.txt` are tracked. Repo is still small (13 MB), but
every future reference video would bloat it. `.gitignore` now covers these paths ✅;
to untrack the existing files run:

```bash
git rm -r --cached reactions/reference_videos reactions/reactions_scripts
git commit -m "chore: stop tracking reference videos and generated scripts"
```

Also: root `vts_link.py` is still tracked but superseded by
`realtime/vts_link.py` (it's deleted in your working tree — commit the deletion).

---

## P1 — Architecture & maintainability

### 6. Duplicated memory-extraction logic
The ~40-line fact-extractor prompt and the `trim_history()` helper are copy-pasted
between [realtime/yuna.py:98](realtime/yuna.py) and
[discord/discord_bot.py:51](discord/discord_bot.py), and have already drifted
(the Discord version has extra rules 1–3). Extract into a shared
`memory_extractor.py` next to `memory.py`.

### 7. Configuration is scattered and hardcoded
Model names (`qwen2.5:14b` in two files, `gemma2:27b`, `llava:13b`, `minicpm-v`),
the Ollama binary path (`/usr/local/bin/ollama` in
[reactions/run_all.py:11](reactions/run_all.py) — use `shutil.which("ollama")`),
the Fish Speech URL, thresholds, and voice choices are all inline constants.
A single `config.py` (or extending `.env`) would make model swaps one-line changes
— and it's the file reviewers look for.

### 8. Voice reference transcripts managed by comment-swapping
[reactions/render_audio.py:18-28](reactions/render_audio.py) — switching Yuna's
voice means commenting/uncommenting `YUNA_TRANSCRIPT` blocks and editing the wav
path. Move to `voice_reference/voices.json` mapping
`{voice_id: {wav, transcript}}` and pick with a `--voice` flag.

### 9. Reaction playback doesn't actually drive the avatar
[reactions/vts_playback.py](reactions/vts_playback.py) is named "VTS playback" but
never touches VTube Studio — it only plays wav files. The realtime pipeline already
has everything needed ([realtime/tts.py](realtime/tts.py) `play_audio()` feeds RMS
into `vts_link.set_audio_level`). Reusing it would give lip-synced avatar recording
for reaction videos — this is also the biggest visible feature win.

### 10. `sys.path.append` hacks instead of a package
Every entry point does `sys.path.append(dirname(dirname(...)))`. Add a minimal
`pyproject.toml` and make the project an installable package (`pip install -e .`),
then use real imports. Note the venv is currently named `yuna/` inside the repo —
rename it to `.venv/` to avoid colliding with a future `yuna` package name.

### 11. Stale comments that contradict the code
[discord/discord_bot.py:22-24](discord/discord_bot.py): "Using massive 27B model"
above `MODEL = "qwen2.5:14b"`, and "Remembers the last 20 full conversational
exchanges" above `MAX_HISTORY = 40` (messages, not exchanges). Small, but they're
the first thing a reviewer sees.

---

## P2 — Polish & portfolio value

### 12. No LICENSE file
GitHub shows "no license" prominently and legally nobody can reuse the code. For a
portfolio repo, MIT is the usual choice — add `LICENSE` with your name.

### 13. No tests or CI
Even a minimal GitHub Actions workflow running `ruff` + a couple of pure-function
tests (e.g. `tts.parse_tags`, `trim_history`, the tag→segment splitter) gives you a
green checkmark badge and signals engineering discipline cheaply. The tag parsing
and history trimming are ideal first targets since they need no GPU.

### 14. Root-level scratch files
`test_ollama_img.py`, `test_req.py`, `test_extract.py`, `test_vision.py` are
one-off experiments at the repo root. Move keepers into `scripts/` or a real
`tests/`, delete the rest. Also: `dashboard/` is untracked — commit it (the
`server.log` inside is now gitignored ✅).

### 15. Fire-and-forget tasks can die on exit
Memory extraction runs via `asyncio.create_task()` with no reference kept
([realtime/yuna.py:270](realtime/yuna.py),
[discord/discord_bot.py:180](discord/discord_bot.py)). Tasks can be
garbage-collected mid-flight or cancelled at shutdown, silently dropping facts.
Keep a task set and `await asyncio.gather(*pending)` before exiting.

### 16. First TTS response pays the model-load cost
Kokoro initializes lazily inside `synthesize()`. When `--tts` is passed, preload
the pipeline during startup so the first reply isn't noticeably slower.

### 17. Discord: per-request aiohttp sessions and mid-function imports
[discord/discord_bot.py:225,276](discord/discord_bot.py) — `import emoji` /
`import aiohttp` happen inside handlers, and a new `ClientSession` is created per
URL. Move imports to the top and share one session for the bot's lifetime.

### 18. README was stale ✅
The old README described Kokoro as the only TTS, Llama 3.1 as the chat model, and
`/react`, `/video` commands that no longer exist. Rewritten to match the actual
codebase (realtime + reactions + Discord + dashboard + INT4 fork).

---

## Applied in this pass ✅

- `README.md` — full portfolio-grade rewrite (architecture diagram, model stack,
  per-pipeline docs, setup guide)
- `requirements.txt` — all real dependencies, grouped by module
- `.env.example` — documented Discord env vars
- `.gitignore` — added `.venv/`, `*.log`, `reactions/voicetts/`,
  `reactions/reference_videos/`, `reactions/reactions_scripts/`
- `IMPROVEMENTS.md` — this file
