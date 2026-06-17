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
    """Save a new fact about the user into the vector database with a username tag."""
    if not fact or not fact.strip():
        return
        
    doc_id = str(uuid.uuid4())
    try:
        collection.add(
            documents=[fact.strip()],
            metadatas=[{"username": username.lower()}],
            ids=[doc_id]
        )
    except Exception as e:
        print(f"\033[91m  [Memory Error] Failed to save fact: {e}\033[0m")

def search_memory(username: str, query: str, n_results=3, collection=default_collection) -> list:
    """Search for relevant past facts based on the current context, strictly filtering by username."""
    if not query or not query.strip():
        return []
        
    if collection.count() == 0:
        return []
        
    actual_n_results = min(n_results, collection.count())
        
    try:
        results = collection.query(
            query_texts=[query],
            n_results=actual_n_results,
            where={"username": username.lower()}
        )
        if results and "documents" in results and results["documents"]:
            return results["documents"][0]
    except Exception as e:
        # Ignore errors if the database is completely empty or search fails
        pass
        
    return []
