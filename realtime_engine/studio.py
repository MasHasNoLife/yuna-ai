import asyncio
import sys

import tts
import vts_link

# Terminal colors
CYAN = '\033[96m'
GREEN = '\033[92m'
GRAY = '\033[90m'
RESET = '\033[0m'

async def main():
    print(f"{CYAN}Initializing Studio Mode...{RESET}")
    
    # Connect to VTube Studio
    print(f"{GRAY}Connecting to VTube Studio...{RESET}")
    await vts_link.init_vts()
    
    print(f"\n{GREEN}Yuna Studio Console — Manual Puppeteering{RESET}")
    print(f"{GRAY}Type or PASTE your custom script below.{RESET}")
    print(f"{GRAY}Type 'quit' or 'exit' to shut down.{RESET}\n")

    def read_multiline():
        lines = []
        while True:
            try:
                line = input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
            except EOFError:
                break
        return "\n".join(lines)

    num = 0
    while True:
        print(f"\n{GREEN}Studio> {GRAY}(Paste your text. Type 'END' on a new line and hit Enter to submit!){RESET}")
        try:
            # Run input in a background thread so we don't freeze the VTube Studio connection!
            text = await asyncio.to_thread(read_multiline)
            text = text.strip()
        except KeyboardInterrupt:
            print(f"\n{GRAY}Shutting down Studio...{RESET}")
            break

        if not text or text.lower() in ("quit", "exit"):
            print(f"\n{GRAY}Shutting down Studio...{RESET}")
            break

        # Send the exact text to her TTS engine, which will automatically 
        # play the audio and trigger the VTube Studio tags!
        await tts.synthesize(text, response_num=num, play=True)
        num += 1

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
