"""Central configuration for all Yuna pipelines.

Loads defaults, then overlays `config.yaml` found via (in order):
  1. $YUNA_CONFIG (explicit path)
  2. ./config.yaml in the current directory
  3. <project root>/config.yaml (nearest ancestor containing pyproject.toml)

Secrets (Discord token, dashboard token) never live in config.yaml — they come
from the environment / .env.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml


def find_project_root(start: Path | None = None) -> Path:
    """Nearest ancestor with a pyproject.toml or config.yaml; falls back to cwd."""
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "pyproject.toml").exists() or (candidate / "config.yaml").exists():
            return candidate
    return cur


@dataclass
class ModelsConfig:
    chat: str = "qwen2.5:14b"
    extractor: str = "qwen2.5:14b"  # background memory extraction (always local/Ollama)
    script: str = "gemma2:27b"
    vision_frames: str = "llava:13b"
    vision_discord: str = "minicpm-v"
    embedding: str = "nomic-embed-text"
    whisper_size: str = "medium"


@dataclass
class LLMConfig:
    """Chat LLM backend. 'ollama' is the primary (local) path; 'google' is the
    secondary API path (needs GOOGLE_API_KEY in .env)."""

    backend: str = "ollama"
    google_model: str = "gemma-4-26b-a4b-it"  # or gemma-4-31b-it (dense, slower)


@dataclass
class EndpointsConfig:
    ollama_url: str = "http://localhost:11434"
    fish_url: str = "http://127.0.0.1:8880/v1"
    vts_host: str = "localhost"
    vts_port: int = 8001


@dataclass
class SamplingConfig:
    temperature: float = 0.8
    top_p: float = 0.9
    repeat_penalty: float = 1.15
    max_history: int = 30
    discord_max_history: int = 40


@dataclass
class MemoryConfig:
    recall_threshold: float = 0.35
    dedup_threshold: float = 0.05
    delete_threshold: float = 0.6
    n_results: int = 2


@dataclass
class TTSConfig:
    backend: str = "kokoro"  # kokoro (local) | fish_cloud (API) | fish_local (INT4 server)
    kokoro_voice: str = "af_heart"
    fish_voice: str = "furina"  # voice id from voice_reference/voices.json
    fish_model: str = "s2-pro"  # local INT4 server model
    fish_cloud_model: str = "s1"  # cloud API model header
    fish_cloud_reference_id: str = ""  # optional fish.audio voice id (skips inline upload)


@dataclass
class STTConfig:
    """Speech-to-text for the web UI's push-to-talk. CPU by default so it
    never competes with the LLM for VRAM."""

    model: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"


@dataclass
class VisionConfig:
    max_frames: int = 30
    frame_interval: int = 2
    jpeg_quality: int = 85


@dataclass
class DashboardConfig:
    host: str = "127.0.0.1"
    port: int = 8000


@dataclass
class PathsConfig:
    """All paths resolve relative to the project root unless absolute."""

    data_dir: str = "data"
    persona_dir: str = "persona"
    persona_example_dir: str = "persona.example"
    voice_reference_dir: str = "voice_reference"

    def __post_init__(self) -> None:
        self._root = find_project_root()

    def _resolve(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else self._root / path

    @property
    def root(self) -> Path:
        return self._root

    @property
    def data(self) -> Path:
        return self._resolve(self.data_dir)

    @property
    def memory(self) -> Path:
        return self.data / "memory"

    @property
    def discord_memory(self) -> Path:
        return self.data / "discord_memory"

    @property
    def responses(self) -> Path:
        return self.data / "responses"

    @property
    def reactions(self) -> Path:
        return self.data / "reactions"

    @property
    def reference_videos(self) -> Path:
        return self.reactions / "reference_videos"

    @property
    def descriptors(self) -> Path:
        return self.reactions / "descriptors"

    @property
    def scripts(self) -> Path:
        return self.reactions / "scripts"

    @property
    def reaction_audio(self) -> Path:
        return self.reactions / "audio"

    @property
    def vts_token(self) -> Path:
        return self.data / "vts_token.txt"

    @property
    def logs(self) -> Path:
        return self.data / "logs"

    @property
    def persona(self) -> Path:
        return self._resolve(self.persona_dir)

    @property
    def persona_example(self) -> Path:
        return self._resolve(self.persona_example_dir)

    @property
    def voice_reference(self) -> Path:
        return self._resolve(self.voice_reference_dir)


@dataclass
class Config:
    models: ModelsConfig = field(default_factory=ModelsConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    endpoints: EndpointsConfig = field(default_factory=EndpointsConfig)
    sampling: SamplingConfig = field(default_factory=SamplingConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    stt: STTConfig = field(default_factory=STTConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)


_SECTIONS = {
    "models": ModelsConfig,
    "llm": LLMConfig,
    "endpoints": EndpointsConfig,
    "sampling": SamplingConfig,
    "memory": MemoryConfig,
    "tts": TTSConfig,
    "stt": STTConfig,
    "vision": VisionConfig,
    "dashboard": DashboardConfig,
    "paths": PathsConfig,
}


def _config_path() -> Path | None:
    explicit = os.environ.get("YUNA_CONFIG")
    if explicit:
        return Path(explicit)
    for candidate in (Path.cwd() / "config.yaml", find_project_root() / "config.yaml"):
        if candidate.exists():
            return candidate
    return None


def load_config(path: Path | str | None = None) -> Config:
    """Build a Config from defaults overlaid with the YAML file (if any).

    Unknown keys in the YAML are ignored with a warning rather than failing,
    so an old config file never blocks startup.
    """
    cfg_path = Path(path) if path else _config_path()
    raw: dict = {}
    if cfg_path and cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

    cfg = Config()
    for section_name in _SECTIONS:
        overrides = raw.get(section_name)
        if not isinstance(overrides, dict):
            continue
        section = getattr(cfg, section_name)
        for key, value in overrides.items():
            if hasattr(section, key) and not key.startswith("_"):
                setattr(section, key, value)
            else:
                # Late import to avoid a cycle with core.logging
                import logging

                logging.getLogger("yuna.config").warning(
                    "Ignoring unknown config key %s.%s", section_name, key
                )
    return cfg


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Singleton accessor used by the pipelines."""
    return load_config()
