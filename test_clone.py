import httpx
import os
import uuid

FISH_URL = "http://127.0.0.1:8880/v1"
REFERENCE_AUDIO = "reference2.wav"

# --- USER CONFIGURATION ---
# IMPORTANT: For zero-shot cloning to work, the AI needs to know EXACTLY what is being said in the reference file.
# Replace this placeholder with the exact transcript of 'reference.wav'
REFERENCE_TRANSCRIPT = "Hello my name is Yownis. I am 18 years old. I live in Malaysia, and my favorite game is league of legends by riot games."

# Write the sentences you want the voice to say here!
CUSTOM_TEXT = "[happy] Oh my god! I got a 2k play! let's go!"
# --------------------------

def test_clone():
    print("[1] Uploading reference voice...")
    voice_id = f"temp_voice_{uuid.uuid4().hex[:6]}"
    
    try:
        with open(REFERENCE_AUDIO, "rb") as f:
            audio_data = f.read()
            
        files = {
            "audio": (REFERENCE_AUDIO, audio_data, "audio/wav")
        }
        data = {
            "id": voice_id,
            "text": REFERENCE_TRANSCRIPT
        }
        
        r = httpx.post(f"{FISH_URL}/references/add", data=data, files=files, timeout=60.0)
        if r.status_code not in [200, 409]:
            print(f"[ERROR] Failed to upload reference voice: {r.text}")
            return
            
        print(f"    -> Voice registered as '{voice_id}'")
    except Exception as e:
        print(f"[ERROR] Failed to connect to server. Is it running? {e}")
        return

    print(f"\n[2] Generating custom speech...\n    Text: '{CUSTOM_TEXT}'")
    payload = {
        "model": "s2-pro",
        "input": CUSTOM_TEXT,
        "voice": voice_id,
        "response_format": "wav"
    }
    
    try:
        r = httpx.post(f"{FISH_URL}/audio/speech", json=payload, timeout=300.0)
        if r.status_code == 200:
            out_file = "test_output.wav"
            with open(out_file, "wb") as f:
                f.write(r.content)
            print(f"\n[SUCCESS] Rendered audio saved to {out_file}!")
            
            # Clean up the reference on the server so we don't clutter it
            httpx.request("DELETE", f"{FISH_URL}/references/delete", json=voice_id)
        else:
            print(f"\n[ERROR] Rendering failed: {r.text}")
    except Exception as e:
        print(f"\n[ERROR] Request failed: {e}")

if __name__ == "__main__":
    if not os.path.exists(REFERENCE_AUDIO):
        print(f"Error: Could not find {REFERENCE_AUDIO} in the current folder.")
    elif "Put the exact words" in REFERENCE_TRANSCRIPT:
        print("Wait! You need to open this script and update the REFERENCE_TRANSCRIPT variable first!")
    else:
        test_clone()
