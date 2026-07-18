"""Reaction stage 1: video -> vision descriptor file.

Runs as its own process (`python -m yuna.reactions.extract`) so Whisper's
CUDA memory is fully released before the scriptwriting stage loads the LLM.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from yuna.core.config import get_config
from yuna.core.logging import get_logger, setup_logging
from yuna.reactions.timeline import numbered_output_path

log = get_logger("reactions.extract")


async def run(video: str, out: Path | None = None) -> Path:
    """Extract a descriptor for `video` (path or filename inside reference_videos/).
    Returns the descriptor path.
    """
    from yuna.reactions.vision import summarize_video

    cfg = get_config()
    video_path = Path(video)
    if not video_path.is_file():
        video_path = cfg.paths.reference_videos / video
    if not video_path.is_file():
        raise FileNotFoundError(
            f"Video not found: {video} (looked in {cfg.paths.reference_videos})"
        )

    log.info("Processing video: %s", video_path.name)
    description = await summarize_video(str(video_path))
    if not description:
        raise RuntimeError("Failed to extract timeline from video")

    cfg.paths.descriptors.mkdir(parents=True, exist_ok=True)
    out = out or numbered_output_path(cfg.paths.descriptors, "descriptor")
    out.write_text(description, encoding="utf-8")
    log.info("Saved descriptor to: %s", out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract a vision descriptor from a video")
    parser.add_argument("video", help="video path, or filename inside reference_videos/")
    parser.add_argument("--out", type=Path, default=None, help="explicit output file")
    args = parser.parse_args(argv)

    setup_logging()
    try:
        out = asyncio.run(run(args.video, args.out))
        print(out)  # machine-readable: last line is the output path
        return 0
    except Exception as e:
        log.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
