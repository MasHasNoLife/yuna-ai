import sys
import os
import subprocess
import re

def flush_vram():
    print(f"\n[SYSTEM] Purging models from VRAM to free up resources...")
    models_to_stop = ["gemma2:27b", "minicpm-v", "nomic-embed-text:latest", "llava:13b"]
    for model in models_to_stop:
        try:
            subprocess.run(["/usr/local/bin/ollama", "stop", model], check=False, capture_output=True)
        except Exception as e:
            pass
    print(f"[SYSTEM] VRAM successfully flushed!")

def run_step(command):
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        output_file = None
        for line in process.stdout:
            print(line, end="")
            # Parse output file names
            match = re.search(r"Saved descriptor to: .*/([^/]+\.txt)", line)
            if match:
                output_file = match.group(1)
            
            match = re.search(r"Reaction script saved to: .*/([^/]+\.txt)", line)
            if match:
                output_file = match.group(1)
                
        process.wait()
        if process.returncode != 0:
            print(f"[ERROR] Command {' '.join(command)} failed with code {process.returncode}")
            sys.exit(1)
            
        return output_file
    except Exception as e:
        print(f"[ERROR] Failed to execute {' '.join(command)}: {e}")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print("Usage: python run_all.py <video_filename>")
        print("Note: The video must be placed in the reference_videos/ folder.")
        sys.exit(1)

    video_filename = sys.argv[1]
    
    # 1. Vision
    print("\n" + "="*50)
    print(" STEP 1: EXTRACTING VISION DESCRIPTORS")
    print("="*50)
    descriptor_file = run_step(["python", "extract_vision.py", video_filename])
    
    if not descriptor_file:
        print("[ERROR] Could not determine descriptor file name.")
        sys.exit(1)
        
    flush_vram()

    # 2. LLM
    print("\n" + "="*50)
    print(" STEP 2: GENERATING SCRIPT WITH GEMMA")
    print("="*50)
    reaction_file = run_step(["python", "generate_script.py", descriptor_file])
    
    if not reaction_file:
        print("[ERROR] Could not determine reaction file name.")
        sys.exit(1)
        
    flush_vram()

    # 3. Audio
    print("\n" + "="*50)
    print(" STEP 3: RENDERING AUDIO WITH FISH SPEECH")
    print("="*50)
    run_step(["python", "render_audio.py", reaction_file])

    # 4. Playback
    print("\n" + "="*50)
    print(" STEP 4: VTS PLAYBACK")
    print("="*50)
    run_step(["python", "vts_playback.py", reaction_file])
    
    print("\n" + "="*50)
    print(" PIPELINE COMPLETE!")
    print("="*50)

if __name__ == "__main__":
    main()
