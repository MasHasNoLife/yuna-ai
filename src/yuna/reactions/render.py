"""Reaction stage 3: script -> per-line wav files via the local Fish Speech
server (voice-cloned). Voice references are configured in
voice_reference/voices.json, not hardcoded.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from yuna.core.config import get_config
from yuna.core.logging import get_logger, setup_logging
from yuna.reactions.timeline import extract_dialogue_lines

log = get_logger("reactions.render")


def load_voice(voice_id: str | None = None) -> tuple[str, Path, str]:
    """(voice_id, wav_path, transcript) from voice_reference/voices.json."""
    cfg = get_config()
    voice_id = voice_id or cfg.tts.fish_voice
    voices_file = cfg.paths.voice_reference / "voices.json"
    if not voices_file.exists():
        raise FileNotFoundError(
            f"{voices_file} not found. Copy voices.example.json and fill in your "
            f"reference wav + transcript for each voice."
        )
    voices = json.loads(voices_file.read_text(encoding="utf-8"))
    if voice_id not in voices:
        raise KeyError(f"Voice '{voice_id}' not in {voices_file} (has: {list(voices)})")
    entry = voices[voice_id]
    wav = cfg.paths.voice_reference / entry["file"]
    if not wav.exists():
        raise FileNotFoundError(f"Reference audio missing: {wav}")
    return voice_id, wav, entry["transcript"]


def ensure_voice_registered(voice_id: str, wav: Path, transcript: str) -> bool:
    """Upload the reference voice to Fish Speech if it isn't registered yet."""
    fish = get_config().endpoints.fish_url
    try:
        r = httpx.get(f"{fish}/audio/voices", timeout=300.0)
        if r.status_code == 200 and voice_id in r.json().get("voices", []):
            log.info("Voice '%s' already registered", voice_id)
            return True
    except Exception as e:
        log.error("Could not connect to Fish Speech API at %s: %s", fish, e)
        return False

    log.info("Registering voice '%s'...", voice_id)
    try:
        files = {"audio": (f"{voice_id}_reference.wav", wav.read_bytes(), "audio/wav")}
        data = {"id": voice_id, "text": transcript}
        r = httpx.post(f"{fish}/references/add", data=data, files=files, timeout=60.0)
        if r.status_code in (200, 409):
            log.info("Voice registered")
            return True
        log.error("Failed to register voice: %s", r.text)
        return False
    except Exception:
        log.exception("Failed to upload reference voice")
        return False


def render_line(text: str, voice_id: str, output_path: Path) -> bool:
    """Render one line through the OpenAI-compatible speech endpoint."""
    cfg = get_config()
    log.info("Rendering: %s...", text[:50])
    payload = {
        "model": cfg.tts.fish_model,
        "input": text,
        "voice": voice_id,
        "response_format": "wav",
    }
    try:
        r = httpx.post(f"{cfg.endpoints.fish_url}/audio/speech", json=payload, timeout=300.0)
        if r.status_code == 200:
            output_path.write_bytes(r.content)
            return True
        log.error("Rendering failed: %s", r.text)
        return False
    except Exception:
        log.exception("Request failed")
        return False


def run(script: str, out_dir: Path | None = None, voice: str | None = None) -> Path:
    """Render every dialogue line of a reaction script. Returns the run directory."""
    cfg = get_config()
    script_path = Path(script)
    if not script_path.is_file():
        script_path = cfg.paths.scripts / script
    if not script_path.is_file():
        raise FileNotFoundError(f"Reaction script not found: {script}")

    voice_id, wav, transcript = load_voice(voice)
    if not ensure_voice_registered(voice_id, wav, transcript):
        raise ConnectionError("Cannot render without the reference voice registered")

    if out_dir is None:
        base_name = script_path.stem.removesuffix("_reaction")
        cfg.paths.reaction_audio.mkdir(parents=True, exist_ok=True)
        counter = 1
        out_dir = cfg.paths.reaction_audio / f"{base_name}_run{counter}"
        while out_dir.exists():
            counter += 1
            out_dir = cfg.paths.reaction_audio / f"{base_name}_run{counter}"
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = extract_dialogue_lines(script_path.read_text(encoding="utf-8"))
    log.info("Rendering %d lines of dialogue to %s", len(lines), out_dir)

    rendered = 0
    for i, line in enumerate(lines):
        out_path = out_dir / f"{i + 1:03d}.wav"
        if render_line(line, voice_id, out_path):
            rendered += 1
    log.info("Done: %d/%d lines rendered", rendered, len(lines))
    if rendered == 0:
        raise RuntimeError("No lines rendered — is the Fish Speech server running?")
    return out_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render a reaction script to audio")
    parser.add_argument("script", help="script path, or filename inside data/reactions/scripts/")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--voice", default=None, help="voice id from voices.json")
    args = parser.parse_args(argv)

    setup_logging()
    try:
        out = run(args.script, args.out_dir, args.voice)
        print(out)
        return 0
    except Exception as e:
        log.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
