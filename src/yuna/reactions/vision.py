"""Multimodal video understanding: frames via OpenCV + LLaVA descriptions,
audio via ffmpeg + faster-whisper, merged into a timestamped timeline.
"""

from __future__ import annotations

import base64
import ctypes
import glob
import os
import subprocess

from yuna.core.config import get_config
from yuna.core.logging import get_logger
from yuna.reactions.timeline import build_timeline

log = get_logger("vision")


# ── Preload CUDA libs from pip-installed nvidia packages ─────────────────────
# CTranslate2 uses dlopen which won't find libs buried in site-packages.
def _preload_cuda_libs():
    try:
        import site

        dirs = site.getsitepackages() if hasattr(site, "getsitepackages") else []
        for sp in dirs:
            pattern = os.path.join(sp, "nvidia", "**", "libcublas*.so*")
            for lib in sorted(glob.glob(pattern, recursive=True)):
                ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
    except (ImportError, OSError):
        pass


_whisper_model = None


def _get_whisper():
    """Load Whisper once and cache it. Tries CUDA, falls back to CPU."""
    global _whisper_model
    if _whisper_model is None:
        _preload_cuda_libs()
        from faster_whisper import WhisperModel

        size = get_config().models.whisper_size
        try:
            log.info("Loading Whisper (%s) on CUDA...", size)
            _whisper_model = WhisperModel(size, device="cuda", compute_type="float16")
        except RuntimeError:
            log.warning("CUDA failed, falling back to CPU")
            _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
    return _whisper_model


# ── Frame extraction ─────────────────────────────────────────────────────────


def extract_frames(video_path: str, interval: int | None = None, max_frames: int | None = None):
    """Pull frames at fixed intervals.
    Returns (list[base64_jpeg], list[timestamp_sec], duration_sec).
    """
    import cv2

    cfg = get_config().vision
    interval = interval or cfg.frame_interval
    max_frames = max_frames or cfg.max_frames

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    native_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = total_frames / native_fps
    frame_gap = max(1, int(native_fps * interval))

    frames, timestamps = [], []
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % frame_gap == 0:
            _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, cfg.jpeg_quality])
            frames.append(base64.b64encode(buffer).decode("utf-8"))
            timestamps.append(frame_idx / native_fps)
            if len(frames) >= max_frames:
                break
        frame_idx += 1

    cap.release()
    return frames, timestamps, duration


# ── Audio transcription ──────────────────────────────────────────────────────


def transcribe_audio(video_path: str) -> list[tuple[float, str]] | None:
    """Extract the audio track and transcribe. Returns [(sec, text), ...] or None."""
    global _whisper_model
    wav_path = video_path + ".tmp.wav"
    try:
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                video_path,
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

        model = _get_whisper()
        try:
            segments, _ = model.transcribe(wav_path)
        except RuntimeError:
            # CUDA failed at inference time — rebuild on CPU
            from faster_whisper import WhisperModel

            log.warning("CUDA inference failed, rebuilding Whisper on CPU")
            size = get_config().models.whisper_size
            _whisper_model = WhisperModel(size, device="cpu", compute_type="int8")
            segments, _ = _whisper_model.transcribe(wav_path)

        result = [(seg.start, seg.text.strip()) for seg in segments if seg.text.strip()]
        return result or None
    except subprocess.CalledProcessError:
        return None  # no audio track or ffmpeg error
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


# ── Frame description (vision model) ─────────────────────────────────────────

VISION_PROMPT_TEMPLATE = (
    "Describe the primary action or subject in this frame in one concise, objective sentence. "
    "Specifically highlight if the image contains: a cute animal, a physical fail or accident, "
    "an impressive stunt, weird/cringe behavior, or readable text. "
    "{audio_context}"
    "{previous_context}"
    "Ignore all background details, scenery, lighting, clothing, and static talking heads. "
    "If the frame is just a normal conversation or lacks clear dynamic action, "
    "output exactly: 'Nothing notable.'"
)


async def describe_frame(client, frame_b64: str, audio_context_text="", previous_context_text=""):
    """Describe one frame, with audio + previous-frame context injected for consistency."""
    audio_injection = (
        f"\n\n[AUDIO CONTEXT]: The following audio was spoken exactly at the moment "
        f"this frame was taken: '{audio_context_text}'. Use this context to identify "
        f"who is speaking or what is happening.\n\n"
        if audio_context_text
        else ""
    )
    previous_injection = (
        f"\n\n[PREVIOUS FRAME CONTEXT]: '{previous_context_text}'.\n"
        f"If the same subjects/scene appear in this new frame, refer to them consistently "
        f"(e.g., 'the same man'). If it is a completely new scene, describe it normally.\n\n"
        if previous_context_text
        else ""
    )
    prompt = VISION_PROMPT_TEMPLATE.replace("{audio_context}", audio_injection).replace(
        "{previous_context}", previous_injection
    )

    response = await client.chat(
        model=get_config().models.vision_frames,
        messages=[{"role": "user", "content": prompt, "images": [frame_b64]}],
    )
    return response["message"]["content"].strip()


# ── Main pipeline ────────────────────────────────────────────────────────────


async def summarize_video(video_path: str) -> str:
    """Video file -> interleaved [visual]/[SPEECH] timeline text."""
    from yuna.core import llm

    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    log.info("Extracting frames...")
    frames, timestamps, duration = extract_frames(video_path)
    log.info("%d frames from %.1fs video", len(frames), duration)

    log.info("Transcribing audio...")
    audio_segments = transcribe_audio(video_path)
    if audio_segments:
        total_words = sum(len(t.split()) for _, t in audio_segments)
        log.info("Audio transcribed (%d words, %d segments)", total_words, len(audio_segments))
    else:
        log.info("No speech detected")

    log.info("Describing frames with %s...", get_config().models.vision_frames)
    client = llm.get_client()
    descriptions: list[tuple[float, str]] = []
    previous_desc = ""

    for i, (frame, ts) in enumerate(zip(frames, timestamps, strict=True)):
        # Audio context within ±1.5s of this frame
        relevant_audio = []
        if audio_segments:
            relevant_audio = [
                text for seg_start, text in audio_segments if abs(seg_start - ts) <= 1.5
            ]

        desc = await describe_frame(
            client,
            frame,
            audio_context_text=" ".join(relevant_audio),
            previous_context_text=previous_desc,
        )
        log.info("Frame %d/%d done", i + 1, len(frames))

        if "nothing notable" in desc.lower():
            continue
        previous_desc = desc
        descriptions.append((ts, f"[{int(ts)}s] {desc}"))

    return build_timeline(descriptions, audio_segments)
