import argparse
import asyncio
import os
import sys
import re
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ollama
import tts
import vts_link
import memory
from yuna_prompt import SYSTEM_PROMPT, STREAM_PROMPT

# ── Config ────────────────────────────────────────────────────────────────────

MODEL        = "qwen2.5:14b"
MAX_HISTORY  = 30       # Max messages kept (not counting system prompt)
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

# Store the active system prompt (base or base+stream)
_active_prompt = SYSTEM_PROMPT

def make_history():
    """Return a fresh message list with just the system prompt."""
    return [{"role": "system", "content": _active_prompt}]

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
  {YELLOW}/reset{RESET}   — Clear conversation history and start fresh.
  {YELLOW}/help{RESET}    — Show this message.
  {YELLOW}exit{RESET}     — Quit.
"""

def print_help():
    print(HELP_TEXT)


# ── Streaming response ────────────────────────────────────────────────────────

async def stream_response(client, messages):
    print(f"\n{YELLOW}Yuna:{RESET} ", end="", flush=True)
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
            text = chunk["message"].get("content", "")
            # Clean up the LLM's jagged line breaks and completely strip asterisks
            text = text.replace("\n", " ").replace("*", "")
            response += text
            print(text, end="", flush=True)

        print()  # newline after response

    except Exception as e:
        print(f"\n{RED}[ERROR] Could not reach Ollama: {e}{RESET}")
        return None

    return response

async def extract_and_save_memory(username: str, recent_context: str, recalled_facts: str, user_input: str, client):
    prompt = f"""You are a STRICT memory extractor. Your ONLY job is to extract permanent, long-term facts.
CRITICAL RULES:
1. NEVER extract conversational intents (e.g., "User is asking...", "User is searching...").
2. If the user asks a question, reply NONE.
3. If the user states an action (e.g., "I am looking for someone"), reply NONE.
4. If there is ANY fact about a person or the world, prefix it with [FACT].
5. PRONOUN RESOLUTION:
   - "I", "me", "my", "mine" ALWAYS refers to {username} (the user speaking).
   - "You", "your", "yours" ALWAYS refers to YUNA (the AI receiving the message).
   - "He", "she", "they" refers to third parties mentioned in the Recent Chat Context.
6. ONLY use [FORGET] if the user EXPLICITLY commands you to forget something (e.g. "forget that"). Do NOT use it to correct facts.
7. IF the user organically corrects a past fact (found in Known Database Facts), use [UPDATE] followed by the old fact, a " -> ", and the new fact. Example: [UPDATE] Mas likes red -> Mas likes blue.

Example 1:
Message: "my favorite color is neon green"
Response: [FACT] {username} loves the color neon green.

Example 2:
Message: "actually my favorite color isn't neon green, it's red"
Response: [UPDATE] {username} loves the color neon green -> {username} loves the color red.

Example 3:
Message: "your nickname is tuna"
Response: [FACT] Yuna's nickname is tuna.

Known Database Facts:
{recalled_facts if recalled_facts else "None"}

Recent Chat Context:
{recent_context}

