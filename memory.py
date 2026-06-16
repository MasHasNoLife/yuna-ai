import os
import uuid
import chromadb
from chromadb.utils import embedding_functions

# Initialize the embedding function to use Ollama's local nomic-embed-text
ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="nomic-embed-text",
)

# Initialize the persistent ChromaDB client
MEMORY_DIR = os.path.join(os.path.dirname(__file__), "yuna_memory")
chroma_client = chromadb.PersistentClient(path=MEMORY_DIR)

# Get or create the collection for user facts
collection = chroma_client.get_or_create_collection(
    name="user_facts",
    embedding_function=ollama_ef
)

def save_memory(username: str, fact: str):
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

def search_memory(username: str, query: str, n_results=3) -> list:
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
