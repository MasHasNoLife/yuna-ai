"""Speech-to-text for the web UI's push-to-talk.

Runs faster-whisper on CPU by default (config stt.*) so it never competes
with the LLM for VRAM. Accepts whatever the browser's MediaRecorder produced
(webm/opus, ogg) and lets ffmpeg normalize it.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import time

from yuna.core.config import get_config
from yuna.core.logging import get_logger

log = get_logger("stt")

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        cfg = get_config().stt
        log.info("Loading whisper-%s on %s (%s)...", cfg.model, cfg.device, cfg.compute_type)
        _model = WhisperModel(cfg.model, device=cfg.device, compute_type=cfg.compute_type)
    return _model


def _transcribe_file(path: str) -> str:
    wav_path = path + ".wav"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                path,
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-y",
                "-loglevel",
                "quiet",
                wav_path,
            ],
            capture_output=True,
            check=True,
        )
        segments, _ = _get_model().transcribe(wav_path, language="en")
        return " ".join(seg.text.strip() for seg in segments).strip()
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


async def transcribe(audio_bytes: bytes, suffix: str = ".webm") -> tuple[str, float]:
    """Returns (text, elapsed_ms). Empty text means nothing recognized."""
    t0 = time.monotonic()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name
    try:
        text = await asyncio.to_thread(_transcribe_file, tmp_path)
    except subprocess.CalledProcessError:
        log.warning("ffmpeg could not decode uploaded audio")
        text = ""
    finally:
        os.remove(tmp_path)
    return text, (time.monotonic() - t0) * 1000
