"""ChromaDB-backed long-term memory with local Ollama embeddings.

Replaces the old root-level memory.py. Differences:
- No import-time side effects: clients/collections are created lazily.
- Config-driven paths and thresholds.
- Errors are logged instead of silently swallowed.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from yuna.core.config import get_config
from yuna.core.logging import get_logger

log = get_logger("memory")


class MemoryStore:
    """One vector collection of facts, partitioned by a `username` metadata tag."""

    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self._collection = None

    @property
    def collection(self):
        if self._collection is None:
            import chromadb
            from chromadb.utils import embedding_functions

            cfg = get_config()
            embed = embedding_functions.OllamaEmbeddingFunction(
                url=f"{cfg.endpoints.ollama_url}/api/embeddings",
                model_name=cfg.models.embedding,
            )
            self.db_path.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(self.db_path))
            self._collection = client.get_or_create_collection(
                name="user_facts", embedding_function=embed
            )
        return self._collection

    # ── Operations ──────────────────────────────────────────────────────────

    def save(self, username: str, fact: str) -> bool:
        """Insert a fact unless a near-duplicate already exists in the partition."""
        if not fact or not fact.strip():
            return False
        fact = fact.strip()
        cfg = get_config().memory

        try:
            if self.collection.count() > 0:
                existing = self.collection.query(
                    query_texts=[fact], n_results=1, where={"username": username.lower()}
                )
                distances = existing.get("distances") or [[]]
                if distances[0] and distances[0][0] < cfg.dedup_threshold:
                    log.debug("Skipped duplicate memory: %s", fact[:60])
                    return False
        except Exception:
            log.exception("Memory dedup check failed; saving anyway")

        try:
            self.collection.add(
                documents=[fact],
                metadatas=[{"username": username.lower()}],
                ids=[str(uuid.uuid4())],
            )
            return True
        except Exception:
            log.exception("Failed to save memory: %s", fact[:60])
            return False

    def search(self, username: str, query: str, n_results: int | None = None) -> str:
        """Relevant facts for `query` joined with ' | ', or '' if none pass the threshold."""
        if not query or not query.strip():
            return ""
        cfg = get_config().memory
        n = n_results or cfg.n_results

        try:
            count = self.collection.count()
            if count == 0:
                return ""
            results = self.collection.query(
                query_texts=[query],
                n_results=min(n, count),
                where={"username": username.lower()},
                include=["documents", "distances"],
            )
            docs = (results.get("documents") or [[]])[0]
            dists = (results.get("distances") or [[]])[0]
            relevant = [
                doc for doc, dist in zip(docs, dists, strict=False) if dist < cfg.recall_threshold
            ]
            return " | ".join(relevant)
        except Exception:
            log.exception("Memory search failed")
            return ""

    def delete(self, username: str, query: str) -> bool:
        """Delete the single closest memory to `query` if it's close enough."""
        if not query or not query.strip():
            return False
        cfg = get_config().memory

        try:
            if self.collection.count() == 0:
                return False
            results = self.collection.query(
                query_texts=[query],
                n_results=1,
                where={"username": username.lower()},
                include=["documents", "distances"],
            )
            docs = (results.get("documents") or [[]])[0]
            dists = (results.get("distances") or [[]])[0]
            if docs and dists[0] < cfg.delete_threshold:
                self.collection.delete(ids=[results["ids"][0][0]])
                log.info("Deleted memory: %s", docs[0])
                return True
            return False
        except Exception:
            log.exception("Memory delete failed")
            return False

    def all(self) -> list[dict]:
        """Every fact with id/username, for the dashboard."""
        data = self.collection.get()
        out = []
        for i, doc_id in enumerate(data.get("ids") or []):
            out.append(
                {
                    "id": doc_id,
                    "fact": data["documents"][i],
                    "username": (data["metadatas"][i] or {}).get("username", "global"),
                }
            )
        return out


# ── Store singletons ────────────────────────────────────────────────────────

_stores: dict[str, MemoryStore] = {}


def get_store(name: str = "main") -> MemoryStore:
    """'main' → data/memory, 'discord' → data/discord_memory."""
    if name not in _stores:
        paths = get_config().paths
        db = paths.memory if name == "main" else paths.discord_memory
        _stores[name] = MemoryStore(db)
    return _stores[name]
