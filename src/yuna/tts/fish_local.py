"""Local INT4 Fish Speech server backend (the fish-speech-int4-patch fork).

For when the chat LLM is small (or remote) and the 12 GB card has room for
voice cloning locally. Non-streaming server endpoint; audio is decoded and
re-chunked into PCM frames.
"""

from __future__ import annotations

import io
from collections.abc import AsyncIterator

import httpx
import numpy as np
import soundfile as sf

from yuna.core.config import get_config
from yuna.realtime.tags import normalize_for_tts, strip_tags

CHUNK_SAMPLES = 6000  # 250ms at 24k


class FishLocalTTS:
    name = "fish_local"

    def available(self) -> tuple[bool, str]:
        fish = get_config().endpoints.fish_url
        try:
            r = httpx.get(f"{fish}/audio/voices", timeout=2.0)
            if r.status_code == 200:
                return True, ""
            return False, f"INT4 server returned HTTP {r.status_code}"
        except Exception:
            return False, "INT4 server not running (scripts/start_fish_server.sh)"

    def synth_stream(self, text: str) -> tuple[int, AsyncIterator[bytes]]:
        # Sample rate is resolved after decode; 24000 matches the s2-pro codec.
        return 24000, self._generate(text)

    async def _generate(self, text: str) -> AsyncIterator[bytes]:
        from yuna.reactions.render import ensure_voice_registered, load_voice

        cfg = get_config()
        clean = strip_tags(normalize_for_tts(text))
        if not clean:
            return

        voice_id, wav, transcript = load_voice(cfg.tts.fish_voice)
        ensure_voice_registered(voice_id, wav, transcript)

        payload = {
            "model": cfg.tts.fish_model,
            "input": clean,
            "voice": voice_id,
            "response_format": "wav",
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            r = await client.post(f"{cfg.endpoints.fish_url}/audio/speech", json=payload)
            if r.status_code != 200:
                raise ConnectionError(f"INT4 server HTTP {r.status_code}: {r.text[:200]}")

        audio, rate = sf.read(io.BytesIO(r.content), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        if rate != 24000:  # resample cheaply if the server ever changes rate
            duration = len(audio) / rate
            target = int(duration * 24000)
            audio = np.interp(
                np.linspace(0, len(audio) - 1, target), np.arange(len(audio)), audio
            ).astype(np.float32)

        pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
        for i in range(0, len(pcm), CHUNK_SAMPLES * 2):
            yield pcm[i : i + CHUNK_SAMPLES * 2]
