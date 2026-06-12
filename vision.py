import asyncio
import base64
import ctypes
import glob
import os
import subprocess

import cv2
import ollama

# ── Preload CUDA libs from pip-installed nvidia packages ─────────────────────
# CTranslate2 uses dlopen which won't find libs buried in site-packages.

def _preload_cuda_libs():
    try:
        import site
        dirs = site.getsitepackages() if hasattr(site, "getsitepackages") else []
        for sp in dirs:
            for lib in sorted(glob.glob(os.path.join(sp, "nvidia", "**", "libcublas*.so*"), recursive=True)):
                ctypes.CDLL(lib, mode=ctypes.RTLD_GLOBAL)
    except (ImportError, OSError):
        pass

_preload_cuda_libs()

from faster_whisper import WhisperModel

# ── Config ────────────────────────────────────────────────────────────────────

VISION_MODEL   = "llava:13b"
WHISPER_SIZE   = "medium"
MAX_FRAMES     = 12          # Max frames to send to the vision model
FRAME_INTERVAL = 1           # Seconds between captured frames
JPEG_QUALITY   = 85          # Compression quality for extracted frames

# ── ANSI colors (match yuna.py) ──────────────────────────────────────────────

RESET = "\033[0m"
GRAY  = "\033[90m"
RED   = "\033[91m"

# ── Whisper (lazy-loaded) ────────────────────────────────────────────────────

_whisper_model = None

def _get_whisper():
    """Load the Whisper model once and cache it. Tries CUDA, falls back to CPU."""
    global _whisper_model
    if _whisper_model is None:
        try:
            print(f"{GRAY}  Loading Whisper ({WHISPER_SIZE}) on CUDA...{RESET}")
            _whisper_model = WhisperModel(WHISPER_SIZE, device="cuda", compute_type="float16")
        except RuntimeError:
            print(f"{GRAY}  CUDA failed, falling back to CPU...{RESET}")
            _whisper_model = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
    return _whisper_model

# ── Frame extraction ─────────────────────────────────────────────────────────

def extract_frames(video_path, interval=FRAME_INTERVAL, max_frames=MAX_FRAMES):
    """
    Pull frames from a video at fixed intervals.
    Returns (list[base64_str], list[float_timestamp], float_duration).
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {video_path}")

    native_fps   = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration     = total_frames / native_fps
    frame_gap    = max(1, int(native_fps * interval))

    frames     = []
    timestamps = []
    frame_idx  = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        if frame_idx % frame_gap == 0:
            _, buffer = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )
            b64 = base64.b64encode(buffer).decode("utf-8")
            frames.append(b64)
            timestamps.append(frame_idx / native_fps)

            if len(frames) >= max_frames:
                break

        frame_idx += 1

    cap.release()
    return frames, timestamps, duration

# ── Audio transcription ──────────────────────────────────────────────────────

def transcribe_audio(video_path):
    """Extract audio track and transcribe with Whisper. Returns [(sec, text), ...] or None."""
    wav_path = video_path + ".tmp.wav"

    try:
        subprocess.run(
            [
                "ffmpeg", "-i", video_path,
                "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                "-y", "-loglevel", "quiet", wav_path,
            ],
            capture_output=True,
            check=True,
        )

        model = _get_whisper()

        try:
            segments, _ = model.transcribe(wav_path)
        except RuntimeError:
            # CUDA failed at inference time — rebuild on CPU
            global _whisper_model
            print(f"{GRAY}  CUDA inference failed, rebuilding Whisper on CPU...{RESET}")
            _whisper_model = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
            model = _whisper_model
            segments, _ = model.transcribe(wav_path)

        # Return timestamped segments: [(start_sec, text), ...]
        result = []
        for seg in segments:
            text = seg.text.strip()
            if text:
                result.append((seg.start, text))
        return result if result else None

    except subprocess.CalledProcessError:
        return None  # no audio track or ffmpeg error

    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)

# ── Frame description (vision model) ─────────────────────────────────────────

VISION_PROMPT = (
    "Describe the primary action or subject in this frame in one concise, objective sentence. "
    "Specifically highlight if the image contains: a cute animal, a physical fail or accident, an impressive stunt, weird/cringe behavior, or readable text. "
    "Ignore all background details, scenery, lighting, clothing, and static talking heads. "
    "If the frame is just a normal conversation or lacks clear dynamic action, output exactly: 'Nothing notable.'"
)

async def describe_frame(client, frame_b64):
    """Send a single frame to the vision model and get a description."""
    response = await client.chat(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": VISION_PROMPT,
                "images": [frame_b64],
            }
        ],
    )
    return response["message"]["content"].strip()

# ── Main pipeline ─────────────────────────────────────────────────────────────

async def summarize_video(video_path):
    """
    Full pipeline: video file → formatted text summary.

    Returns a string with [VISUAL] and [AUDIO] sections ready to feed
    into Yuna's build_video_message().
    """
    if not os.path.isfile(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")

    # ── 1. Extract frames ────────────────────────────────────────────────────
    print(f"{GRAY}  Extracting frames...{RESET}")
    frames, timestamps, duration = extract_frames(video_path)
    print(f"{GRAY}  {len(frames)} frames from {duration:.1f}s video{RESET}")

    # ── 2. Transcribe audio ──────────────────────────────────────────────
    print(f"{GRAY}  Transcribing audio...{RESET}")
    audio_segments = transcribe_audio(video_path)

    if audio_segments:
        total_words = sum(len(t.split()) for _, t in audio_segments)
        print(f"{GRAY}  Audio transcribed ({total_words} words, {len(audio_segments)} segments){RESET}")
    else:
        print(f"{GRAY}  No speech detected{RESET}")

    # ── 3. Describe frames ───────────────────────────────────────────────
    print(f"{GRAY}  Describing frames with {VISION_MODEL}...{RESET}")
    client = ollama.AsyncClient()
    descriptions = []

    for i, (frame, ts) in enumerate(zip(frames, timestamps)):
        desc = await describe_frame(client, frame)
        print(f"{GRAY}    Frame {i + 1}/{len(frames)} done{RESET}")

        # Skip boring frames
        if "nothing notable" in desc.lower():
            continue

        descriptions.append((ts, f"[{int(ts)}s] {desc}"))

    # ── 4. Build interleaved timeline ─────────────────────────────────────
    #   Merge visual + audio entries by timestamp so Yuna
    #   experiences them in the order they actually happen.
    timeline = []

    # Add visual entries (already filtered, only highlights)
    for ts, desc in descriptions:
        timeline.append((ts, desc))

    # Add audio entries
    if audio_segments:
        for start_sec, text in audio_segments:
            timeline.append((start_sec, f'[SPEECH] "{text}"'))

    # Sort by timestamp (visuals and audio interleaved)
    timeline.sort(key=lambda x: x[0])

    # Format
    parts = []
    for ts, entry in timeline:
        # Visual entries already have [Xs] prefix from describe_frame
        if entry.startswith("["):
            parts.append(entry)
        else:
            parts.append(f"[{int(ts)}s] {entry}")

    summary = "\n".join(parts)
    return summary


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: python vision.py <video_path>")
        sys.exit(1)

    result = asyncio.run(summarize_video(sys.argv[1]))
    print(f"\n{'═' * 60}")
    print(result)
    print(f"{'═' * 60}")
