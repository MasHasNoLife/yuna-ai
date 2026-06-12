import argparse
import asyncio
import os
import ollama
import tts
import vts_link
import memory
from yuna_prompt import SYSTEM_PROMPT
from vision import summarize_video

# ── Config ────────────────────────────────────────────────────────────────────

MODEL        = "llama3.1"
MAX_HISTORY  = 12       # Max messages kept (not counting system prompt)
TEMPERATURE  = 0.8
TOP_P        = 0.9
REPEAT_PEN   = 1.15

# ── ANSI color helpers ────────────────────────────────────────────────────────

RESET  = "\033[0m"
CYAN   = "\033[96m"
YELLOW = "\033[93m"
GRAY   = "\033[90m"
RED    = "\033[91m"

def label(text, color):
    return f"{color}{text}{RESET}"

# ── History helpers ───────────────────────────────────────────────────────────

def make_history():
    """Return a fresh message list with just the system prompt."""
    return [{"role": "system", "content": SYSTEM_PROMPT}]

def trim_history(messages):
    """Keep system prompt + last MAX_HISTORY messages, trimming in pairs."""
    if len(messages) > MAX_HISTORY + 1:
        keep = messages[-(MAX_HISTORY):]
        # Ensure we start with a user message, not an orphaned assistant reply
        if keep and keep[0]["role"] == "assistant":
            keep = keep[1:]
        return [messages[0]] + keep
    return messages

# ── Commands ──────────────────────────────────────────────────────────────────

HELP_TEXT = f"""
{CYAN}Commands:{RESET}
  {YELLOW}/react{RESET}   — Give a video file path for Yuna to watch and react to.
  {YELLOW}/video{RESET}   — Manually paste a video description for Yuna to react to.
  {YELLOW}/reset{RESET}   — Clear conversation history and start fresh.
  {YELLOW}/help{RESET}    — Show this message.
  {YELLOW}exit{RESET}     — Quit.
"""

def print_help():
    print(HELP_TEXT)

# ── Video input ───────────────────────────────────────────────────────────────

def collect_video_input():
    """
    Let the user paste a multi-line video description.
    Two consecutive blank lines (or a single /done) signals end of input.
    """
    print(f"\n{GRAY}Paste your video description or transcript below.")
    print(f"Press Enter twice when done.{RESET}\n")

    lines = []
    blank_streak = 0

    while True:
        try:
            line = input()
        except EOFError:
            break

        if line.strip().lower() in ("/done", "/end"):
            break

        if line.strip() == "":
            blank_streak += 1
            if blank_streak >= 2:
                break
            lines.append(line)
        else:
            blank_streak = 0
            lines.append(line)

    content = "\n".join(lines).strip()
    return content

def build_video_message(description):
    """Wrap video content so Yuna knows it's a video she's watching."""
    return (
        "[VIDEO CONTENT — React to this as if you are watching it live]\n\n"
        + description
    )

# ── Streaming response ────────────────────────────────────────────────────────

async def stream_response(client, messages):
    """Stream Yuna's reply and return the full response string."""
    print(f"\n{CYAN}Yuna:{RESET} ", end="", flush=True)

    response = ""

    try:
        stream = await client.chat(
            model=MODEL,
            messages=messages,
            stream=True,
            options={
                "temperature": TEMPERATURE,
                "top_p": TOP_P,
                "repeat_penalty": REPEAT_PEN,
            }
        )

        async for chunk in stream:
            text = chunk["message"]["content"]
            response += text
            print(text, end="", flush=True)

        print()  # newline after response

    except Exception as e:
        print(f"\n{RED}[ERROR] Could not reach Ollama: {e}{RESET}")
        return None

    return response

async def extract_and_save_memory(username, user_input, client):
    prompt = f"""You are a STRICT memory extractor. Your ONLY job is to extract permanent, long-term facts.
CRITICAL RULES:
1. NEVER extract conversational intents (e.g., "User is asking...", "User is searching...").
2. If the user asks a question, reply NONE.
3. If the user states an action (e.g., "I am looking for someone"), reply NONE.
4. If there is a fact about the user, prefix it with [PERSONAL] {username}.
5. If there is a fact about someone else, prefix it with [GLOBAL].

Example 1:
Message: "who am i"
Response: NONE

Example 2:
Message: "i am searching for someone named james"
Response: NONE

Example 3:
Message: "i am mas can't u see"
Response: NONE

Example 4:
Message: "tell me what you know"
Response: NONE

Example 5:
Message: "my favorite color is neon green"
Response: [PERSONAL] {username} loves the color neon green.

Example 6:
Message: "Ironmouse is a vtuber"
Response: [GLOBAL] Ironmouse is a vtuber.

Message: "{user_input}"
Response:"""
    try:
        response = await client.chat(model=MODEL, messages=[{'role': 'user', 'content': prompt}])
        content = response['message']['content'].strip()
        if content != 'NONE' and "NONE" not in content and len(content) > 5:
            lines = content.split('\n')
            for line in lines:
                clean_line = line.strip(" -*•")
                if clean_line.startswith("[PERSONAL]"):
                    fact = clean_line.replace("[PERSONAL]", "").strip()
                    if fact:
                        await asyncio.to_thread(memory.save_memory, username, fact)
                elif clean_line.startswith("[GLOBAL]"):
                    fact = clean_line.replace("[GLOBAL]", "").strip()
                    if fact:
                        await asyncio.to_thread(memory.save_memory, "global", fact)
    except Exception as e:
        pass

