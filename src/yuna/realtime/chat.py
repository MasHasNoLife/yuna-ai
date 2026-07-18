"""The realtime chat loop: streaming LLM chat with memory recall,
background fact extraction, TTS, and avatar control.
"""

from __future__ import annotations

import asyncio
import re

from yuna.core import fact_extractor, llm
from yuna.core.config import get_config
from yuna.core.history import make_history, trim_history
from yuna.core.logging import get_logger
from yuna.core.memory import get_store
from yuna.core.persona import load_persona
from yuna.realtime import tts, vts_link

log = get_logger("chat")

# Presentation colors for the chat REPL (UI output, not logging)
RESET = "\033[0m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
GRAY = "\033[90m"
RED = "\033[91m"

HELP_TEXT = f"""
{CYAN}Commands:{RESET}
  {YELLOW}/reset{RESET}   — Clear conversation history and start fresh.
  {YELLOW}/help{RESET}    — Show this message.
  {YELLOW}exit{RESET}     — Quit.
"""

# Injected into each user turn: prevents attention drift on the tag format
FORMAT_REMINDER = (
    "\n\n[SYSTEM REMINDER: You are Yuna. The VERY FIRST WORD of your response "
    "MUST be a [tag]. You may use multiple tags throughout. NEVER write "
    "asterisks. Keep your response to 1-2 sentences.]"
)

TEST_TEXT = (
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


async def stream_response(client, model: str, messages: list[dict]) -> str | None:
    """Stream tokens to the terminal; returns the full cleaned response."""
    cfg = get_config().sampling
    print(f"\n{YELLOW}Yuna:{RESET} ", end="", flush=True)
    response = ""
    try:
        async for text in llm.chat_stream(
            client,
            model,
            messages,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            repeat_penalty=cfg.repeat_penalty,
        ):
            # Clean jagged line breaks and strip asterisks as tokens arrive
            text = text.replace("\n", " ").replace("*", "")
            response += text
            print(text, end="", flush=True)
        print()
    except ConnectionError as e:
        print(f"\n{RED}[ERROR] {e}{RESET}")
        return None
    return response


async def chat_loop(
    tts_enabled: bool = False,
    studio_enabled: bool = False,
    test_mode: bool = False,
    stream_enabled: bool = False,
):
    cfg = get_config()
    persona = load_persona()
    system_prompt = persona.system
    if stream_enabled:
        system_prompt = system_prompt + "\n\n" + persona.stream

    print(f"\n{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    print(f"{CYAN}  Yuna — AI VTuber  {RESET}")
    print(f"{CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}")
    if tts_enabled:
        print(f"{GRAY}[TTS Enabled]{RESET}")
    if stream_enabled:
        print(f"{GRAY}[Stream Mode]{RESET}")

    if studio_enabled:
        await vts_link.init_vts()

    # ── Test mode: run canned emotion sequence and exit ──────────────────────
    if test_mode:
        print(f"{YELLOW}[TEST MODE] Running VTS emotion sequence...{RESET}")
        if tts_enabled:
            await tts.synthesize(TEST_TEXT, response_num=0)
        print(f"{YELLOW}[TEST MODE] Sequence complete. Exiting.{RESET}")
        await vts_link.close()
        return

    client = llm.get_client()
    model = cfg.models.chat
    if not await llm.check_model(client, model):
        print(f"{RED}[ERROR] Ollama/model check failed — see log above.{RESET}")
        return
    print(f"{GRAY}[Connected to Ollama — model '{model}' ready]{RESET}")
    print(HELP_TEXT)

    if tts_enabled:
        tts.preload()

    store = get_store("main")
    messages = make_history(system_prompt)
    background_tasks: set[asyncio.Task] = set()
    response_num = 0

    print()
    raw_user = await asyncio.to_thread(input, f"{GRAY}Log in as (default: Mas): {RESET}")
    current_username = raw_user.strip() or "Mas"
    print(f"{GRAY}Logged in as {current_username}{RESET}\n")

    try:
        while True:
            try:
                # input() in a thread so it doesn't freeze the event loop
                raw_input_ = await asyncio.to_thread(
                    input, f"{YELLOW}[{current_username}]:{RESET} "
                )
                user_input = raw_input_.strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{GRAY}Shutting down...{RESET}")
                break

            if not user_input:
                continue

            # ── Commands ─────────────────────────────────────────────────────
            if user_input.lower() in ("exit", "quit"):
                print(f"{GRAY}Shutting down...{RESET}")
                break
            if user_input.lower() == "/help":
                print(HELP_TEXT)
                continue
            if user_input.lower() == "/reset":
                messages = make_history(system_prompt)
                print(f"{GRAY}[History cleared]{RESET}\n")
                continue

            # ── Memory recall ────────────────────────────────────────────────
            global_mem = await asyncio.to_thread(store.search, "global", user_input)

            # ── Background fact extraction ───────────────────────────────────
            if fact_extractor.is_worth_extracting(user_input):
                context_lines = []
                for msg in messages[-3:]:
                    if msg["role"] == "system":
                        continue
                    role_name = "Yuna" if msg["role"] == "assistant" else "User"
                    context_lines.append(f"{role_name}: {msg['content']}")

                task = asyncio.create_task(
                    fact_extractor.extract_and_apply(
                        client,
                        model,
                        current_username,
                        user_input,
                        "\n".join(context_lines),
                        global_mem,
                        store,
                        partition="global",
                    )
                )
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)

            # ── Build user message with recalled context ─────────────────────
            if global_mem:
                print(f"{GRAY}  [Recalled Memory] General: {global_mem}{RESET}")
                full_user_input = (
                    f"(You vaguely recall: General: {global_mem})\n\n"
                    f"[{current_username}]: {user_input}"
                )
            else:
                full_user_input = f"[{current_username}]: {user_input}"
            full_user_input += FORMAT_REMINDER

            messages.append({"role": "user", "content": full_user_input})
            messages = trim_history(messages, cfg.sampling.max_history)

            response = await stream_response(client, model, messages)
            if response:
                messages.append({"role": "assistant", "content": response})

                # Trigger first emotion tag before TTS starts
                if studio_enabled:
                    first = re.search(r"\[(.*?)\]", response)
                    if first:
                        await vts_link.trigger_expression(first.group(1))

                if tts_enabled:
                    await tts.synthesize(response, response_num=response_num)
                    response_num += 1
                    if studio_enabled:
                        await vts_link.trigger_expression(None, turn_off=True)
            else:
                messages.pop()  # remove user message that got no reply
    finally:
        # Drain pending memory extractions so facts aren't dropped on exit
        if background_tasks:
            print(f"{GRAY}[Saving pending memories...]{RESET}")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*background_tasks, return_exceptions=True), timeout=15.0
                )
            except asyncio.TimeoutError:
                log.warning("Memory extraction tasks timed out on shutdown")
        await vts_link.close()
