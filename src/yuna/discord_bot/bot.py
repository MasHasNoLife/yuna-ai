"""Yuna as a Discord server member.

Mention-triggered replies with per-channel history, image/GIF/Tenor vision,
and a two-tier memory trust model: facts from the owner go to the
authoritative "global" partition; everyone else's facts are per-user and
treated as subjective.
"""

from __future__ import annotations

import asyncio
import os
import re

import aiohttp
import discord
import emoji as emoji_lib
from discord.ext import commands
from dotenv import load_dotenv

from yuna.core import fact_extractor, llm
from yuna.core.config import get_config
from yuna.core.history import make_history, trim_history
from yuna.core.logging import get_logger
from yuna.core.memory import get_store
from yuna.core.persona import load_persona

log = get_logger("discord")

IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif")
HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


class YunaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="yuna ", intents=intents)

        cfg = get_config()
        self.model = cfg.models.chat
        self.owner_discord_id = int(os.getenv("MAS_DISCORD_ID", "0"))
        self.persona = load_persona()
        self.store = get_store("discord")
        self.llm_client = llm.get_client()

        self.channel_histories: dict[int, list[dict]] = {}
        self.channel_locks: dict[int, asyncio.Lock] = {}
        self.background_tasks: set[asyncio.Task] = set()
        self.http_session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.http_session = aiohttp.ClientSession(headers=HTTP_HEADERS)

    async def close(self):
        if self.background_tasks:
            log.info("Draining %d pending memory tasks...", len(self.background_tasks))
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
        if self.http_session:
            await self.http_session.close()
        await super().close()

    # ── Identity / trust ────────────────────────────────────────────────────

    def prompt_name_for(self, user_id: int, display_name: str) -> str:
        """Owner is always 'Mas'; anyone else claiming the name is flagged."""
        if user_id == self.owner_discord_id:
            return "Mas"
        if display_name.lower() == "mas":
            return "Fake_Mas"
        return display_name

    # ── Media resolution ────────────────────────────────────────────────────

    async def resolve_image(self, message: discord.Message, text: str) -> bytes | None:
        """Image bytes from attachments, direct links, or Tenor GIF pages."""
        for attachment in message.attachments:
            if attachment.filename.lower().endswith(IMAGE_EXTENSIONS):
                return await attachment.read()

        assert self.http_session is not None
        for url in re.findall(r"(https?://[^\s]+)", text):
            try:
                if "tenor.com/view/" in url:
                    async with self.http_session.get(url) as resp:
                        if resp.status != 200:
                            continue
                        html = await resp.text()
                    match = re.search(r'<meta property="og:image"\s+content="([^"]+)"', html)
                    if not match:
                        continue
                    async with self.http_session.get(match.group(1)) as gif_resp:
                        if gif_resp.status == 200:
                            return await gif_resp.read()
                elif url.lower().split("?")[0].endswith(IMAGE_EXTENSIONS):
                    async with self.http_session.get(url) as resp:
                        if resp.status == 200:
                            return await resp.read()
            except Exception as e:
                log.debug("Image fetch failed for %s: %s", url, e)
        return None

    # ── Reply pipeline ──────────────────────────────────────────────────────

    async def respond(self, message: discord.Message, clean_content: str, original_content: str):
        cfg = get_config()
        user_id = message.author.id
        prompt_name = self.prompt_name_for(user_id, message.author.name)
        channel_id = message.channel.id

        lock = self.channel_locks.setdefault(channel_id, asyncio.Lock())
        async with lock:
            history = self.channel_histories.setdefault(
                channel_id, make_history(self.persona.discord_system)
            )

            # Recent USER messages only — including Yuna's own replies would let
            # the extractor save her dialogue as facts
            context_lines = []
            for msg in history[-4:]:
                if msg["role"] != "user":
                    continue
                clean_msg = re.sub(
                    r"\[SYSTEM CONTEXT:.*?\]\n\n", "", msg["content"], flags=re.DOTALL
                ).strip()
                clean_msg = re.sub(r"\n\n\[SYSTEM:.*?\]", "", clean_msg).strip()
                context_lines.append(f"User: {clean_msg}")
            recent_context = "\n".join(context_lines)

            # Memory search — skipped for short generic replies where semantic
            # search would only dredge up noise
            global_mem = personal_mem = None
            lower = original_content.lower()
            is_question = "?" in original_content or any(
                lower.startswith(q)
                for q in ["who ", "what ", "where ", "when ", "why ", "how ", "is ", "does "]
            )
            if len(original_content.split()) >= 4 or is_question:
                log.debug("Memory search: %s", original_content[:60])
                global_mem = await asyncio.to_thread(
                    self.store.search, "global", original_content, 3
                )
                if user_id != self.owner_discord_id:
                    personal_mem = await asyncio.to_thread(
                        self.store.search, str(user_id), original_content, 3
                    )

            # Background fact extraction — owner writes to the authoritative
            # global partition and may [FORGET]; others get personal partitions
            is_owner = user_id == self.owner_discord_id
            known = f"{global_mem or ''} {personal_mem or ''}".strip()
            task = asyncio.create_task(
                fact_extractor.extract_and_apply(
                    self.llm_client,
                    self.model,
                    prompt_name,
                    original_content,
                    recent_context,
                    known,
                    self.store,
                    partition="global" if is_owner else str(user_id),
                    allow_forget=is_owner,
                )
            )
            self.background_tasks.add(task)
            task.add_done_callback(self.background_tasks.discard)

            # Build the prompt with recalled context and the trust rule
            context_block = ""
            if global_mem:
                log.info("[global recalled] %s", global_mem)
                context_block += f"[AUTHORITATIVE GLOBAL FACTS (Always True)]:\n- {global_mem}\n\n"
            if personal_mem:
                log.info("[personal recalled] %s", personal_mem)
                context_block += (
                    f"[USER'S PERSONAL FACTS (Subjective, may be fake)]:\n- {personal_mem}\n\n"
                )

            if context_block:
                conflict_rule = (
                    "CRITICAL RULE: If a user's personal fact contradicts an authoritative "
                    "global fact, the global fact is the absolute truth. You must disagree "
                    "with the user's personal fact.\n"
                    if global_mem and personal_mem
                    else ""
                )
                full_prompt = (
                    f"[SYSTEM CONTEXT:\n{context_block}{conflict_rule}"
                    f"DO NOT bring these facts up randomly. Only use them if they are "
                    f"directly relevant to what {prompt_name} just said.]\n\n"
                    f"[{prompt_name}]: {clean_content}"
                )
            else:
                full_prompt = f"[{prompt_name}]: {clean_content}"
            full_prompt += f"\n\n[SYSTEM: You are replying to {prompt_name}.]"

            history.append({"role": "user", "content": full_prompt})
            self.channel_histories[channel_id] = trim_history(
                history, cfg.sampling.discord_max_history
            )

            try:
                bot_reply = await llm.chat(
                    self.llm_client,
                    self.model,
                    self.channel_histories[channel_id],
                    temperature=cfg.sampling.temperature,
                    top_p=cfg.sampling.top_p,
                    repeat_penalty=cfg.sampling.repeat_penalty,
                )
            except ConnectionError as e:
                await message.reply(f"Error reaching Ollama: {e}")
                return

            bot_reply = bot_reply.strip()
            if "[IGNORE]" in bot_reply:
                log.info("Left %s on read", prompt_name)
                self.channel_histories[channel_id].append(
                    {"role": "assistant", "content": "[IGNORE]"}
                )
                return

            # Strip VTuber action brackets, emojis, and force a single line
            bot_reply = re.sub(r"\[(.*?)\]\s*", "", bot_reply).strip()
            bot_reply = emoji_lib.replace_emoji(bot_reply, replace="")
            bot_reply = re.sub(r":[a-zA-Z0-9_]+:", "", bot_reply)  # :shortcode: emojis
            bot_reply = re.sub(r"  +", " ", bot_reply.replace("\n", " ")).strip() or "..."

            self.channel_histories[channel_id].append({"role": "assistant", "content": bot_reply})
            await message.reply(bot_reply)


