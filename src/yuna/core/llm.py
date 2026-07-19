"""Thin Ollama client wrapper: connection checks and retry with backoff.

Every pipeline talks to Ollama through this module instead of instantiating
`ollama.AsyncClient` directly, so connection policy lives in one place.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import ollama

from yuna.core.config import get_config
from yuna.core.logging import get_logger

log = get_logger("llm")

_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds: 1, 2, 4


def get_client() -> ollama.AsyncClient:
    return ollama.AsyncClient(host=get_config().endpoints.ollama_url)


def _with_num_ctx(options: dict) -> dict:
    """Every Ollama call must use the SAME num_ctx: a different value spawns a
    new runner, which is a full ~8s model reload. Chat passed 8192 while
    extraction used the default 4096 — the model reloaded twice per turn."""
    options.setdefault("num_ctx", get_config().sampling.num_ctx)
    return options


async def check_model(client: ollama.AsyncClient, model: str) -> bool:
    """True if Ollama is reachable and `model` is pulled."""
    try:
        model_list = await client.list()
    except Exception as e:
        log.error("Cannot connect to Ollama: %s", e)
        return False
    available = [m.model for m in model_list.models]
    if not any(model in m for m in available):
        log.error("Model '%s' not found. Run: ollama pull %s", model, model)
        return False
    return True


async def chat(client: ollama.AsyncClient, model: str, messages: list[dict], **options) -> str:
    """Non-streaming chat completion with retries. Returns the reply text."""
    last_error: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            response = await client.chat(
                model=model,
                messages=messages,
                options=_with_num_ctx(options),
                think=get_config().llm.think,
            )
            return response["message"]["content"]
        except Exception as e:
            last_error = e
            delay = _BACKOFF_BASE * (2**attempt)
            log.warning("Ollama chat failed (attempt %d/%d): %s", attempt + 1, _RETRIES, e)
            if attempt < _RETRIES - 1:
                await asyncio.sleep(delay)
    raise ConnectionError(f"Ollama chat failed after {_RETRIES} attempts: {last_error}")


async def chat_stream(
    client: ollama.AsyncClient, model: str, messages: list[dict], **options
) -> AsyncIterator[str]:
    """Streaming chat completion. Retries only the initial connection —
    once tokens flow, a mid-stream error propagates (retrying would replay text).
    """
    last_error: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            stream = await client.chat(
                model=model,
                messages=messages,
                stream=True,
                options=_with_num_ctx(options),
                think=get_config().llm.think,
            )
            break
        except Exception as e:
            last_error = e
            log.warning("Ollama stream failed (attempt %d/%d): %s", attempt + 1, _RETRIES, e)
            if attempt < _RETRIES - 1:
                await asyncio.sleep(_BACKOFF_BASE * (2**attempt))
    else:
        raise ConnectionError(f"Ollama stream failed after {_RETRIES} attempts: {last_error}")

    async for chunk in stream:
        yield chunk["message"].get("content", "")
