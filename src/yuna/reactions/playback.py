"""Reaction stage 4: play rendered lines in sequence.

With --studio, connects to VTube Studio first so playback drives the avatar's
lip-sync and body bounce (reuses the realtime RMS pipeline).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from yuna.core.config import get_config
from yuna.core.logging import get_logger, setup_logging
from yuna.reactions.timeline import extract_dialogue_lines
from yuna.realtime import vts_link
from yuna.realtime.tts import play_audio

log = get_logger("reactions.playback")


def _find_audio_dir(base_name: str) -> Path | None:
    """Latest matching run dir in data/reactions/audio for a script stem."""
    audio_root = get_config().paths.reaction_audio
    exact = audio_root / base_name
    if exact.exists():
        return exact
    latest = None
    counter = 1
    while True:
        candidate = audio_root / f"{base_name}_run{counter}"
        if candidate.exists():
            latest = candidate
            counter += 1
        else:
            break
    return latest


async def run(script: str, audio_dir: Path | None = None, studio: bool = False):
    cfg = get_config()
    script_path = Path(script)
    if not script_path.is_file():
        script_path = cfg.paths.scripts / script
    if not script_path.is_file():
        raise FileNotFoundError(f"Script not found: {script}")

    if audio_dir is None:
        base_name = script_path.stem.removesuffix("_reaction")
        audio_dir = _find_audio_dir(base_name)
    if audio_dir is None or not audio_dir.exists():
        raise FileNotFoundError(
            f"No rendered audio found for {script_path.stem} — run the render stage first"
        )

    log.info("Audio run folder: %s", audio_dir)

    if studio:
        await vts_link.init_vts()

    dialogue_lines = extract_dialogue_lines(script_path.read_text(encoding="utf-8"))
    wav_files = sorted(f for f in audio_dir.iterdir() if f.suffix == ".wav")

    if len(wav_files) != len(dialogue_lines):
        log.warning(
            "Wav count (%d) != dialogue lines (%d); playback may be out of sync",
            len(wav_files),
            len(dialogue_lines),
        )

    log.info("Starting playback (%d lines)", len(wav_files))
    try:
        for i, wav_file in enumerate(wav_files):
            if i < len(dialogue_lines):
                print(f"> {dialogue_lines[i]}")
            await play_audio(wav_file)  # feeds lip-sync when VTS is connected
            await asyncio.sleep(1.0)
    finally:
        if studio:
            await vts_link.close()
    log.info("Playback finished")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Play back a rendered reaction")
    parser.add_argument("script", help="script path, or filename inside data/reactions/scripts/")
    parser.add_argument("--audio-dir", type=Path, default=None)
    parser.add_argument("--studio", action="store_true", help="drive the avatar via VTube Studio")
    args = parser.parse_args(argv)

    setup_logging()
    try:
        asyncio.run(run(args.script, args.audio_dir, args.studio))
        return 0
    except Exception as e:
        log.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
