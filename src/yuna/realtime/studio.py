"""Studio mode: manual puppeteering console.

Paste any tagged script; Yuna performs it with TTS + avatar expressions.
Useful for testing and producing recorded content.
"""

from __future__ import annotations

import asyncio

from yuna.realtime import tts, vts_link

CYAN = "\033[96m"
GREEN = "\033[92m"
GRAY = "\033[90m"
RESET = "\033[0m"


def _read_multiline() -> str:
    lines: list[str] = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)


async def studio_loop():
    print(f"{CYAN}Initializing Studio Mode...{RESET}")
    await vts_link.init_vts()
    tts.preload()

    print(f"\n{GREEN}Yuna Studio Console — Manual Puppeteering{RESET}")
    print(f"{GRAY}Type or PASTE your custom script below.{RESET}")
    print(f"{GRAY}Type 'quit' or 'exit' to shut down.{RESET}\n")

    num = 0
    try:
        while True:
            print(
                f"\n{GREEN}Studio> {GRAY}"
                f"(Paste your text. Type 'END' on a new line and hit Enter to submit!){RESET}"
            )
            try:
                # input in a thread so the VTS websocket stays alive
                text = (await asyncio.to_thread(_read_multiline)).strip()
            except KeyboardInterrupt:
                break

            if not text or text.lower() in ("quit", "exit"):
                break

            await tts.synthesize(text, response_num=num, play=True)
            num += 1
    finally:
        print(f"\n{GRAY}Shutting down Studio...{RESET}")
        await vts_link.close()
