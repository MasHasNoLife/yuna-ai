"""Local Kokoro-82M TTS backend: free, private, always available.

Reuses the realtime pipeline's tag-aware synthesis (per-emotion speaking
rates) and converts to raw 16-bit PCM for the web audio stream.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import numpy as np

from yuna.core.config import get_config
from yuna.realtime.emotions import speech_speed
from yuna.realtime.tags import normalize_for_tts, split_segments

SAMPLE_RATE = 24000
CHUNK_SAMPLES = SAMPLE_RATE // 4  # 250ms per websocket frame


class KokoroTTS:
    name = "kokoro"

    def available(self) -> tuple[bool, str]:
        try:
            import kokoro  # noqa: F401

            return True, ""
        except ImportError:
            return False, "kokoro not installed (pip install kokoro)"

    def synth_stream(self, text: str) -> tuple[int, AsyncIterator[bytes]]:
        return SAMPLE_RATE, self._generate(text)

    async def _generate(self, text: str) -> AsyncIterator[bytes]:
        import asyncio

        from yuna.realtime import tts as rt_tts

        if not rt_tts.preload():
            raise RuntimeError("Kokoro pipeline failed to load")

        voice = get_config().tts.kokoro_voice
        segments = split_segments(normalize_for_tts(text)) or [(None, text)]

        for tag, seg_text in segments:
            if not seg_text.strip():
                continue
            speed = speech_speed(tag)

            def _run(t=seg_text, s=speed):
                return list(rt_tts._pipeline(t, voice=voice, speed=s, split_pattern=r"\n+"))

            chunks = await asyncio.to_thread(_run)
            for _, _, audio in chunks:
                pcm = (np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0) * 32767).astype(
                    np.int16
                )
                raw = pcm.tobytes()
                for i in range(0, len(raw), CHUNK_SAMPLES * 2):
                    yield raw[i : i + CHUNK_SAMPLES * 2]
