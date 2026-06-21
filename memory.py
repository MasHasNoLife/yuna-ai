import os
import uuid
import chromadb
from chromadb.utils import embedding_functions

# Initialize the embedding function to use Ollama's local nomic-embed-text
ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text",
)

# Keep a cache of collections to avoid re-initializing
_collections = {}

# ── ANSI colors ─────────────────────────────────────────────────────────────
GRAY = "\033[90m"
RED  = "\033[91m"
RESET = "\033[0m"

def get_collection(db_name="yuna_memory"):
    if db_name in _collections:
        return _collections[db_name]
        
    memory_dir = os.path.join(os.path.dirname(__file__), db_name)
    chroma_client = chromadb.PersistentClient(path=memory_dir)
    collection = chroma_client.get_or_create_collection(
        name="user_facts",
        embedding_function=ollama_ef
    )
    _collections[db_name] = collection
    return collection

# Default collection for yuna.py to maintain backward compatibility
default_collection = get_collection()

def save_memory(username: str, fact: str, collection=default_collection):
    """Save a new fact about the user into the vector database with a username tag.
    Checks for duplicate/near-duplicate memories before inserting."""
    if not fact or not fact.strip():
        return
    
    fact = fact.strip()
    
    # Deduplication: check if a very similar memory already exists
    try:
        if collection.count() > 0:
            existing = collection.query(
                query_texts=[fact],
                n_results=1,
                where={"username": username.lower()}
            )
            if existing and existing["distances"] and existing["distances"][0]:
                # ChromaDB uses L2 distance — lower = more similar
                # A distance under 0.05 means the memories are nearly identical
                if existing["distances"][0][0] < 0.05:
                    print(f"\033[90m  [Memory] Skipped duplicate: {fact[:60]}...\033[0m")
                    return
    except Exception:
        pass  # If dedup check fails, just save anyway
        
    doc_id = str(uuid.uuid4())
    try:
        collection.add(
            documents=[fact],
            metadatas=[{"username": username.lower()}],
            ids=[doc_id]
        )
    except Exception as e:
        pass

def search_memory(username: str, query: str, n_results=2, collection=default_collection) -> str:
    """Search for relevant past facts based on the current context, strictly filtering by username.
    Returns a clean string of memories, or empty string if nothing relevant is found."""
    if not query or not query.strip():
        return ""
        
    if collection.count() == 0:
        return ""
        
    actual_n_results = min(n_results, collection.count())
        
    try:
        results = collection.query(
            query_texts=[query],
            n_results=actual_n_results,
            where={"username": username.lower()},
            include=["documents", "distances"]
        )
        if results and results["documents"] and results["documents"][0]:
            relevant = []
            for doc, dist in zip(results["documents"][0], results["distances"][0]):
                if dist < 0.35:  # Tightened threshold significantly to prevent generic phrases from pulling up facts
                    relevant.append(doc)
            
            if relevant:
                return " | ".join(relevant)
    except Exception as e:
        # Ignore errors if the database is completely empty or search fails
        pass
        
    return ""

def delete_memory(username: str, query: str, collection=default_collection):
    """Find the closest matching memory and delete it permanently."""
    if not query or not query.strip():
        return
        
    if collection.count() == 0:
        return
        
    try:
        results = collection.query(
            query_texts=[query],
            n_results=1,
            where={"username": username.lower()},
            include=["documents", "distances"]
        )
        if results and results["documents"] and results["documents"][0]:
            if results["distances"][0][0] < 0.6:
                doc_to_delete = results["documents"][0][0]
                doc_id = results["ids"][0][0]
                collection.delete(ids=[doc_id])
                print(f"\033[91m  [Memory Deleted]\033[0m {doc_to_delete}")
    except Exception as e:
        pass
