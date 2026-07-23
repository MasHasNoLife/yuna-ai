"""Yuna Web — the conversational interface + control center.

One FastAPI app serving:
  - WS  /ws/chat      streaming chat (JSON events + binary PCM audio frames)
  - POST /api/stt     push-to-talk transcription
  - GET  /api/metrics monitoring snapshot (System tab)
  - GET  /api/health  doctor checks as JSON
  - REST /api/memories, /api/prompt (absorbed from the old dashboard)

Binds to 127.0.0.1 by default; set YUNA_DASHBOARD_TOKEN to require a bearer
token on /api/*.
"""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    HTTPException,
    Request,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from yuna import __version__
from yuna.core.chat_session import ChatSession
from yuna.core.config import get_config
from yuna.core.logging import get_logger
from yuna.core.memory import get_store
from yuna.core.metrics import get_hub
from yuna.core.persona import FILES as PERSONA_FILES
from yuna.core.persona import persona_file
from yuna.tts import backend_names, get_tts_backend

log = get_logger("web")


async def require_token(request: Request):
    token = os.getenv("YUNA_DASHBOARD_TOKEN")
    if token and request.headers.get("Authorization") != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Missing or invalid dashboard token")


# Token guard applies to HTTP /api/* routes only — the websocket checks its
# own ?token= query param (a Request dependency would crash in a WS scope).
app = FastAPI(title="Yuna Web", version=__version__)
api = APIRouter(prefix="/api", dependencies=[Depends(require_token)])


class MemoryAddRequest(BaseModel):
    username: str
    fact: str


class PromptUpdateRequest(BaseModel):
    content: str


# ── Chat websocket ──────────────────────────────────────────────────────────


