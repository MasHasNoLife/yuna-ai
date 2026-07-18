"""Kokoro TTS: tag-aware synthesis with per-emotion speaking rates,
plus RMS-tracked playback that feeds the avatar's lip-sync.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from yuna.core.config import get_config
from yuna.core.logging import get_logger
from yuna.realtime import vts_link
from yuna.realtime.emotions import speech_speed
from yuna.realtime.tags import normalize_for_tts, split_segments

log = get_logger("tts")

_pipeline = None  # Kokoro stays loaded between requests


def preload() -> bool:
    """Load the Kokoro pipeline up front so the first reply isn't slow."""
    global _pipeline
    if _pipeline is not None:
        return True
    try:
        from kokoro import KPipeline
    except ImportError:
        log.error("Kokoro not installed. Run: pip install kokoro soundfile")
        return False
    from yuna.core.config import get_config

    device = get_config().tts.kokoro_device
    log.info("Loading Kokoro pipeline on %s...", device)
    _pipeline = KPipeline(lang_code="a", device=device)
    return True


async def synthesize(
    text: str,
    response_num: int = 0,
    voice: str | None = None,
    play: bool = True,
    out_dir: Path | None = None,
) -> list[tuple[str | None, Path]] | None:
    """Render text to audio segment(s), one per [tag] segment.

    Pre-generates ALL segments before playback so there are no mid-sentence
    gaps, then plays them while swapping avatar expressions between segments.
    Returns [(tag, wav_path), ...] or None if nothing was rendered.
    """
    cfg = get_config()
    voice = voice or cfg.tts.kokoro_voice
    out_dir = out_dir or cfg.paths.responses

    if not preload():
        return None

    text = normalize_for_tts(text)
    segments = split_segments(text)
    if not segments:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Pre-generate audio for all segments
    audio_segments: list[tuple[str | None, Path]] = []
    for idx, (tag, seg_text) in enumerate(segments):
        current_speed = speech_speed(tag)
        log.debug("Synthesizing [%s] at %.2fx", tag or "none", current_speed)

        try:

            def _run_generator(t=seg_text, s=current_speed):
                gen = _pipeline(t, voice=voice, speed=s, split_pattern=r"\n+")
                return list(gen)

            chunks = await asyncio.to_thread(_run_generator)

            all_audio: list[float] = []
            for _, _, audio in chunks:
                all_audio.extend(audio)

            if all_audio:
                out_path = out_dir / f"response_{response_num:04d}_{idx}.wav"
                sf.write(str(out_path), all_audio, 24000)
                audio_segments.append((tag, out_path))
        except Exception:
            log.exception("Synthesis failed for segment %d", idx)

    # 2. Play segments back-to-back, swapping expressions mid-response
    if play:
        for tag, out_path in audio_segments:
            if tag:
                asyncio.create_task(vts_link.trigger_expression(tag, turn_off=False))
            await play_audio(out_path)

        # Hold the final emotion briefly so it doesn't vanish instantly
        await asyncio.sleep(2.0)
        asyncio.create_task(vts_link.trigger_expression(None, turn_off=True))

    return audio_segments or None


async def play_audio(path: Path | str):
    """Play a wav with ffplay while feeding RMS volume to the avatar lip-sync."""
    try:
        audio_data, sample_rate = sf.read(str(path), dtype="float32")
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)  # stereo -> mono

        # 0.3s of end padding prevents ALSA buffer cutoff on exit
        proc = await asyncio.create_subprocess_exec(
            "ffplay",
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "quiet",
            "-af",
            "apad=pad_dur=0.3",
            str(path),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )

        # Feed RMS volume synced to wall-clock time (~30Hz, matches physics loop)
        chunk_duration = 0.033
        chunk_size = int(sample_rate * chunk_duration)
        total_chunks = len(audio_data) // chunk_size
        start_time = time.monotonic()

        for i in range(total_chunks):
            chunk = audio_data[i * chunk_size : (i + 1) * chunk_size]
            rms = float(np.sqrt(np.mean(chunk**2)))
            # Typical speech RMS is 0.01-0.15 — scale to 0..1
            vts_link.set_audio_level(min(1.0, rms * 8.0))

            target_time = start_time + (i + 1) * chunk_duration
            sleep_for = target_time - time.monotonic()
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

        vts_link.set_audio_level(0.0)
        await proc.wait()
    except FileNotFoundError:
        log.error("ffplay not found — audio saved but not played (install ffmpeg)")
    except Exception:
        log.exception("Playback error")
