"""Fish Audio cloud TTS backend (api.fish.audio): streaming voice clone.

Secondary/API path — costs per character and sends text to Fish's servers.
Uses the reference voice from voice_reference/voices.json (inline upload) or
a fish.audio voice id if tts.fish_cloud_reference_id is set.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx

from yuna.core.config import get_config
from yuna.core.logging import get_logger
from yuna.realtime.tags import normalize_for_tts, strip_tags

log = get_logger("tts.fish_cloud")

API_URL = "https://api.fish.audio/v1/tts"
SAMPLE_RATE = 24000  # requested from the API for parity with Kokoro


class FishCloudTTS:
    name = "fish_cloud"

    def __init__(self):
        self._reference: dict | None = None

    def available(self) -> tuple[bool, str]:
        if not os.getenv("FISH_API_KEY"):
            return False, "FISH_API_KEY not set in .env"
        try:
            import ormsgpack  # noqa: F401
        except ImportError:
            return False, "ormsgpack not installed (pip install ormsgpack)"
        return True, ""

    def _load_reference(self) -> dict:
        """Inline reference (audio bytes + transcript) from voices.json."""
        if self._reference is None:
            from yuna.reactions.render import load_voice

            _, wav, transcript = load_voice(get_config().tts.fish_voice)
            self._reference = {"audio": wav.read_bytes(), "text": transcript}
        return self._reference

    def synth_stream(self, text: str) -> tuple[int, AsyncIterator[bytes]]:
        return SAMPLE_RATE, self._generate(text)

    async def _generate(self, text: str) -> AsyncIterator[bytes]:
        import ormsgpack

        cfg = get_config().tts
        clean = strip_tags(normalize_for_tts(text))
        if not clean:
            return

        body: dict = {
            "text": clean,
            "format": "pcm",  # raw 16-bit mono PCM at sample_rate
            "sample_rate": SAMPLE_RATE,
            "latency": "balanced",
        }
        if cfg.fish_cloud_reference_id:
            body["reference_id"] = cfg.fish_cloud_reference_id
        else:
            body["references"] = [self._load_reference()]

        headers = {
            "Authorization": f"Bearer {os.environ['FISH_API_KEY']}",
            "Content-Type": "application/msgpack",
            "model": cfg.fish_cloud_model,
        }

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
            async with client.stream(
                "POST", API_URL, headers=headers, content=ormsgpack.packb(body)
            ) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode(errors="replace")[:200]
                    if resp.status_code == 402:
                        raise ConnectionError(
                            "Fish API credit empty — top up at fish.audio/app/developers"
                        )
                    raise ConnectionError(f"Fish cloud TTS HTTP {resp.status_code}: {detail}")
                async for chunk in resp.aiter_bytes():
                    if chunk:
                        yield chunk
