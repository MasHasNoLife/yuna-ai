"""Full reaction pipeline orchestrator: vision -> script -> render -> playback.

Stages run as subprocesses on purpose: stage 1 loads Whisper into GPU memory
that only a process exit fully releases, and the scriptwriting model needs
that VRAM. Between stages, Ollama models are explicitly evicted. Output paths
are passed explicitly (each stage prints its output path as the last line).
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from yuna.core.config import get_config
from yuna.core.logging import get_logger

log = get_logger("reactions.pipeline")


def flush_vram():
    """Evict Ollama models so the next stage has the GPU to itself."""
    ollama_bin = shutil.which("ollama")
    if not ollama_bin:
        log.warning("ollama binary not on PATH; skipping VRAM flush")
        return
    cfg = get_config().models
    log.info("Purging models from VRAM...")
    for model in {cfg.script, cfg.vision_frames, cfg.vision_discord, cfg.embedding}:
        subprocess.run([ollama_bin, "stop", model], check=False, capture_output=True)
    log.info("VRAM flushed")


def _run_stage(module: str, *args: str) -> str:
    """Run a stage module in a subprocess, stream its output, and return the
    output path it printed on its last line.
    """
    cmd = [sys.executable, "-m", module, *args]
    log.info("Running: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    last_line = ""
    assert proc.stdout is not None
    for line in proc.stdout:
        print(line, end="")
        if line.strip():
            last_line = line.strip()
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"Stage {module} failed with code {proc.returncode}")
    return last_line


def run(video: str, studio: bool = False):
    banner = lambda title: print(f"\n{'=' * 50}\n {title}\n{'=' * 50}")  # noqa: E731

    banner("STEP 1: EXTRACTING VISION DESCRIPTORS")
    descriptor = _run_stage("yuna.reactions.extract", video)
    flush_vram()

    banner("STEP 2: GENERATING REACTION SCRIPT")
    script = _run_stage("yuna.reactions.script_gen", descriptor)
    flush_vram()

    banner("STEP 3: RENDERING AUDIO WITH FISH SPEECH")
    _run_stage("yuna.reactions.render", script)

    banner("STEP 4: PLAYBACK")
    playback_args = [script] + (["--studio"] if studio else [])
    _run_stage("yuna.reactions.playback", *playback_args)

    banner("PIPELINE COMPLETE!")
