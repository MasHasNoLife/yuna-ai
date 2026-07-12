import sys
import os
import asyncio
import re
from pathlib import Path
import soundfile as sf
import numpy as np

# Add root directory to python path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INPUT_SCRIPTS = os.path.join(os.path.dirname(__file__), "reactions_scripts")
INPUT_AUDIO = os.path.join(os.path.dirname(__file__), "voicetts")

async def play_audio_linux(file_path):
    """Play a .wav file with padded silence to prevent audio cutoff on auto-exit."""
    try:
        # Start ffplay with 0.3s of padding at the end to prevent ALSA buffer cutoff on exit
        proc = await asyncio.create_subprocess_exec(
            "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", "-af", "apad=pad_dur=0.3", file_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
    except FileNotFoundError:
        print(f"[ERROR] ffplay not found. Please install ffmpeg.")
    except Exception as e:
        print(f"[ERROR] Audio playback failed: {e}")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python vts_playback.py <reaction_filename>")
        print("Note: The file must be placed in the reactions/reactions_scripts/ folder.")
        sys.exit(1)

    reaction_name = sys.argv[1]
    script_path = os.path.join(INPUT_SCRIPTS, reaction_name)

    if not os.path.isfile(script_path):
        print(f"[ERROR] Script not found: {script_path}")
        sys.exit(1)

    base_name = Path(reaction_name).stem
    if base_name.endswith("_reaction"):
        base_name = base_name.replace("_reaction", "")

    # We look for voicetts/base_name (e.g. voicetts/reaction1)
    run_dir = os.path.join(INPUT_AUDIO, base_name)
    
    # Fallback to checking for _run1 if exact match doesn't exist
    if not os.path.exists(run_dir):
        counter = 1
        while True:
            test_dir = os.path.join(INPUT_AUDIO, f"{base_name}_run{counter}")
            if os.path.exists(test_dir):
                run_dir = test_dir
                counter += 1
            else:
                break
                
        # If it still doesn't exist, we failed to find it
        if not os.path.exists(run_dir):
            print(f"[ERROR] Could not find any rendered audio folders for {base_name} in {INPUT_AUDIO}")
            sys.exit(1)

    print(f"\n[SYSTEM] Found audio run folder: {run_dir}")
    
    # Read the script lines
    with open(script_path, "r", encoding="utf-8") as f:
        script_text = f.read()
        
    lines = script_text.splitlines()
    dialogue_lines = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("[TIMESTAMP") or line.startswith("[DESCRIPTOR"):
            continue
        dialogue_lines.append(line)
        
    # Get all wav files
    wav_files = [f for f in os.listdir(run_dir) if f.endswith(".wav")]
    wav_files.sort()
    
    if len(wav_files) != len(dialogue_lines):
        print(f"[WARNING] Number of wav files ({len(wav_files)}) does not match number of dialogue lines ({len(dialogue_lines)}). Playback may be out of sync.")

    print(f"\n[PLAYBACK] Starting automated playback...\n")
    
    for i, wav_file in enumerate(wav_files):
        if i < len(dialogue_lines):
            line = dialogue_lines[i]
            
            # Print the line
            print(f"> {line}")
                
            # Play Audio
            audio_path = os.path.join(run_dir, wav_file)
            await play_audio_linux(audio_path)
            
            await asyncio.sleep(1.0) # 1 second pause between lines
        else:
            # We have more audio than lines? Just play it
            audio_path = os.path.join(run_dir, wav_file)
            await play_audio_linux(audio_path)
            
    print("\n[SUCCESS] Playback finished!")

if __name__ == "__main__":
    asyncio.run(main())