async def chat_loop(tts_enabled=False, studio_enabled=False):
    print(f"\n{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{CYAN}  Yuna — AI VTuber  {RESET}")
    print(f"{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")

    if tts_enabled:
        print(f"{GRAY}[TTS Enabled]{RESET}")

    if studio_enabled:
        # Initialize VTube Studio connection
        await vts_link.init_vts()

    client = ollama.AsyncClient()
    response_num = 0

    # ── Startup checks ───────────────────────────────────────────────────────
    try:
        model_list = await client.list()
    except Exception:
        print(f"\n{RED}[ERROR] Cannot connect to Ollama. Is it running?{RESET}")
        return

    available = [m.model for m in model_list.models]
    if not any(MODEL in m for m in available):
        print(f"\n{RED}[ERROR] Model '{MODEL}' not found. Run: ollama pull {MODEL}{RESET}")
        return

    print(f"{GRAY}[Connected to Ollama — model '{MODEL}' ready]{RESET}")
    print_help()

    messages = make_history()
    
    print()
    raw_user = await asyncio.to_thread(input, f"{GRAY}Log in as (default: Mas): {RESET}")
    current_username = raw_user.strip() or "Mas"
    print(f"{GRAY}Logged in as {current_username}{RESET}\n")

    while True:
        try:
            # Run input() in a separate thread so it doesn't freeze the asyncio event loop!
            raw_input = await asyncio.to_thread(input, f"{YELLOW}[{current_username}]:{RESET} ")
            user_input = raw_input.strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{GRAY}Shutting down...{RESET}")
            break

        if not user_input:
            continue

        # ── Commands ──────────────────────────────────────────────────────────

        if user_input.lower() in ("exit", "quit"):
            print(f"{GRAY}Shutting down...{RESET}")
            break

        if user_input.lower() == "/help":
            print_help()
            continue

        if user_input.lower() == "/reset":
            messages = make_history()
            print(f"{GRAY}[History cleared]{RESET}\n")
            continue

        if user_input.lower() == "/react":
            video_path = input(f"{GRAY}Video path: {RESET}").strip()

            if not video_path:
                print(f"{GRAY}[No path entered]{RESET}\n")
                continue

            if not os.path.isfile(video_path):
                print(f"{RED}[ERROR] File not found: {video_path}{RESET}\n")
                continue

            try:
                print(f"{GRAY}[Processing video...]{RESET}")
                description = await summarize_video(video_path)
                print(f"\n{GRAY}── Generated description ──{RESET}")
                print(f"{GRAY}{description}{RESET}")
                print(f"{GRAY}───────────────────────────{RESET}\n")
            except Exception as e:
                print(f"{RED}[ERROR] Vision pipeline failed: {e}{RESET}\n")
                continue

            video_message = build_video_message(description)
            messages.append({"role": "user", "content": video_message})
            messages = trim_history(messages)

            response = await stream_response(client, messages)
            if response:
                messages.append({"role": "assistant", "content": response})
                if tts_enabled:
                    await tts.synthesize(response, response_num=response_num)
                    response_num += 1
            else:
                messages.pop()

            continue

        if user_input.lower() == "/video":
            description = collect_video_input()

            if not description:
                print(f"{GRAY}[No video content entered]{RESET}\n")
                continue

            # Inject video content as a user message
            video_message = build_video_message(description)
            messages.append({"role": "user", "content": video_message})
            messages = trim_history(messages)

            response = await stream_response(client, messages)
            if response:
                messages.append({"role": "assistant", "content": response})
                if tts_enabled:
                    await tts.synthesize(response, response_num=response_num)
                    response_num += 1
            else:
                messages.pop()  # remove user message that got no reply

            continue

        # ── Normal chat ───────────────────────────────────────────────────────

        # 1. Spawn memory extraction in the background so it doesn't slow down the chat
        asyncio.create_task(extract_and_save_memory(current_username, user_input, client))
        
        # 2. Retrieve past memories based on what the user just said
        personal_mem = await asyncio.to_thread(memory.search_memory, current_username, user_input)
        global_mem = await asyncio.to_thread(memory.search_memory, "global", user_input)
        
        full_user_input = user_input
        context_block = ""
        
        if personal_mem:
            context_block += f"- You previously remembered this about the user: '{personal_mem}'\n"
        if global_mem:
            context_block += f"- You know this general fact: '{global_mem}'\n"
        if context_block:
            full_user_input = f"[SYSTEM CONTEXT:\n{context_block}Use this naturally if it applies.]\n\n[{current_username}]: {user_input}"
        else:
            full_user_input = f"[{current_username}]: {user_input}"

        messages.append({"role": "user", "content": full_user_input})
        messages = trim_history(messages)

        response = await stream_response(client, messages)
        if response:
            messages.append({"role": "assistant", "content": response})
            if tts_enabled:
                await tts.synthesize(response, response_num=response_num)
                response_num += 1
        else:
            messages.pop()  # remove user message that got no reply


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tts", action="store_true", help="Enable text-to-speech")
    parser.add_argument("--studio", action="store_true", help="Enable VTube Studio connection")
    args = parser.parse_args()
    
    asyncio.run(chat_loop(tts_enabled=args.tts, studio_enabled=args.studio))