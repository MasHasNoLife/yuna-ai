"""The `yuna` command-line interface: one entry point for every pipeline."""

from __future__ import annotations

import argparse
import asyncio
import sys

from yuna import __version__
from yuna.core.config import get_config
from yuna.core.logging import setup_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="yuna",
        description="Yuna AI — a fully local AI VTuber pipeline.",
    )
    parser.add_argument("--version", action="version", version=f"yuna-ai {__version__}")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p_chat = sub.add_parser("chat", help="realtime chat with Yuna")
    p_chat.add_argument("--tts", action="store_true", help="enable text-to-speech")
    p_chat.add_argument("--studio", action="store_true", help="enable VTube Studio avatar")
    p_chat.add_argument("--stream", action="store_true", help="stream-mode persona")
    p_chat.add_argument("--test", action="store_true", help="run the canned emotion demo and exit")

    sub.add_parser("studio", help="manual puppeteering console (paste scripts, Yuna performs)")

    p_tts = sub.add_parser("tts", help="synthesize text with the realtime TTS")
    p_tts.add_argument("text", nargs="?", help="text to speak (omit for interactive mode)")
    p_tts.add_argument("--voice", default=None, help="Kokoro voice (default from config)")
    p_tts.add_argument("--no-play", action="store_true", help="save audio without playing")

    p_react = sub.add_parser("react", help="full video reaction pipeline (4 stages)")
    p_react.add_argument(
        "video", help="video path, or filename in data/reactions/reference_videos/"
    )
    p_react.add_argument(
        "--studio", action="store_true", help="lip-sync the avatar during playback"
    )

    p_rt = sub.add_parser("react-text", help="reaction script from a text topic")
    p_rt.add_argument("topic", help="topic or scenario to react to")

    sub.add_parser("discord", help="run the Discord bot")
    sub.add_parser("web", help="run the web interface (chat + memory + monitoring)")
    sub.add_parser("dashboard", help="alias for 'web'")
    sub.add_parser("doctor", help="check every dependency and service")

    p_bench = sub.add_parser("bench", help="memory benchmark (LoCoMo replay + QA scoring)")
    p_bench.add_argument(
        "--dataset", default="data/benchmarks/locomo10.json", help="path to locomo10.json"
    )
    p_bench.add_argument(
        "--strategy",
        default="agentic",
        choices=["none", "full_history", "raw_rag", "agentic"],
        help="memory strategy under test",
    )
    p_bench.add_argument("--model", default=None, help="Ollama model (default: models.extractor)")
    p_bench.add_argument(
        "--qa-model", default="", help="QA answerer model (default: same as --model)"
    )
    p_bench.add_argument(
        "--no-grounding", action="store_true", help="ablation: disable temporal grounding"
    )
    p_bench.add_argument("--conversations", type=int, default=1, help="how many convs (0=all)")
    p_bench.add_argument("--sessions", type=int, default=0, help="sessions per conv (0=all)")
    p_bench.add_argument("--qa", type=int, default=0, help="questions per conv (0=all)")
    p_bench.add_argument("--out", default="data/bench_results", help="output directory")

    args = parser.parse_args(argv)
    cfg = get_config()
    setup_logging(args.verbose, log_dir=cfg.paths.logs)

    from dotenv import load_dotenv

    load_dotenv(cfg.paths.root / ".env")

    if args.command == "chat":
        from yuna.realtime.chat import chat_loop

        asyncio.run(
            chat_loop(
                tts_enabled=args.tts,
                studio_enabled=args.studio,
                test_mode=args.test,
                stream_enabled=args.stream,
            )
        )
        return 0

    if args.command == "studio":
        from yuna.realtime.studio import studio_loop

        try:
            asyncio.run(studio_loop())
        except KeyboardInterrupt:
            pass
        return 0

    if args.command == "tts":
        return asyncio.run(_tts_command(args))

    if args.command == "react":
        from yuna.reactions.pipeline import run as run_pipeline

        run_pipeline(args.video, studio=args.studio)
        return 0

    if args.command == "react-text":
        from yuna.reactions.script_gen import run as run_script

        out = asyncio.run(run_script(args.topic, from_text=True))
        print(out)
        return 0

    if args.command == "discord":
        from yuna.discord_bot.bot import run as run_bot

        run_bot()
        return 0

    if args.command in ("web", "dashboard"):
        from yuna.web.server import run as run_web

        run_web()
        return 0

    if args.command == "doctor":
        from yuna.doctor import run as run_doctor

        return run_doctor()

    if args.command == "bench":
        import json
        from pathlib import Path

        from yuna.bench.runner import RunConfig
        from yuna.bench.runner import run as run_bench

        bench_cfg = RunConfig(
            dataset=Path(args.dataset),
            strategy=args.strategy,
            model=args.model or cfg.models.extractor,
            out_dir=Path(args.out),
            conversations=args.conversations,
            sessions=args.sessions,
            qa=args.qa,
            qa_model=args.qa_model,
            temporal_grounding=not args.no_grounding,
        )
        summary = asyncio.run(run_bench(bench_cfg))
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    parser.error(f"unknown command {args.command}")
    return 2


async def _tts_command(args) -> int:
    from yuna.realtime import tts

    if args.text:
        result = await tts.synthesize(args.text, voice=args.voice, play=not args.no_play)
        return 0 if result else 1

    # Interactive mode
    print("\nKokoro TTS — interactive mode. Type text to synthesize, 'quit' to exit.\n")
    num = 0
    while True:
        try:
            text = input("TTS> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text or text.lower() in ("quit", "exit"):
            break
        if await tts.synthesize(text, response_num=num, voice=args.voice, play=not args.no_play):
            num += 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
