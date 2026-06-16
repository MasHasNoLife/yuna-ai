import sys
import os
import asyncio
from pathlib import Path

# Add root directory to python path to import shared modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from vision import summarize_video

# Directories
REFERENCE_DIR = os.path.join(os.path.dirname(__file__), "reference_videos")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "video_descriptors")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python 1_extract_vision.py <video_filename>")
        print("Note: The video must be placed in the reactions/reference_videos/ folder.")
        sys.exit(1)

    video_name = sys.argv[1]
    video_path = os.path.join(REFERENCE_DIR, video_name)

    if not os.path.isfile(video_path):
        print(f"[ERROR] Video not found: {video_path}")
        sys.exit(1)

    print(f"[VISION] Processing video: {video_name}")
    try:
        description = await summarize_video(video_path)
    except Exception as e:
        print(f"[ERROR] Vision pipeline failed: {e}")
        sys.exit(1)

    if not description:
        print("[ERROR] Failed to extract timeline from video.")
        sys.exit(1)

    # Make sure output dir exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Save output smartly without replacing if possible
    out_file = os.path.join(OUTPUT_DIR, "descriptor.txt")
    
    # If the file exists, append a number
    counter = 1
    while os.path.exists(out_file):
        out_file = os.path.join(OUTPUT_DIR, f"descriptor{counter}.txt")
        counter += 1

    with open(out_file, "w", encoding="utf-8") as f:
        f.write(description)
        
    print(f"\n[SUCCESS] Saved descriptor to: {out_file}")

if __name__ == "__main__":
    asyncio.run(main())
