import sys
import os
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# Allow importing from parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from memory import get_collection, default_collection

app = FastAPI(title="Yuna Web Control Center")

# --- Models ---
class MemoryAddRequest(BaseModel):
    username: str
    fact: str

class PromptUpdateRequest(BaseModel):
    content: str

# --- Endpoints ---

@app.get("/api/memories")
def get_memories():
    """Retrieve all memories from the discord collection, grouped by username."""
    try:
        col = get_collection("discord/discord_memory")
        data = col.get()
        memories = []
        if data and data.get("ids"):
            for i in range(len(data["ids"])):
                memories.append({
                    "id": data["ids"][i],
                    "fact": data["documents"][i],
                    "username": data["metadatas"][i].get("username", "global")
                })
        return {"memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/memories")
def add_memory(req: MemoryAddRequest):
    """Manually inject a fact into a specific partition."""
    try:
        col = get_collection("discord/discord_memory")
        memory_id = str(uuid.uuid4())
        col.add(
            documents=[req.fact],
            metadatas=[{"username": req.username.lower()}],
            ids=[memory_id]
        )
        return {"status": "success", "id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: str):
    """Delete a specific memory by ID."""
    try:
        col = get_collection("discord/discord_memory")
        col.delete(ids=[memory_id])
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/prompt")
def get_prompt():
    """Read the current yuna_prompt.py file."""
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "yuna_prompt.py")
    try:
        with open(prompt_path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/prompt")
def update_prompt(req: PromptUpdateRequest):
    """Overwrite the yuna_prompt.py file."""
    prompt_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "yuna_prompt.py")
    try:
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(req.content)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files for the frontend
static_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(static_path, "index.html"))

if __name__ == "__main__":
    print("Starting Yuna Web Dashboard on http://localhost:8000")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
