"""ChromaDB-backed long-term memory with local Ollama embeddings.

Replaces the old root-level memory.py. Differences:
- No import-time side effects: clients/collections are created lazily.
- Config-driven paths and thresholds.
- Errors are logged instead of silently swallowed.
"""

from __future__ import annotations

import re
import time
import uuid
from pathlib import Path

from yuna.core.config import get_config
from yuna.core.logging import get_logger

log = get_logger("memory")

_DAY = 86400
# An event whose text already carries an absolute date (a 4-digit year) must NOT
# also get a wall-clock age prefix — the two can contradict. In live chat an
# event is timestamped when written (e.g. today), but its content date (from
# temporal grounding) can be earlier, which would render "(earlier today) … last
# spoke (on 19 July 2026)". The written date is authoritative; skip the prefix.
_HAS_ABS_DATE = re.compile(r"\b(?:19|20)\d{2}\b")


def format_age(ts: float | None, now: float | None = None) -> str:
    """Human age of a memory: '' (fresh/unknown), 'yesterday', '3 days ago', ..."""
    if not ts:
        return ""
    now = now or time.time()
    days = int((now - ts) // _DAY)
    if days <= 0:
        return "earlier today"
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    if days < 60:
        return f"{days // 7} weeks ago"
    return f"{days // 30} months ago"


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

    def save(self, username: str, fact: str, kind: str = "fact", ts: float | None = None) -> bool:
        """Insert a fact unless a near-duplicate already exists in the partition.

        kind: 'fact' (durable truth), 'event' (dated happening), 'session'
        (conversation summary). Everything is timestamped for age-aware recall;
        pass `ts` to backdate (bench stamps session dates, not ingest time).
        """
        if not fact or not fact.strip():
            return False
        fact = fact.strip()
        from yuna.core import safety

        if safety.is_blocked(fact):
            log.warning("Refused to store blocked content: %s", fact[:40])
            return False
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
                metadatas=[{"username": username.lower(), "kind": kind, "ts": ts or time.time()}],
                ids=[str(uuid.uuid4())],
            )
            return True
        except Exception:
            log.exception("Failed to save memory: %s", fact[:60])
            return False

    def search(self, username: str, query: str, n_results: int | None = None) -> str:
        """Relevant facts for `query` joined with ' | ', or '' if none pass the threshold.

        Events and session summaries are prefixed with their age — "(3 days ago) ..." —
        so the model can talk about time like a person instead of an eternal present.
        """
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
                include=["documents", "distances", "metadatas"],
            )
            docs = (results.get("documents") or [[]])[0]
            dists = (results.get("distances") or [[]])[0]
            metas = (results.get("metadatas") or [[]])[0]
            relevant = []
            for doc, dist, meta in zip(docs, dists, metas, strict=False):
                if dist >= cfg.recall_threshold:
                    continue
                meta = meta or {}
                if meta.get("kind") in ("event", "session"):
                    age = format_age(meta.get("ts"))
                    if age and not _HAS_ABS_DATE.search(doc):
                        doc = f"({age}) {doc}"
                relevant.append(doc)
            return " | ".join(relevant)
        except Exception:
            log.exception("Memory search failed")
            return ""

    def profile(self, username: str, limit: int = 8) -> list[str]:
        """The newest durable facts in a partition (Yuna's self-knowledge, or a
        user's core profile). Injected every turn regardless of query relevance."""
        try:
            data = self.collection.get(where={"username": username.lower()})
        except Exception:
            log.exception("Memory profile fetch failed")
            return []
        rows = []
        for doc, meta in zip(
            data.get("documents") or [], data.get("metadatas") or [], strict=False
        ):
            meta = meta or {}
            if meta.get("kind", "fact") == "fact":
                rows.append((meta.get("ts", 0), doc))
        rows.sort(reverse=True)
        return [doc for _, doc in rows[:limit]]

    def latest_summary(self, username: str) -> tuple[str, float] | None:
        """Most recent session summary for a partition: (text, ts) or None."""
        try:
            data = self.collection.get(where={"username": username.lower()})
        except Exception:
            log.exception("Memory summary fetch failed")
            return None
        best: tuple[float, str] | None = None
        for doc, meta in zip(
            data.get("documents") or [], data.get("metadatas") or [], strict=False
        ):
            meta = meta or {}
            if meta.get("kind") == "session":
                ts = meta.get("ts", 0)
                if best is None or ts > best[0]:
                    best = (ts, doc)
        return (best[1], best[0]) if best else None

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
            meta = data["metadatas"][i] or {}
            out.append(
                {
                    "id": doc_id,
                    "fact": data["documents"][i],
                    "username": meta.get("username", "global"),
                    "kind": meta.get("kind", "fact"),
                    "ts": meta.get("ts"),
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