New Message to Extract: "{user_input}"
Response:"""
    try:
        response = await client.chat(model=MODEL, messages=[{'role': 'user', 'content': prompt}])
        content = response['message']['content'].strip()
        if content != 'NONE' and "NONE" not in content and len(content) > 5:
            lines = content.split('\n')
            for line in lines:
                clean_line = line.strip(" -*•")
                if clean_line.startswith("[FACT]"):
                    fact = clean_line.replace("[FACT]", "").strip()
                    if fact:
                        print(f"\033[92m[MEMORY EXTRACTED]\033[0m {fact}")
                        await asyncio.to_thread(memory.save_memory, "global", fact)
                elif clean_line.startswith("[UPDATE]"):
                    parts = clean_line.replace("[UPDATE]", "").split("->")
                    if len(parts) == 2:
                        old_fact = parts[0].strip()
                        new_fact = parts[1].strip()
                        if old_fact and new_fact:
                            print(f"\033[94m[MEMORY UPDATED]\033[0m {old_fact} -> {new_fact}")
                            await asyncio.to_thread(memory.delete_memory, "global", old_fact)
                            await asyncio.to_thread(memory.save_memory, "global", new_fact)
                elif clean_line.startswith("[FORGET]"):
                    fact = clean_line.replace("[FORGET]", "").strip()
                    if fact:
                        await asyncio.to_thread(memory.delete_memory, "global", fact)
    except Exception as e:
        pass

async def chat_loop(tts_enabled=False, studio_enabled=False, test_mode=False, stream_enabled=False):
    global _active_prompt
    
    if stream_enabled:
        _active_prompt = SYSTEM_PROMPT + "\n\n" + STREAM_PROMPT
    else:
        _active_prompt = SYSTEM_PROMPT

    print(f"\n{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{CYAN}  Yuna — AI VTuber  {RESET}")
    print(f"{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")

    if tts_enabled:
        print(f"{GRAY}[TTS Enabled]{RESET}")
    if stream_enabled:
        print(f"{GRAY}[Stream Mode]{RESET}")

    if studio_enabled:
        await vts_link.init_vts()

    # ── Test mode: run canned emotions and exit ──────────────────────────
    if test_mode:
        print(f"{YELLOW}[TEST MODE] Running VTS emotion sequence...{RESET}")
        test_text = (
            "[happy] I am so excited to test this new system! "
            "[laugh] Ha, this is amazing, I can't stop bouncing! "
            "[sad] But what if something breaks again... "
            "[angry] That would be so frustrating! "
            "[smug] Nah, my developer is way too smart for that. "
            "[surprised] Wait, did it actually work?! "
            "[thinking] Hmm, let me think about what else to test... "
            "[flustered] Oh no, everyone is watching me test this! "
            "[excited] This is the best day ever!"
        )
        if tts_enabled:
            await tts.synthesize(test_text, response_num=0)
        print(f"{YELLOW}[TEST MODE] Sequence complete. Exiting.{RESET}")
        if studio_enabled and vts_link._instance:
            await vts_link._instance.close()
        return

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


        # ── Normal chat ───────────────────────────────────────────────────────

        # 2. Retrieve past global memories
        global_mem = await asyncio.to_thread(memory.search_memory, "global", user_input)
        
        # 1. Spawn memory extraction only if the message is substantial enough to contain facts
        if len(user_input.split()) >= 4:
            context_lines = []
            for msg in messages[-3:]:
                if msg['role'] == 'system':
                    continue
                role_name = "Yuna" if msg['role'] == 'assistant' else "User"
                context_lines.append(f"{role_name}: {msg['content']}")
            
            recent_context = "\n".join(context_lines)

            asyncio.create_task(extract_and_save_memory(current_username, recent_context, global_mem, user_input, client))
        
        # 3. Build the user message, injecting memories only if relevant
        if global_mem:
            context = f"General: {global_mem}"
            print(f"{GRAY}  [Recalled Memory] {context}{RESET}")
            full_user_input = f"(You vaguely recall: {context})\n\n[{current_username}]: {user_input}"
        else:
            full_user_input = f"[{current_username}]: {user_input}"

        # Injecting formatting rules into the user prompt prevents 'attention drift' 
        # and guarantees compliance with the 1-sentence tag format.
        full_user_input += "\n\n[SYSTEM REMINDER: You are Yuna, a female ai waifu. The VERY FIRST WORD of your response MUST be a [tag]. You may use multiple tags throughout. NEVER write asterisks. Keep your response to 1-2 sentences.]"

        messages.append({"role": "user", "content": full_user_input})
        messages = trim_history(messages)

        response = await stream_response(client, messages)
        if response:
            messages.append({"role": "assistant", "content": response})

            # Trigger first emotion tag before TTS starts
            if studio_enabled:
                first_tag = re.search(r'\[(.*?)\]', response)
                if first_tag:
                    await vts_link.trigger_expression(first_tag.group(1))

            if tts_enabled:
                await tts.synthesize(response, response_num=response_num)
                response_num += 1

                # Reset to neutral after speech ends
                if studio_enabled:
                    await vts_link.trigger_expression(None, turn_off=True)
        else:
            messages.pop()  # remove user message that got no reply


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tts", action="store_true", help="Enable text-to-speech")
    parser.add_argument("--studio", action="store_true", help="Enable VTube Studio integration")
    parser.add_argument("--test", action="store_true", help="Run VTS test sequence then exit")
    parser.add_argument("--stream", action="store_true", help="Enable streaming mode")
    args = parser.parse_args()

    asyncio.run(chat_loop(
        tts_enabled=args.tts,
        studio_enabled=args.studio,
        test_mode=args.test,
        stream_enabled=args.stream
    ))