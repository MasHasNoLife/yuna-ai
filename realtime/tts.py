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

TAG_PATTERN = re.compile(r"\[(.*?)\]\s*")

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

    # Pronunciation dictionary to prevent TTS from spelling out expressive sounds!
    text = re.sub(r'\b[Hh]mph\b', 'humph', text)
    text = re.sub(r'\b[Pp]fft\b', 'puf', text)
    text = re.sub(r'\b[Tt]ch\b', 'tsk', text)

    # Convert asterisk emphasis to single quotes.
    # (ALL CAPS makes Kokoro spell it out like an acronym. Quotes usually give it a slight inflection!)
    text = re.sub(r'\*(.*?)\*', r"'\1'", text)

    # Parse all tags and split the text into segments
    segments = []
    last_idx = 0
    current_tag = None
    
    for match in TAG_PATTERN.finditer(text):
        segment_text = text[last_idx:match.start()].strip()
        if segment_text:
            segments.append((current_tag, segment_text))
            
        current_tag = match.group(1).lower()
        last_idx = match.end()
        
    segment_text = text[last_idx:].strip()
    if segment_text:
        segments.append((current_tag, segment_text))
        
    if not segments:
        return None

    if _pipeline is None:
        print(f"{GRAY}  [TTS] Initializing Kokoro Pipeline (this only happens once)...{RESET}", flush=True)
        _pipeline = KPipeline(lang_code='a')

    os.makedirs(RESPONSE_DIR, exist_ok=True)
    
    # 1. Pre-generate audio for ALL segments so there are no pauses during playback
    audio_segments = []
    for idx, (tag, seg_text) in enumerate(segments):
        current_speed = 1.0
        if tag in ["sad", "tired", "bored", "thinking", "confused", "concerned"]:
            current_speed = 0.85
        elif tag in ["angry", "scoff", "hmph", "tease", "smug", "annoyed"]:
            current_speed = 1.05
        elif tag in ["happy", "laugh", "giggle", "impressed", "surprised", "flustered", "embarrassed", "denial", "competitive"]:
            current_speed = 1.15
        elif tag in ["panic", "shock", "gasp", "excited"]:
            current_speed = 1.25

        print(f"{GRAY}  [TTS] Synthesizing [{tag if tag else 'none'}] at {current_speed}x speed...{RESET}", flush=True)

        try:
            def _run_generator(t=seg_text, s=current_speed):
                gen = _pipeline(t, voice=voice, speed=s, split_pattern=r'\n+')
                return list(gen)
                
            chunks = await asyncio.to_thread(_run_generator)
            
            all_audio = []
            for _, _, audio in chunks:
                all_audio.extend(audio)
                
            if all_audio:
                out_path = os.path.join(RESPONSE_DIR, f"response_{response_num:04d}_{idx}.wav")
                sf.write(out_path, all_audio, 24000)
                audio_segments.append((tag, out_path))
        except Exception as e:
            print(f"{RED}  [TTS ERROR] {e}{RESET}")

    # 2. Seamlessly play the audio segments and swap expressions mid-sentence!
    if play:
        for tag, out_path in audio_segments:
            if tag:
                asyncio.create_task(vts_link.trigger_expression(tag, turn_off=False))
            await play_audio(out_path)
            
        # Hold the final emotion for 2 seconds after she stops talking so it doesn't just instantly vanish
        await asyncio.sleep(2.0)
        asyncio.create_task(vts_link.trigger_expression(None, turn_off=True))

    return audio_segments

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
