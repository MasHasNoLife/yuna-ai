"""`yuna doctor` — preflight diagnostics for every pipeline.

Checks each external dependency and service, prints a pass/fail table with
actionable hints, and exits non-zero if anything required is broken.
"""

from __future__ import annotations

import shutil
import socket
from dataclasses import dataclass

import httpx

from yuna.core.config import get_config

OK, WARN, FAIL = "ok", "warn", "fail"
_ICONS = {OK: "\033[92m✔\033[0m", WARN: "\033[93m⚠\033[0m", FAIL: "\033[91m✘\033[0m"}


@dataclass
class Check:
    name: str
    status: str
    detail: str
    hint: str = ""


def _check_binary(name: str, hint: str) -> Check:
    path = shutil.which(name)
    if path:
        return Check(name, OK, path)
    return Check(name, FAIL, "not found on PATH", hint)


def _check_ollama() -> list[Check]:
    cfg = get_config()
    url = cfg.endpoints.ollama_url
    try:
        r = httpx.get(f"{url}/api/tags", timeout=5.0)
        r.raise_for_status()
    except Exception as e:
        return [
            Check(
                "ollama server",
                FAIL,
                f"{url} unreachable ({type(e).__name__})",
                "start it with: ollama serve",
            )
        ]

    checks = [Check("ollama server", OK, url)]
    available = [m.get("name", "") or m.get("model", "") for m in r.json().get("models", [])]
    wanted = {
        "chat model": cfg.models.chat,
        "embedding model": cfg.models.embedding,
        "frame vision model": cfg.models.vision_frames,
        "script model": cfg.models.script,
        "discord vision model": cfg.models.vision_discord,
    }
    for label, model in wanted.items():
        if any(model in name for name in available):
            checks.append(Check(label, OK, model))
        else:
            # chat + embedding are required for the core loop; the rest are per-pipeline
            severity = FAIL if label in ("chat model", "embedding model") else WARN
            checks.append(Check(label, severity, f"{model} not pulled", f"ollama pull {model}"))
    return checks


def _check_port(name: str, host: str, port: int, hint: str) -> Check:
    try:
        with socket.create_connection((host, port), timeout=2.0):
            return Check(name, OK, f"{host}:{port}")
    except OSError:
        return Check(name, WARN, f"{host}:{port} not reachable", hint)


def _check_fish() -> Check:
    fish = get_config().endpoints.fish_url
    try:
        r = httpx.get(f"{fish}/audio/voices", timeout=3.0)
        if r.status_code == 200:
            voices = ", ".join(r.json().get("voices", [])) or "no voices registered"
            return Check("fish speech server", OK, f"{fish} ({voices})")
        return Check(
            "fish speech server",
            WARN,
            f"HTTP {r.status_code}",
            "only needed for the reaction render stage",
        )
    except Exception:
        return Check(
            "fish speech server",
            WARN,
            f"{fish} not reachable",
            "start it with: scripts/start_fish_server.sh (reaction pipeline only)",
        )


def _check_cuda() -> Check:
    try:
        import torch

        if torch.cuda.is_available():
            return Check("CUDA", OK, torch.cuda.get_device_name(0))
        return Check(
            "CUDA", WARN, "torch present but no GPU visible", "pipelines fall back to CPU (slow)"
        )
    except ImportError:
        return Check("CUDA", WARN, "torch not importable", "pip install -e .")


def _check_files() -> list[Check]:
    cfg = get_config()
    checks = []

    persona_files = list(cfg.paths.persona.glob("*.txt")) if cfg.paths.persona.exists() else []
    if persona_files:
        checks.append(Check("persona", OK, f"{cfg.paths.persona} ({len(persona_files)} files)"))
    else:
        checks.append(
            Check(
                "persona",
                WARN,
                "no private persona found",
                "using persona.example/ — copy it to persona/ to customize",
            )
        )

    env = cfg.paths.root / ".env"
    if env.exists() and "DISCORD_TOKEN" in env.read_text(encoding="utf-8"):
        checks.append(Check("discord .env", OK, str(env)))
    else:
        checks.append(
            Check(
                "discord .env",
                WARN,
                "DISCORD_TOKEN not configured",
                "cp .env.example .env (discord bot only)",
            )
        )

    voices = cfg.paths.voice_reference / "voices.json"
    if voices.exists():
        checks.append(Check("voice references", OK, str(voices)))
    else:
        checks.append(
            Check(
                "voice references",
                WARN,
                "voices.json missing",
                "cp voice_reference/voices.example.json voice_reference/voices.json",
            )
        )
    return checks


def run() -> int:
    cfg = get_config()
    checks: list[Check] = []

    checks.append(_check_binary("ffmpeg", "install ffmpeg (audio extraction)"))
    checks.append(_check_binary("ffplay", "install ffmpeg (audio playback)"))
    checks.append(_check_binary("ollama", "install from https://ollama.com"))
    checks.extend(_check_ollama())
    checks.append(
        _check_port(
            "vtube studio api",
            cfg.endpoints.vts_host,
            cfg.endpoints.vts_port,
            "start VTube Studio and enable 'Start API' (avatar features only)",
        )
    )
    checks.append(_check_fish())
    checks.append(_check_cuda())
    checks.extend(_check_files())

    print(f"\nYuna doctor — {cfg.paths.root}\n")
    width = max(len(c.name) for c in checks) + 2
    for c in checks:
        line = f"  {_ICONS[c.status]}  {c.name:<{width}} {c.detail}"
        print(line)
        if c.hint and c.status != OK:
            print(f"      {'':<{width}} → {c.hint}")

    failures = [c for c in checks if c.status == FAIL]
    warns = [c for c in checks if c.status == WARN]
    print(
        f"\n  {len(checks) - len(failures) - len(warns)} ok, {len(warns)} warnings, "
        f"{len(failures)} failures\n"
    )
    return 1 if failures else 0
