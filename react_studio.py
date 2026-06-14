import asyncio
import os
import sys
import subprocess
import ollama

import vision
import yuna_prompt
import fish_render

# Terminal colors
CYAN = '\033[96m'
GREEN = '\033[92m'
GRAY = '\033[90m'
RED = '\033[91m'
RESET = '\033[0m'

OFFLINE_MODEL = "gemma2:27b"
OUTPUT_DIR = "responses"

async def flush_vram():
    """Forces Ollama to completely unload the heavy LLM from VRAM."""
    print(f"{GRAY}[System] Purging {OFFLINE_MODEL} from VRAM to make room for TTS...{RESET}")
    try:
        # Run the stop command directly
        subprocess.run(["ollama", "stop", OFFLINE_MODEL], check=True, capture_output=True)
        print(f"{GREEN}[System] VRAM successfully flushed!{RESET}")
    except Exception as e:
        print(f"{RED}[System Warning] Failed to stop model cleanly: {e}{RESET}")

async def generate_offline_script(timeline_text):
    """Feeds the timeline to the massive LLM and generates the reaction script."""
    print(f"\n{CYAN}[LLM] Booting up {OFFLINE_MODEL} (This may take a moment to load into RAM/VRAM)...{RESET}")
    
    prompt = f"React to this video:\n\n{timeline_text}"
    messages = [
        {"role": "system", "content": yuna_prompt.SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    print(f"{CYAN}[LLM] Generating high-fidelity script...{RESET}\n")
    
    try:
        client = ollama.AsyncClient()
        response = ""
        stream = await client.chat(
            model=OFFLINE_MODEL,
            messages=messages,
            stream=True,
            options={
                "temperature": 0.8,
                "top_p": 0.9,
                "repeat_penalty": 1.1,
            }
        )

        async for chunk in stream:
            text = chunk["message"].get("content", "")
            response += text
            print(text, end="", flush=True)

        print() # Newline
        return response

    except Exception as e:
        print(f"\n{RED}[ERROR] LLM Generation failed: {e}{RESET}")
        return None

async def render_fish_speech(script_text):
    """Sends the generated script to the Fish Speech local server to render the audio."""
    print(f"\n{CYAN}[TTS] Connecting to Fish Speech API...{RESET}")
    await fish_render.render_script(script_text)

async def main():
    if len(sys.argv) < 2:
        print(f"{RED}Usage: python react_studio.py <path_to_video.mp4 OR path_to_descriptors.txt>{RESET}")
        sys.exit(1)

    input_path = sys.argv[1]
    
    # ── 1. Input Injection ───────────────────────────────────────────────────
    if input_path.endswith(".txt"):
        print(f"{GRAY}[Input] Reading pre-edited descriptors from {input_path}...{RESET}")
        try:
            with open(input_path, "r", encoding="utf-8") as f:
                timeline = f.read()
        except Exception as e:
            print(f"{RED}[ERROR] Could not read file: {e}{RESET}")
            return
    else:
        print(f"{GRAY}[Input] Running full vision extraction on {input_path}...{RESET}")
        timeline = await vision.summarize_video(input_path)
        if not timeline:
            print(f"{RED}[ERROR] Failed to extract timeline from video.{RESET}")
            return

    # ── 2. Script Generation ─────────────────────────────────────────────────
    script = await generate_offline_script(timeline)
    if not script:
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_txt = os.path.join(OUTPUT_DIR, "offline_script.txt")
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"{GRAY}[System] Script saved to {out_txt}{RESET}")

    # ── 3. VRAM Purge ────────────────────────────────────────────────────────
    await flush_vram()

    # ── 4. Human Review & Editing ────────────────────────────────────────────
    print(f"\n{CYAN}--- REVIEW SCRIPT ---{RESET}")
    print(f"{GRAY}The script has been saved to: {out_txt}{RESET}")
    print(f"{GRAY}You can open that file right now, fix any mistakes, add [laugh] tags, or rewrite lines.{RESET}")
    
    try:
        input(f"\n{GREEN}Press Enter when you are ready to render the audio (or Ctrl+C to abort)...{RESET}")
    except KeyboardInterrupt:
        print(f"\n{GRAY}Aborted. Your script is saved in {out_txt}.{RESET}")
        return
        
    # Reload the script just in case the user edited the file!
    with open(out_txt, "r", encoding="utf-8") as f:
        final_script = f.read()

    # ── 5. Audio Rendering ───────────────────────────────────────────────────
    await render_fish_speech(final_script)
    
    print(f"\n{GREEN}Offline Reaction Studio pipeline complete!{RESET}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{GRAY}Pipeline aborted.{RESET}")
