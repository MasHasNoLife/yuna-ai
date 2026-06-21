import sys
import os
import asyncio
from pathlib import Path
import ollama

# Add root directory to python path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yuna_prompt import SYSTEM_PROMPT, VIDEO_REACTION_PROMPT
import memory

# Directories
INPUT_DIR = os.path.join(os.path.dirname(__file__), "video_descriptors")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "reactions_scripts")
OFFLINE_MODEL = "gemma2:27b"

async def main():
    if len(sys.argv) < 2:
        print("Usage: python 2_generate_script.py <descriptor_filename>")
        print("Note: The file must be placed in the reactions/video_descriptors/ folder.")
        sys.exit(1)

    descriptor_name = sys.argv[1]
    descriptor_path = os.path.join(INPUT_DIR, descriptor_name)

    if not os.path.isfile(descriptor_path):
        print(f"[ERROR] Descriptor file not found: {descriptor_path}")
        sys.exit(1)

    try:
        with open(descriptor_path, "r", encoding="utf-8") as f:
            timeline_text = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read file: {e}")
        sys.exit(1)

    print(f"\n[LLM] Booting up {OFFLINE_MODEL}...")
    client = ollama.AsyncClient()

    # Query Memory!
    username = "Mas"  # Default user, or we can make it an arg
    personal_mem, global_mem = await asyncio.gather(
        asyncio.to_thread(memory.search_memory, username, "video reaction inside jokes"),
        asyncio.to_thread(memory.search_memory, "global", "video reaction context")
    )

    context_prompt = ""
    if personal_mem or global_mem:
        context_parts = []
        if personal_mem:
            context_parts.append(f"About {username}: {personal_mem}")
        if global_mem:
            context_parts.append(f"General: {global_mem}")
        context = " | ".join(context_parts)
        context_prompt = f"(You vaguely recall: {context})\n\n"

    prompt = f"{context_prompt}React to this video:\n\n{timeline_text}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + VIDEO_REACTION_PROMPT},
        {"role": "user", "content": prompt}
    ]

    print(f"[LLM] Generating high-fidelity script based on memory and descriptor...\n")
    

    try:
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
    except Exception as e:
        print(f"\n[ERROR] LLM Generation failed: {e}")
        sys.exit(1)

    if not response:
        print("[ERROR] Generated empty script.")
        sys.exit(1)

    # Make sure output dir exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Save smartly without overwriting
    out_file = os.path.join(OUTPUT_DIR, "reaction.txt")
    
    counter = 1
    while os.path.exists(out_file):
        out_file = os.path.join(OUTPUT_DIR, f"reaction{counter}.txt")
        counter += 1

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(response)
        
    print(f"\n[System] Reaction script saved to: {out_file}")

if __name__ == "__main__":
    asyncio.run(main())
