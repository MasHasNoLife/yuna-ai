"""Yuna Web Control Center: memory browser/editor and persona editor.

Security posture (fixes the old dashboard/server.py):
- Binds to 127.0.0.1 by default (was 0.0.0.0).
- The persona editor reads/writes plain-text persona files — the old endpoint
  wrote arbitrary content into an importable .py file (remote code execution).
- Optional bearer auth: set YUNA_DASHBOARD_TOKEN to require it on /api/*.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from yuna.core.config import get_config
from yuna.core.memory import get_store
from yuna.core.persona import FILES as PERSONA_FILES
from yuna.core.persona import persona_file


async def require_token(request: Request):
    token = os.getenv("YUNA_DASHBOARD_TOKEN")
    if token and request.headers.get("Authorization") != f"Bearer {token}":
        raise HTTPException(status_code=401, detail="Missing or invalid dashboard token")


app = FastAPI(title="Yuna Web Control Center", dependencies=[Depends(require_token)])


class MemoryAddRequest(BaseModel):
    username: str
    fact: str


class PromptUpdateRequest(BaseModel):
    content: str


# ── Memory endpoints ────────────────────────────────────────────────────────


@app.get("/api/memories")
def get_memories():
    """All memories in the Discord collection, with their partitions."""
    try:
        return {"memories": get_store("discord").all()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/memories")
def add_memory(req: MemoryAddRequest):
    """Manually inject a fact into a partition."""
    try:
        memory_id = str(uuid.uuid4())
        get_store("discord").collection.add(
            documents=[req.fact],
            metadatas=[{"username": req.username.lower()}],
            ids=[memory_id],
        )
        return {"status": "success", "id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: str):
    try:
        get_store("discord").collection.delete(ids=[memory_id])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


# ── Persona endpoints (plain text, never executable code) ───────────────────


def _validated_persona_path(name: str) -> Path:
    if name not in PERSONA_FILES:
        raise HTTPException(
            status_code=400, detail=f"Unknown persona file '{name}' (valid: {list(PERSONA_FILES)})"
        )
    return persona_file(name)


@app.get("/api/prompt")
def get_prompt(name: str = "system"):
    path = _validated_persona_path(name)
    if not path.exists():
        example = get_config().paths.persona_example / PERSONA_FILES[name]
        content = example.read_text(encoding="utf-8") if example.exists() else ""
    else:
        content = path.read_text(encoding="utf-8")
    return {"content": content, "name": name}


@app.post("/api/prompt")
def update_prompt(req: PromptUpdateRequest, name: str = "system"):
    path = _validated_persona_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(req.content, encoding="utf-8")
    return {"status": "success", "name": name}


# ── Static frontend ─────────────────────────────────────────────────────────

static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
def serve_index():
    return FileResponse(str(static_path / "index.html"))


def run():
    import uvicorn

    cfg = get_config().dashboard
    print(f"Starting Yuna Web Dashboard on http://{cfg.host}:{cfg.port}")
    if not os.getenv("YUNA_DASHBOARD_TOKEN"):
        print("(set YUNA_DASHBOARD_TOKEN to require auth on the API)")
    uvicorn.run(app, host=cfg.host, port=cfg.port)