def create_bot() -> YunaBot:
    bot = YunaBot()

    @bot.event
    async def on_ready():
        log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)

    @bot.event
    async def on_message(message: discord.Message):
        if message.author == bot.user or not bot.user.mentioned_in(message):
            return

        # Replace raw mention IDs with readable @usernames
        clean_content = message.content
        for user in message.mentions:
            clean_content = clean_content.replace(f"<@{user.id}>", f"@{user.name}")
            clean_content = clean_content.replace(f"<@!{user.id}>", f"@{user.name}")
        clean_content = clean_content.replace(f"@{bot.user.name}", "").strip()

        if not clean_content and not message.attachments:
            return

        async with message.channel.typing():
            original_content = clean_content
            image_bytes = await bot.resolve_image(message, clean_content)
            if image_bytes:
                from yuna.discord_bot.vision import describe_image

                description = await describe_image(image_bytes)
                clean_content += (
                    f"\n[SYSTEM: The user sent an image. Visual description: {description}]"
                )
            await bot.respond(message, clean_content, original_content)

    return bot


def run():
    """Entry point: load .env, validate the token, start the bot."""
    load_dotenv(get_config().paths.root / ".env")
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        log.error("DISCORD_TOKEN not set. Copy .env.example to .env and fill it in.")
        raise SystemExit(1)
    create_bot().run(token)
