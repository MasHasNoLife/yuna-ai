"""Reaction stage 2: descriptor (or text topic) -> in-character reaction script,
written by the offline scriptwriting model and seeded with recalled memories.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from yuna.core import llm
from yuna.core.config import get_config
from yuna.core.logging import get_logger, setup_logging
from yuna.core.memory import get_store
from yuna.core.persona import load_persona
from yuna.reactions.timeline import numbered_output_path

log = get_logger("reactions.script")


async def _recall_context(username: str = "Mas") -> str:
    store = get_store("main")
    personal_mem, global_mem = await asyncio.gather(
        asyncio.to_thread(store.search, username, "video reaction inside jokes"),
        asyncio.to_thread(store.search, "global", "video reaction context"),
    )
    parts = []
    if personal_mem:
        parts.append(f"About {username}: {personal_mem}")
    if global_mem:
        parts.append(f"General: {global_mem}")
    return f"(You vaguely recall: {' | '.join(parts)})\n\n" if parts else ""


async def run(source: str, out: Path | None = None, from_text: bool = False) -> Path:
    """Generate a reaction script.

    source: descriptor path/filename (default) or a raw text topic (from_text=True).
    Returns the script path.
    """
    cfg = get_config()
    persona = load_persona()

    if from_text:
        content = source
        task_prompt = persona.text_reaction
        user_prompt = f"Topic/Scenario:\n\n{content}"
        stem = "text_reaction"
    else:
        descriptor_path = Path(source)
        if not descriptor_path.is_file():
            descriptor_path = cfg.paths.descriptors / source
        if not descriptor_path.is_file():
            raise FileNotFoundError(f"Descriptor not found: {source}")
        content = descriptor_path.read_text(encoding="utf-8")
        task_prompt = persona.video_reaction
        user_prompt = f"React to this video:\n\n{content}"
        stem = "reaction"

    model = cfg.models.script
    log.info("Generating script with %s...", model)
    client = llm.get_client()

    context_prompt = await _recall_context()
    messages = [
        {"role": "system", "content": persona.system + "\n\n" + task_prompt},
        {"role": "user", "content": context_prompt + user_prompt},
    ]

    response = ""
    async for text in llm.chat_stream(
        client, model, messages, temperature=0.8, top_p=0.9, repeat_penalty=1.1
    ):
        response += text
        print(text, end="", flush=True)
    print()

    if not response.strip():
        raise RuntimeError("Generated empty script")

    cfg.paths.scripts.mkdir(parents=True, exist_ok=True)
    out = out or numbered_output_path(cfg.paths.scripts, stem)
    out.write_text(response, encoding="utf-8")
    log.info("Reaction script saved to: %s", out)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a reaction script")
    parser.add_argument("source", help="descriptor file, or a text topic with --text")
    parser.add_argument("--text", action="store_true", help="treat source as a raw text topic")
    parser.add_argument("--out", type=Path, default=None, help="explicit output file")
    args = parser.parse_args(argv)

    setup_logging()
    try:
        out = asyncio.run(run(args.source, args.out, from_text=args.text))
        print(out)
        return 0
    except Exception as e:
        log.error("%s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
