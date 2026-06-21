import os
import sys
import asyncio
import re
import discord
from discord.ext import commands
from dotenv import load_dotenv

# Allow importing from parent directory for memory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ollama
import memory
from memory import get_collection, search_memory, save_memory, delete_memory
from discord_prompt import DISCORD_SYSTEM_PROMPT
from discord_vision import describe_image

# Point load_dotenv to the parent directory to find the main .env file
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
TOKEN = os.getenv('DISCORD_TOKEN')
MAS_DISCORD_ID = int(os.getenv('MAS_DISCORD_ID', '0'))

# Using massive 27B model for intelligence
MODEL = "qwen2.5:14b"
MAX_HISTORY = 40  # INCREASED MEMORY: Remembers the last 20 full conversational exchanges in short-term context!
TEMPERATURE = 0.8
TOP_P = 0.9
REPEAT_PEN = 1.15

# Isolated discord memory database
discord_collection = get_collection(db_name="discord/discord_memory")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="yuna ", intents=intents)

channel_histories = {}
channel_locks = {}

def make_discord_history():
    return [{"role": "system", "content": DISCORD_SYSTEM_PROMPT}]

def trim_history(messages):
    """Keep system prompt + last MAX_HISTORY messages, trimming in pairs."""
    if len(messages) > MAX_HISTORY + 1:
        keep = messages[-(MAX_HISTORY):]
        if keep and keep[0]["role"] == "assistant":
            keep = keep[1:]
        return [messages[0]] + keep
    return messages

