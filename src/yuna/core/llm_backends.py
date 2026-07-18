"""Pluggable chat LLM backends.

The primary path is local Ollama; the secondary path is the Google AI API
(Gemma 4 / Gemini models, GOOGLE_API_KEY in .env). Both stream `Chunk`s:
normal text plus optional `thought` chunks (Gemma 4 emits reasoning parts,
which belong in the monitoring feed, never in Yuna's mouth).
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from yuna.core.config import get_config
from yuna.core.logging import get_logger

log = get_logger("llm.backend")

_RETRIES = 3
_BACKOFF_BASE = 1.0

GOOGLE_BASE = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class Chunk:
    text: str
    thought: bool = False


def to_google_contents(messages: list[dict]) -> list[dict]:
    """Convert OpenAI-style messages to Gemini API `contents`.

    Gemma models don't support systemInstruction, so system messages are
    folded into the first user turn. Pure function (unit-tested).
    """
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    system_text = "\n\n".join(system_parts)

    contents: list[dict] = []
    for msg in messages:
        if msg["role"] == "system":
            continue
        role = "model" if msg["role"] == "assistant" else "user"
        text = msg["content"]
        if system_text and role == "user" and not contents:
            text = f"[SYSTEM INSTRUCTIONS]\n{system_text}\n[END SYSTEM INSTRUCTIONS]\n\n{text}"
        contents.append({"role": role, "parts": [{"text": text}]})

    # Edge case: history starts with an assistant turn (or is system-only)
    if system_text and (not contents or contents[0]["role"] != "user"):
        contents.insert(
            0,
            {
                "role": "user",
                "parts": [
                    {"text": f"[SYSTEM INSTRUCTIONS]\n{system_text}\n[END SYSTEM INSTRUCTIONS]"}
                ],
            },
        )
    return contents


def google_generation_config(options: dict) -> dict:
    """Map our sampling options onto the Gemini API's generationConfig."""
    out = {}
    if "temperature" in options:
        out["temperature"] = options["temperature"]
    if "top_p" in options:
        out["topP"] = options["top_p"]
    # repeat_penalty has no Gemini API equivalent — dropped intentionally
    return out


class OllamaBackend:
    """Local Ollama (the primary path)."""

    name = "ollama"

    def __init__(self, model: str | None = None):
        import ollama

        cfg = get_config()
        self.model = model or cfg.models.chat
        self.client = ollama.AsyncClient(host=cfg.endpoints.ollama_url)

    @property
    def label(self) -> str:
        return f"ollama/{self.model}"

    async def chat(self, messages: list[dict], **options) -> str:
        from yuna.core import llm

        return await llm.chat(self.client, self.model, messages, **options)

    async def chat_stream(self, messages: list[dict], **options) -> AsyncIterator[Chunk]:
        from yuna.core import llm

        async for text in llm.chat_stream(self.client, self.model, messages, **options):
            yield Chunk(text)


class GoogleBackend:
    """Google AI API (Gemma 4 / Gemini). Secondary path — needs GOOGLE_API_KEY."""

    name = "google"

    def __init__(self, model: str | None = None):
        self.model = model or get_config().llm.google_model
        self._client: httpx.AsyncClient | None = None

    @property
    def label(self) -> str:
        return f"google/{self.model}"

    @property
    def api_key(self) -> str:
        key = os.getenv("GOOGLE_API_KEY", "")
        if not key:
            raise ConnectionError("GOOGLE_API_KEY not set in .env")
        return key

    def _http(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0))
        return self._client

    async def chat(self, messages: list[dict], **options) -> str:
        body = {"contents": to_google_contents(messages)}
        gen_cfg = google_generation_config(options)
        if gen_cfg:
            body["generationConfig"] = gen_cfg

        last_error: Exception | None = None
        for attempt in range(_RETRIES):
            try:
                r = await self._http().post(
                    f"{GOOGLE_BASE}/models/{self.model}:generateContent",
                    headers={"x-goog-api-key": self.api_key},
                    json=body,
                )
                r.raise_for_status()
                parts = r.json()["candidates"][0]["content"]["parts"]
                return "".join(p.get("text", "") for p in parts if not p.get("thought"))
            except Exception as e:
                last_error = e
                log.warning("Google chat failed (attempt %d/%d): %s", attempt + 1, _RETRIES, e)
                if attempt < _RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_BASE * (2**attempt))
        raise ConnectionError(f"Google chat failed after {_RETRIES} attempts: {last_error}")

    async def chat_stream(self, messages: list[dict], **options) -> AsyncIterator[Chunk]:
        body = {"contents": to_google_contents(messages)}
        gen_cfg = google_generation_config(options)
        if gen_cfg:
            body["generationConfig"] = gen_cfg

        last_error: Exception | None = None
        for attempt in range(_RETRIES):
            try:
                async with self._http().stream(
                    "POST",
                    f"{GOOGLE_BASE}/models/{self.model}:streamGenerateContent?alt=sse",
                    headers={"x-goog-api-key": self.api_key},
                    json=body,
                ) as resp:
                    if resp.status_code != 200:
                        detail = (await resp.aread()).decode(errors="replace")[:300]
                        raise ConnectionError(f"HTTP {resp.status_code}: {detail}")
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload = json.loads(line[6:])
                        candidates = payload.get("candidates") or []
                        if not candidates:
                            continue
                        for part in candidates[0].get("content", {}).get("parts", []):
                            text = part.get("text", "")
                            if text:
                                yield Chunk(text, thought=bool(part.get("thought")))
                return
            except (httpx.HTTPError, ConnectionError) as e:
                last_error = e
                log.warning("Google stream failed (attempt %d/%d): %s", attempt + 1, _RETRIES, e)
                if attempt < _RETRIES - 1:
                    await asyncio.sleep(_BACKOFF_BASE * (2**attempt))
        raise ConnectionError(f"Google stream failed after {_RETRIES} attempts: {last_error}")


BACKENDS = {"ollama": OllamaBackend, "google": GoogleBackend}


def get_backend(name: str | None = None, model: str | None = None):
    """Backend instance by name (default from config.llm.backend)."""
    name = name or get_config().llm.backend
    if name not in BACKENDS:
        raise ValueError(f"Unknown LLM backend '{name}' (have: {list(BACKENDS)})")
    return BACKENDS[name](model=model)
