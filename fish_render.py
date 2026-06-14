import httpx
import os
import re

FISH_URL = "http://127.0.0.1:8880/v1"
YUNA_AUDIO_PATH = "yuna_reference.wav"
YUNA_TRANSCRIPT = "Great looking, what would you think if I said that was guaranteed? Huh? Oh my gosh, you're blushing. I love how you just can't hide anything. You have a little sauce on your face, no let me get that for you."

def initialize_yuna_voice():
    """Uploads the Yuna reference audio to the Fish Speech API if not already present."""
    print("[TTS] Checking if Yuna reference voice is loaded...")
    
    try:
        r = httpx.get(f"{FISH_URL}/audio/voices", timeout=300.0)
        if r.status_code == 200:
            voices = r.json().get("voices", [])
            if "yuna" in voices:
                print("[TTS] Yuna voice is already registered!")
                return True
    except Exception as e:
        print(f"[ERROR] Could not connect to Fish Speech API: {e}")
        return False
        
    print("[TTS] Registering Yuna voice for the first time...")
    try:
        with open(YUNA_AUDIO_PATH, "rb") as f:
            audio_data = f.read()
            
        files = {
            "audio": ("yuna_reference.wav", audio_data, "audio/wav")
        }
        data = {
            "id": "yuna",
            "text": YUNA_TRANSCRIPT
        }
        
        r = httpx.post(f"{FISH_URL}/references/add", data=data, files=files, timeout=60.0)
        
        if r.status_code in [200, 409]: # 409 means already exists
            print("[TTS] Yuna voice successfully registered!")
            return True
        else:
            print(f"[ERROR] Failed to register voice: {r.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Failed to upload reference voice: {e}")
        return False

def render_line(text, output_path):
    """Hits the OpenAI compatible endpoint to render TTS."""
    print(f"[TTS] Rendering: {text[:50]}...")
    payload = {
        "model": "s2-pro",
        "input": text,
        "voice": "yuna",
        "response_format": "wav"
    }
    try:
        r = httpx.post(f"{FISH_URL}/audio/speech", json=payload, timeout=300.0)
        if r.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(r.content)
            return True
        else:
            print(f"[ERROR] Rendering failed: {r.text}")
            return False
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        return False

async def render_script(script_text, output_dir="responses/rendered_audio"):
    """Parses the generated script and renders audio for each spoken line."""
    if not initialize_yuna_voice():
        print("[ERROR] Cannot render without the Yuna voice initialized.")
        return
        
    os.makedirs(output_dir, exist_ok=True)
    
    # We split by [TIMESTAMP lines to get separate segments
    # But for simplicity, we can just grab all lines of actual dialogue
    lines = script_text.split("\n")
    dialogue_buffer = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("[TIMESTAMP") or line.startswith("[DESCRIPTOR"):
            continue
            
        # We are intentionally keeping [laugh], [annoyed], etc., so you can test them!
        
        if line:
            dialogue_buffer.append(line)
            
    print(f"\n[TTS] Found {len(dialogue_buffer)} lines of dialogue to render.")
    
    for i, line in enumerate(dialogue_buffer):
        filename = f"{i+1:03d}.wav"
        out_path = os.path.join(output_dir, filename)
        success = render_line(line, out_path)
        if success:
            print(f"      -> Saved {filename}")
        
    print(f"\n[TTS] Done rendering {len(dialogue_buffer)} audio files to {output_dir}/")

if __name__ == "__main__":
    import sys
    import asyncio
    
    if len(sys.argv) < 2:
        print("Usage: python fish_render.py <path_to_text_file> [output_directory]")
        sys.exit(1)
        
    input_file = sys.argv[1]
    out_dir = sys.argv[2] if len(sys.argv) > 2 else "responses/rendered_audio"
        
    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()
        
    asyncio.run(render_script(text, output_dir=out_dir))
