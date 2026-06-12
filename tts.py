"""
tts.py — Kokoro TTS integration for Yuna.

Usage:
  As a module:    from tts import synthesize
  Standalone:     python tts.py "Hello world!"
  Interactive:    python tts.py

Handles:
  - Parsing Yuna's emotional [tags] from response text
  - Running Kokoro TTS directly in Python
  - Saving and playing the resulting audio
"""

import argparse
import asyncio
import os
import re
import soundfile as sf
import torch

try:
    from kokoro import KPipeline
except ImportError:
    print("Kokoro is not installed. Please run: pip install kokoro soundfile")
    KPipeline = None

import vts_link

# ── Config ──────────────────────────────────────────────────────────────────

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
RESPONSE_DIR = os.path.join(BASE_DIR, "responses")

# Kokoro initialization
# We use a global pipeline so it stays loaded in memory between requests
_pipeline = None

# ── ANSI colors ─────────────────────────────────────────────────────────────

RESET = "\033[0m"
GRAY  = "\033[90m"
RED   = "\033[91m"
GREEN = "\033[92m"

# ── Tag parsing ─────────────────────────────────────────────────────────────

TAG_PATTERN = re.compile(r"(?:\[(.*?)\]|\*(.*?)\*)\s*")

def parse_tags(text):
    """
    Strip performance tags from Yuna's response and return clean text.
    """
    clean = TAG_PATTERN.sub("", text).strip()
    clean = re.sub(r"  +", " ", clean)       # collapse double spaces
    return clean

# ── Audio synthesis ─────────────────────────────────────────────────────────

async def synthesize(text, response_num=0, voice='af_heart', play=True):
    """
    Full TTS pipeline:
      1. Strip [tags] from text
      2. Synthesize using Kokoro pipeline
      3. Save .wav file
      4. Optionally play audio

    Returns path to saved audio file, or None on failure.
    """
    global _pipeline

    if KPipeline is None:
        print(f"{RED}  [TTS ERROR] Kokoro not installed.{RESET}")
        return None

    # Extract the first tag to trigger VTube Studio
    match = TAG_PATTERN.search(text)
    if match:
        tag = (match.group(1) or match.group(2)).lower()
        # Trigger the expression asynchronously so it doesn't block audio generation
        asyncio.create_task(vts_link.trigger_expression(tag))

    clean_text = parse_tags(text)

    if not clean_text.strip():
        return None

    if _pipeline is None:
        print(f"{GRAY}  [TTS] Initializing Kokoro Pipeline (this only happens once)...{RESET}", flush=True)
        # Choose 'a' for American English, 'b' for British
        _pipeline = KPipeline(lang_code='a')

    os.makedirs(RESPONSE_DIR, exist_ok=True)
    output_path = os.path.join(RESPONSE_DIR, f"response_{response_num:04d}.wav")

    print(f"{GRAY}  [TTS] Synthesizing ({len(clean_text)} chars) with voice '{voice}'...{RESET}", flush=True)

    try:
        # Run Kokoro generation in a background thread so it doesn't block WebSockets!
        def _run_generator():
            gen = _pipeline(clean_text, voice=voice, speed=1.0, split_pattern=r'\n+')
            return list(gen)
            
        chunks = await asyncio.to_thread(_run_generator)
        
        # Accumulate audio data
        all_audio = []
        sample_rate = 24000
        
        for i, (gs, ps, audio) in enumerate(chunks):
            all_audio.extend(audio)
            
        if not all_audio:
            print(f"{RED}  [TTS ERROR] No audio generated.{RESET}")
            return None
            
        # Save output
        sf.write(output_path, all_audio, sample_rate)
        print(f"{GRAY}  [TTS] Saved: {output_path}{RESET}")

    except Exception as e:
        print(f"{RED}  [TTS ERROR] {e}{RESET}")
        return None

    if play:
        await play_audio(output_path)

    return output_path

# ── Audio playback ──────────────────────────────────────────────────────────

async def play_audio(path):
    """Play a .wav file using ffplay (blocks until done, no video window)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except FileNotFoundError:
        print(f"{RED}  [TTS] ffplay not found — audio saved but not played{RESET}")
    except Exception as e:
        print(f"{RED}  [TTS] Playback error: {e}{RESET}")

# ── Standalone CLI ──────────────────────────────────────────────────────────

async def _cli():
    parser = argparse.ArgumentParser(
        description="Kokoro TTS — synthesize text to speech",
    )
    parser.add_argument("text", nargs="?", help="Text to synthesize (omit for interactive mode)")
    parser.add_argument("--voice", "-v", default="af_heart", help="Kokoro voice name (e.g. af_heart, af_bella)")
    parser.add_argument("--no-play", action="store_true", help="Save audio without playing")

    args = parser.parse_args()

    if KPipeline is None:
        print(f"{RED}Kokoro is not installed! Run: pip install kokoro soundfile{RESET}")
        return

    # ── Single-shot mode ─────────────────────────────────────────────────────
    if args.text:
        await synthesize(args.text, voice=args.voice, play=not args.no_play)
        return

    # ── Interactive mode ─────────────────────────────────────────────────────
    print(f"\n{GREEN}Kokoro TTS — Interactive Mode{RESET}")
    print(f"{GRAY}Type text to synthesize.  'quit' to exit.{RESET}")
    print(f"{GRAY}Using voice: {args.voice}{RESET}\n")

    num = 0
    while True:
        try:
            text = input(f"{GREEN}TTS>{RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GRAY}Bye!{RESET}")
            break

        if not text or text.lower() in ("quit", "exit"):
            break

        path = await synthesize(text, response_num=num, voice=args.voice,
                                play=not args.no_play)
        if path:
            num += 1

if __name__ == "__main__":
    asyncio.run(_cli())
