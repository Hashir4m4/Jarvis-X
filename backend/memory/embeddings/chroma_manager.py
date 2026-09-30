import logging
import os

try:
    import chromadb
    from chromadb.config import Settings
except ImportError:
    chromadb = None

logger = logging.getLogger(__name__)

class ChromaManager:
    def __init__(self, config: dict):
        self.enabled = chromadb is not None
        if not self.enabled:
            logger.warning("chromadb package not found. Vector memory disabled.")
            return

        self.db_path = config.get("chroma_db_path", "memory/database_storage/chroma")
        
        # Ensure directory exists
        db_dir = os.path.abspath(self.db_path)
        os.makedirs(db_dir, exist_ok=True)
        
        try:
            self.client = chromadb.PersistentClient(path=db_dir)
            # Default collection for conversation history
            self.collection = self.client.get_or_create_collection(
                name="conversations",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("ChromaDB initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.enabled = False

    def add_memory(self, doc_id: str, text: str, metadata: dict = None):
        if not self.enabled:
            return
            
        try:
            self.collection.add(
                documents=[text],
                metadatas=[metadata] if metadata else [{}],
                ids=[doc_id]
            )
        except Exception as e:
            logger.error(f"Failed to add memory to Chroma: {e}")

    def search_memory(self, query: str, n_results: int = 3) -> list:
        if not self.enabled:
            return []
            
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            
            # Extract and format the results
            memories = []
            if results and results['documents'] and len(results['documents']) > 0:
                for idx, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][idx] if results['metadatas'] else {}
                    memories.append({"content": doc, "metadata": metadata})
                    
            return memories
        except Exception as e:
            logger.error(f"Error searching Chroma: {e}")
            return []

    def query_similar(self, query: str, n_results: int = 3) -> list:
        if not self.enabled:
            return []
            
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            
            memories = []
            if results and results.get('documents') and len(results['documents']) > 0:
                for idx, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][idx] if results.get('metadatas') else {}
                    doc_id = results['ids'][0][idx] if results.get('ids') else None
                    distance = results['distances'][0][idx] if results.get('distances') else 0.0
                    memories.append({
                        "id": doc_id,
                        "document": doc,
                        "metadata": metadata,
                        "distance": distance
                    })
            return memories
        except Exception as e:
            logger.error(f"Error querying Chroma: {e}")
            return []