class WSChat:
    """One connected client: a ChatSession plus TTS/speak options."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.session = ChatSession()
        self.speak = True
        self.tts_name = get_config().tts.backend
        self.busy = False

    async def send_json(self, payload: dict):
        await self.ws.send_json(payload)

    async def pump_out_of_band(self):
        """Forward background events (memory ops) to the client."""
        while True:
            event = await self.session.events.get()
            await self.send_json(event)

    async def speak_reply(self, text: str):
        record = self.session.last_record
        try:
            backend = get_tts_backend(self.tts_name)
            ok, reason = backend.available()
            if not ok:
                await self.send_json(
                    {"type": "tts_unavailable", "backend": self.tts_name, "reason": reason}
                )
                return
            if record:
                record.tts_backend = backend.name
            t0 = time.monotonic()
            sample_rate, stream = backend.synth_stream(text)
            await self.send_json({"type": "audio_start", "sample_rate": sample_rate})
            first = None
            total = 0
            async for chunk in stream:
                if first is None and chunk:
                    first = time.monotonic() - t0
                    if record:
                        record.ttfa_ms = first * 1000
                total += len(chunk)
                await self.ws.send_bytes(chunk)
            if record:
                record.tts_ms = (time.monotonic() - t0) * 1000
                record.audio_bytes = total
            await self.send_json({"type": "audio_end"})
        except Exception as e:
            log.warning("TTS failed (%s): %s", self.tts_name, e)
            await self.send_json(
                {"type": "tts_error", "backend": self.tts_name, "message": str(e)[:200]}
            )

    async def handle_message(self, text: str, source: str = "text"):
        if self.busy:
            await self.send_json({"type": "error", "message": "Still replying — hold on."})
            return
        self.busy = True
        try:
            reply = ""
            async for event in self.session.process(text, source=source):
                if event["type"] == "reply_done":
                    reply = event["text"]
                await self.send_json(event)
            if reply and self.speak:
                await self.speak_reply(reply)
            if self.session.last_record:
                get_hub().finish(self.session.last_record)
                self.session.last_record = None
        finally:
            self.busy = False

    async def handle_control(self, data: dict):
        kind = data.get("type")
        if kind == "user_message":
            text = (data.get("text") or "").strip()
            if text:
                await self.handle_message(text, source=data.get("source", "text"))
        elif kind == "set_options":
            if "speak" in data:
                self.speak = bool(data["speak"])
            if data.get("tts_backend") in backend_names():
                self.tts_name = data["tts_backend"]
            if data.get("llm_backend"):
                try:
                    label = self.session.set_backend(data["llm_backend"])
                    await self.send_json({"type": "backend_changed", "label": label})
                except (ValueError, ConnectionError) as e:
                    await self.send_json({"type": "error", "message": str(e)})
            if "username" in data and data["username"].strip():
                self.session.set_user(data["username"].strip())
            await self.send_json({"type": "options", **self.options()})
        elif kind == "reset":
            await self.session.summarize_session()  # remember this conversation first
            self.session.reset()
            await self.send_json({"type": "reset_done"})

    def options(self) -> dict:
        return {
            "speak": self.speak,
            "tts_backend": self.tts_name,
            "llm_label": self.session.backend.label,
            "username": self.session.username,
        }


@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    token = os.getenv("YUNA_DASHBOARD_TOKEN")
    if token and ws.query_params.get("token") != token:
        await ws.close(code=4401)
        return
    await ws.accept()
    chat = WSChat(ws)
    tts_status = {}
    for name in backend_names():
        ok, reason = get_tts_backend(name).available()
        tts_status[name] = {"available": ok, "reason": reason}
    await chat.send_json(
        {"type": "hello", "version": __version__, "tts_backends": tts_status, **chat.options()}
    )
    pump = asyncio.create_task(chat.pump_out_of_band())
    try:
        while True:
            data = await ws.receive_json()
            await chat.handle_control(data)
    except WebSocketDisconnect:
        pass
    finally:
        pump.cancel()
        try:
            await asyncio.wait_for(chat.session.summarize_session(), timeout=60.0)
        except Exception:
            log.warning("Session summary on disconnect skipped")
        await chat.session.drain(timeout=10.0)
        log.info("Client disconnected")


# ── STT ─────────────────────────────────────────────────────────────────────


@api.post("/stt")
async def transcribe_audio(file: UploadFile):
    from yuna.web.stt import transcribe

    audio = await file.read()
    if len(audio) < 100:
        raise HTTPException(status_code=400, detail="Empty recording")
    suffix = Path(file.filename or "clip.webm").suffix or ".webm"
    text, elapsed_ms = await transcribe(audio, suffix=suffix)
    return {"text": text, "ms": round(elapsed_ms)}


# ── Monitoring / health ─────────────────────────────────────────────────────


@api.get("/metrics")
def metrics():
    return get_hub().snapshot()


@api.get("/health")
async def health():
    from yuna.doctor import collect

    checks = await asyncio.to_thread(collect)
    return {
        "checks": [
            {"name": c.name, "status": c.status, "detail": c.detail, "hint": c.hint} for c in checks
        ]
    }


@api.get("/config")
def config_view():
    cfg = get_config()
    return {
        "llm_backend": cfg.llm.backend,
        "google_model": cfg.llm.google_model,
        "ollama_chat_model": cfg.models.chat,
        "extractor_model": cfg.models.extractor,
        "tts_backend": cfg.tts.backend,
        "stt": f"whisper-{cfg.stt.model} ({cfg.stt.device})",
    }


# ── Memories (absorbed from the old dashboard, now on the main store) ───────


@api.get("/memories")
def get_memories(store: str = "main"):
    try:
        return {"memories": get_store(store).all()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@api.post("/memories")
def add_memory(req: MemoryAddRequest, store: str = "main"):
    try:
        memory_id = str(uuid.uuid4())
        get_store(store).collection.add(
            documents=[req.fact],
            metadatas=[{"username": req.username.lower()}],
            ids=[memory_id],
        )
        return {"status": "success", "id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@api.delete("/memories/{memory_id}")
def delete_memory(memory_id: str, store: str = "main"):
    try:
        get_store(store).collection.delete(ids=[memory_id])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Persona (plain text, never executable code) ─────────────────────────────


def _validated_persona_path(name: str) -> Path:
    if name not in PERSONA_FILES:
        raise HTTPException(
            status_code=400, detail=f"Unknown persona file '{name}' (valid: {list(PERSONA_FILES)})"
        )
    return persona_file(name)


@api.get("/prompt")
def get_prompt(name: str = "system"):
    path = _validated_persona_path(name)
    if not path.exists():
        example = get_config().paths.persona_example / PERSONA_FILES[name]
        content = example.read_text(encoding="utf-8") if example.exists() else ""
    else:
        content = path.read_text(encoding="utf-8")
    return {"content": content, "name": name}


@api.post("/prompt")
def update_prompt(req: PromptUpdateRequest, name: str = "system"):
    path = _validated_persona_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content, encoding="utf-8")
    return {"status": "success", "name": name}


app.include_router(api)


# ── Static frontend ─────────────────────────────────────────────────────────

static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(static_path / "index.html"))


def run():
    import uvicorn

    cfg = get_config().dashboard
    print(f"Yuna Web on http://{cfg.host}:{cfg.port}")
    if not os.getenv("YUNA_DASHBOARD_TOKEN"):
        print("(set YUNA_DASHBOARD_TOKEN in .env to require auth)")
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="warning")
