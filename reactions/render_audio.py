import sys
import os
import asyncio
import httpx
from pathlib import Path

# Add root directory to python path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

INPUT_DIR = os.path.join(os.path.dirname(__file__), "reactions_scripts")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "voicetts")
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))

FISH_URL = "http://127.0.0.1:8880/v1"

YUNA_AUDIO_PATH = os.path.join(ROOT_DIR, "voice_reference", "furina.wav")

# FOR mommy.wav YUNA_TRANSCRIPT = "I am being jealous over this? I am not even a jealous person, okay? I think I'm pretty mature and understandable and I don't get jealous over these things, okay? Yeah, yeah I said that you're annoying what are you gonna do about it?" # mommy asmr

# YUNA_TRANSCRIPT = "That sounds fun! Wait are you asking me out on a date? Alright, I'll go out o a date with you. I'll see you there, looking forward to it." # random anime same va as kaguya.wav

# YUNA_TRANSCRIPT = "Great looking, what would you think if I said that was guaranteed? Huh? Oh my gosh, you're blushing. I love how you just can't hide anything. You have a little sauce on your face, no let me get that for you." # rin tohsaka

YUNA_TRANSCRIPT = "Good evening. *sigh* Mademoiselle Crabalett has been muttering about getting in shape lately and even said that she wanted to drag me along with her. Hmph, I'm already eating much healthier than last month. I work very hard to maintain my figure. Hey, you can tell, can't you!?" # furina english va

#YUNA_TRANSCRIPT = "I strongly advise you not to stand in the Fatui's way. Otherwise, the next time we meet. I might just have to drop all this meaningless etiquette." # sandrone.wav genshin's en va 

def initialize_yuna_voice():
    """Uploads the Yuna reference audio to the Fish Speech API if not already present."""
    print("[TTS] Checking if Yuna reference voice is loaded...")
    
    voice_id = Path(YUNA_AUDIO_PATH).stem
    
    try:
        r = httpx.get(f"{FISH_URL}/audio/voices", timeout=300.0)
        if r.status_code == 200:
            voices = r.json().get("voices", [])
            if voice_id in voices:
                print(f"[TTS] Voice '{voice_id}' is already registered!")
                return True
                
        # If it's a new voice ID but 'yuna' still exists, it's fine, Fish Speech will just load the new one alongside it.
    except Exception as e:
        print(f"[ERROR] Could not connect to Fish Speech API: {e}")
        return False
        
    print("[TTS] Registering Yuna voice for the first time...")
    try:
        with open(YUNA_AUDIO_PATH, "rb") as f:
            audio_data = f.read()
            
        files = {
            "audio": (f"{voice_id}_reference.wav", audio_data, "audio/wav")
        }
        data = {
            "id": voice_id,
            "text": YUNA_TRANSCRIPT
        }
        
        r = httpx.post(f"{FISH_URL}/references/add", data=data, files=files, timeout=60.0)
        
        if r.status_code in [200, 409]:
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
    voice_id = Path(YUNA_AUDIO_PATH).stem
    print(f"[TTS] Rendering: {text[:50]}...")
    payload = {
        "model": "s2-pro",
        "input": text,
        "voice": voice_id,
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

async def main():
    if len(sys.argv) < 2:
        print("Usage: python 3_render_audio.py <reaction_filename>")
        print("Note: The file must be placed in the reactions/reactions_scripts/ folder.")
        sys.exit(1)

    reaction_name = sys.argv[1]
    reaction_path = os.path.join(INPUT_DIR, reaction_name)

    if not os.path.isfile(reaction_path):
        print(f"[ERROR] Reaction script not found: {reaction_path}")
        sys.exit(1)

    try:
        with open(reaction_path, "r", encoding="utf-8") as f:
            script_text = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read file: {e}")
        sys.exit(1)

    # Determine unique output folder
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    base_name = Path(reaction_name).stem
    if base_name.endswith("_reaction"):
        base_name = base_name.replace("_reaction", "")
        
    run_dir = os.path.join(OUTPUT_DIR, f"{base_name}_run1")
    counter = 1
    while os.path.exists(run_dir):
        counter += 1
        run_dir = os.path.join(OUTPUT_DIR, f"{base_name}_run{counter}")

    print(f"\n[SYSTEM] Preparing to render audio to {run_dir} ...")
    
    if not initialize_yuna_voice():
        print("[ERROR] Cannot render without the Yuna voice initialized.")
        sys.exit(1)
        
    os.makedirs(run_dir, exist_ok=True)
    
    lines = script_text.splitlines()
    dialogue_buffer = []
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith("[TIMESTAMP") or line.startswith("[DESCRIPTOR"):
            continue
        dialogue_buffer.append(line)
            
    print(f"\n[TTS] Found {len(dialogue_buffer)} lines of dialogue to render.")
    
    for i, line in enumerate(dialogue_buffer):
        filename = f"{i+1:03d}.wav"
        out_path = os.path.join(run_dir, filename)
        success = render_line(line, out_path)
        if success:
            print(f"      -> Saved {filename}")
        
    print(f"\n[TTS] Done rendering {len(dialogue_buffer)} audio files to {run_dir}/")

if __name__ == "__main__":
    asyncio.run(main())