async def extract_and_save_discord_memory(user_id, prompt_name, user_input, recent_context, recalled_facts, client):
    prompt = f"""You are a STRICT memory extractor. Your ONLY job is to extract permanent, long-term facts.
CRITICAL RULES:
1. You must ONLY extract BRAND NEW facts explicitly stated in the "New Message to Extract".
2. DO NOT extract facts that are ONLY found in the "Known Database Facts" or "Recent Chat Context" blocks. 
3. If the new message does not contain a new fact, or is just a question/action, reply NONE.
4. NEVER extract conversational intents (e.g., "User is asking...", "User is searching...").
4. If there is ANY fact about a person or the world, prefix it with [FACT].
5. PRONOUN RESOLUTION:
   - "I", "me", "my", "mine" ALWAYS refers to {prompt_name} (the user speaking).
   - "You", "your", "yours" ALWAYS refers to YUNA (the AI receiving the message).
   - "He", "she", "they" refers to third parties mentioned in the Recent Chat Context.
6. ONLY use [FORGET] if the user EXPLICITLY commands you to forget something (e.g. "forget that"). Do NOT use it to correct facts.
7. IF the user organically corrects a past fact (found in Known Database Facts), use [UPDATE] followed by the old fact, a " -> ", and the new fact. Example: [UPDATE] Mas likes red -> Mas likes blue.

Example 1:
Message: "my favorite color is neon green"
Response: [FACT] {prompt_name} loves the color neon green.

Example 2:
Message: "actually my favorite color isn't neon green, it's red"
Response: [UPDATE] {prompt_name} loves the color neon green -> {prompt_name} loves the color red.

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
        target_partition = "global" if str(user_id) == str(MAS_DISCORD_ID) else str(user_id)
        partition_label = "GLOBAL" if target_partition == "global" else "PERSONAL"
        
        response = await client.chat(model=MODEL, messages=[{'role': 'user', 'content': prompt}])
        content = response['message']['content'].strip()
        if content != 'NONE' and "NONE" not in content and len(content) > 5:
            lines = content.split('\n')
            for line in lines:
                clean_line = line.strip(" -*•")
                if clean_line.startswith("[FACT]"):
                    fact = clean_line.replace("[FACT]", "").strip()
                    if fact:
                        print(f"\033[92m[{partition_label} MEMORY EXTRACTED]\033[0m {fact}")
                        await asyncio.to_thread(save_memory, target_partition, fact, discord_collection)
                elif clean_line.startswith("[UPDATE]"):
                    parts = clean_line.replace("[UPDATE]", "").split("->")
                    if len(parts) == 2:
                        old_fact = parts[0].strip()
                        new_fact = parts[1].strip()
                        if old_fact and new_fact:
                            print(f"\033[94m[{partition_label} MEMORY UPDATED]\033[0m {old_fact} -> {new_fact}")
                            await asyncio.to_thread(delete_memory, target_partition, old_fact, discord_collection)
                            await asyncio.to_thread(save_memory, target_partition, new_fact, discord_collection)
                elif clean_line.startswith("[FORGET]"):
                    if str(user_id) == str(MAS_DISCORD_ID):
                        fact = clean_line.replace("[FORGET]", "").strip()
                        if fact:
                            await asyncio.to_thread(delete_memory, "global", fact, discord_collection)
                    else:
                        print(f"\033[93m[FORGET REJECTED]\033[0m Unauthorized user ({prompt_name}) tried to delete a global memory.")
    except Exception as e:
        pass

async def process_ai_response(user_id: int, display_name: str, clean_content: str, message: discord.Message, original_content: str = None):
    if original_content is None:
        original_content = clean_content
    
    channel = message.channel
    user_id_str = str(user_id)
    
    # NO Imposter logic. Treat everyone like a normal friend, UNLESS they try to steal Mas's identity.
    if user_id == MAS_DISCORD_ID:
        prompt_name = "Mas"
    else:
        if display_name.lower() == "mas":
            prompt_name = "Fake_Mas"
        else:
            prompt_name = display_name
            
    channel_id = channel.id
    if channel_id not in channel_locks:
        channel_locks[channel_id] = asyncio.Lock()
        
    async with channel_locks[channel_id]:
        if channel_id not in channel_histories:
            channel_histories[channel_id] = make_discord_history()
            
        history = channel_histories[channel_id]
        
        context_lines = []
        for msg in history[-4:]:
            if msg['role'] == 'system':
                continue
            # CRITICAL FIX: Only include the User's messages in the context for the memory extractor.
            # If we include Yuna's messages, the extractor might accidentally extract her dialogue as a fact!
            if msg['role'] == 'assistant':
                continue
                
            role_name = "User"
            # Strip out internal system tags so the extractor just reads the raw chat
            clean_msg = re.sub(r"\[SYSTEM CONTEXT:.*?\]\n\n", "", msg['content'], flags=re.DOTALL).strip()
            clean_msg = re.sub(r"\n\n\[SYSTEM:.*?\]", "", clean_msg).strip()
            context_lines.append(f"{role_name}: {clean_msg}")
            
        recent_context = "\n".join(context_lines)
        
        # If the user's message is extremely short (e.g., "yes", "lol", "something else"), 
        # semantic search will either pull up random garbage or keep us trapped in the past topic.
        # It's better to just skip the memory search entirely for short, generic replies.
        global_mem = None
        personal_mem = None
        
        original_lower = original_content.lower()
        is_question = "?" in original_content or any(original_lower.startswith(q) for q in ["who ", "what ", "where ", "when ", "why ", "how ", "is ", "does "])
        
        if len(original_content.split()) >= 4 or is_question:
            print(f"\033[90m[MEMORY SEARCH]\033[0m Querying database for: {original_content}")
            global_mem = await asyncio.to_thread(search_memory, "global", original_content, 3, discord_collection)
            if str(user_id) != str(MAS_DISCORD_ID):
                personal_mem = await asyncio.to_thread(search_memory, str(user_id), original_content, 3, discord_collection)
        
        client = ollama.AsyncClient()
        extractor_known_facts = f"{global_mem if global_mem else ''} {personal_mem if personal_mem else ''}".strip()
        asyncio.create_task(extract_and_save_discord_memory(user_id_str, prompt_name, original_content, recent_context, extractor_known_facts, client))
        
        context_block = ""
        if global_mem:
            print(f"\033[96m[GLOBAL RECALLED]\033[0m {global_mem}")
            context_block += f"[AUTHORITATIVE GLOBAL FACTS (Always True)]:\n- {global_mem}\n\n"
            
        if personal_mem:
            print(f"\033[96m[PERSONAL RECALLED]\033[0m {personal_mem}")
            context_block += f"[USER'S PERSONAL FACTS (Subjective, may be fake)]:\n- {personal_mem}\n\n"
            
        if context_block:
            conflict_rule = "CRITICAL RULE: If a user's personal fact contradicts an authoritative global fact, the global fact is the absolute truth. You must disagree with the user's personal fact.\n" if global_mem and personal_mem else ""
            full_prompt = f"[SYSTEM CONTEXT:\n{context_block}{conflict_rule}DO NOT bring these facts up randomly. Only use them if they are directly relevant to what {prompt_name} just said.]\n\n[{prompt_name}]: {clean_content}"
        else:
            full_prompt = f"[{prompt_name}]: {clean_content}"
            
        full_prompt += f"\n\n[SYSTEM: You are replying to {prompt_name}.]"
            
        history.append({"role": "user", "content": full_prompt})
        channel_histories[channel_id] = trim_history(history)
        
        try:
            response = await client.chat(
                model=MODEL,
                messages=channel_histories[channel_id],
                stream=False,
                options={
                    "temperature": TEMPERATURE,
                    "top_p": TOP_P,
                    "repeat_penalty": REPEAT_PEN,
                }
            )
            
            bot_reply = response['message']['content'].strip()
            
            if "[IGNORE]" in bot_reply:
                print(f"\033[93m[IGNORED]\033[0m Left {prompt_name} on read.")
                channel_histories[channel_id].append({"role": "assistant", "content": "[IGNORE]"})
                return
            
            # Strip out any VTuber action brackets, emojis, and force single line
            bot_reply = re.sub(r"\[(.*?)\]\s*", "", bot_reply).strip()
            
            import emoji
            bot_reply = emoji.replace_emoji(bot_reply, replace='')
            
            # Strip Discord shortcode emojis (e.g., :cake:, :smile:)
            bot_reply = re.sub(r':[a-zA-Z0-9_]+:', '', bot_reply)
            
            bot_reply = bot_reply.replace("\n", " ")
            bot_reply = re.sub(r"  +", " ", bot_reply).strip()
            
            if not bot_reply:
                bot_reply = "..."
            
            channel_histories[channel_id].append({"role": "assistant", "content": bot_reply})
            
            await message.reply(bot_reply)
                
        except Exception as e:
            await message.reply(f"Error reaching Ollama: {str(e)}")

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
        
    if bot.user.mentioned_in(message):
        # The ultimate solution: manually replace raw IDs with their global Discord username (e.g., @redx.08)
        clean_content = message.content
        for user in message.mentions:
            clean_content = clean_content.replace(f'<@{user.id}>', f'@{user.name}')
            clean_content = clean_content.replace(f'<@!{user.id}>', f'@{user.name}')
            
        clean_content = clean_content.replace(f'@{bot.user.name}', '').strip()
        
        if not clean_content and not message.attachments:
            return
            
        async with message.channel.typing():
            # Check for images: either as attachments or direct links in the text
            image_bytes = None
            
            if message.attachments:
                for attachment in message.attachments:
                    if any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
                        image_bytes = await attachment.read()
                        break
                        
            if not image_bytes:
                import aiohttp
                urls = re.findall(r'(https?://[^\s]+)', clean_content)
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                
                for url in urls:
                    if 'tenor.com/view/' in url:
                        try:
                            async with aiohttp.ClientSession(headers=headers) as session:
                                async with session.get(url) as resp:
                                    if resp.status == 200:
                                        html = await resp.text()
                                        match = re.search(r'<meta property="og:image"\s+content="([^"]+)"', html)
                                        if match:
                                            gif_url = match.group(1)
                                            async with session.get(gif_url) as gif_resp:
                                                if gif_resp.status == 200:
                                                    image_bytes = await gif_resp.read()
                                                    break
                        except Exception:
                            pass
                    elif any(url.lower().split('?')[0].endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.webp', '.gif']):
                        try:
                            async with aiohttp.ClientSession(headers=headers) as session:
                                async with session.get(url) as resp:
                                    if resp.status == 200:
                                        image_bytes = await resp.read()
                                        break
                        except Exception:
                            pass
                            
            original_content = clean_content
            if image_bytes:
                description = await describe_image(image_bytes)
                clean_content += f"\n[SYSTEM: The user sent an image. Visual description: {description}]"
                        
            await process_ai_response(message.author.id, message.author.name, clean_content, message, original_content)

if __name__ == "__main__":
    if not TOKEN:
        print("Please create a .env file and set DISCORD_TOKEN=your_token_here")
    else:
        bot.run(TOKEN)
