"""Pluggable TTS backends for the web interface.

Every backend implements:
    name: str
    available() -> tuple[bool, str]          # (usable, reason-if-not)
    synth_stream(text) -> (sample_rate, AsyncIterator[bytes])  # 16-bit mono PCM

'kokoro' is the local default; 'fish_cloud' is the API voice-clone path;
'fish_local' talks to the INT4 Fish Speech server when it's running.
"""

from __future__ import annotations

from yuna.core.config import get_config


def get_tts_backend(name: str | None = None):
    from yuna.tts.fish_cloud import FishCloudTTS
    from yuna.tts.fish_local import FishLocalTTS
    from yuna.tts.kokoro import KokoroTTS

    backends = {"kokoro": KokoroTTS, "fish_cloud": FishCloudTTS, "fish_local": FishLocalTTS}
    name = name or get_config().tts.backend
    if name not in backends:
        raise ValueError(f"Unknown TTS backend '{name}' (have: {list(backends)})")
    return backends[name]()


def backend_names() -> list[str]:
    return ["kokoro", "fish_cloud", "fish_local"]
