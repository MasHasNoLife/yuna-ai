"""Persona loading.

The persona is plain-text data, not executable Python (the old yuna_prompt.py
was importable code, which also made the dashboard's prompt editor a remote
code execution vector). Private persona files live in persona/ (gitignored);
persona.example/ ships with the repo and is the per-file fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from yuna.core.config import get_config
from yuna.core.logging import get_logger

log = get_logger("persona")

FILES = {
    "system": "system.txt",
    "stream": "stream.txt",
    "video_reaction": "video_reaction.txt",
    "text_reaction": "text_reaction.txt",
    "discord_system": "discord_system.txt",
}


@dataclass
class Persona:
    system: str = ""
    stream: str = ""
    video_reaction: str = ""
    text_reaction: str = ""
    discord_system: str = ""


def persona_file(name: str) -> Path:
    """Path of the active (private) persona file for a given field."""
    return get_config().paths.persona / FILES[name]


def load_persona() -> Persona:
    paths = get_config().paths
    persona = Persona()
    missing: list[str] = []

    for field in fields(Persona):
        filename = FILES[field.name]
        private = paths.persona / filename
        example = paths.persona_example / filename
        if private.exists():
            setattr(persona, field.name, private.read_text(encoding="utf-8").strip())
        elif example.exists():
            setattr(persona, field.name, example.read_text(encoding="utf-8").strip())
            missing.append(filename)
        else:
            missing.append(filename)

    if missing:
        log.warning(
            "Using example persona for: %s (create persona/%s to customize)",
            ", ".join(missing),
            ", persona/".join(missing) if len(missing) > 1 else missing[0],
        )
    return persona
