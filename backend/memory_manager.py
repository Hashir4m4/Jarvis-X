import logging
from typing import List, Dict, Any, Optional

from .memory.memory_api import MemoryAPI

logger = logging.getLogger(__name__)


class MemoryManager(MemoryAPI):
    """
    Unified JARVIS OS Memory Manager (Phase 4 + OS Memory Layer).
    Inherits from MemoryAPI, uniting:
      1. Markdown Vault (vault/raw, vault/wiki, vault/outputs, vault/daily)
      2. SQLite (Short-term/relational memory)
      3. ChromaDB (Long-term semantic vector embeddings)
    """

    def __init__(self, config: Dict[str, Any], session_id: str = "default"):
        super().__init__(config, session_id=session_id)

    def add_message(self, role: str, content: str):
        """
        Adds a message to both short-term SQLite and long-term Chroma vector store.
        Maintains complete backward compatibility with existing codebase.
        """
        # 1. Save to structured SQL database
        msg_id = self.sqlite.add_message(self.session_id, role, content)

        # 2. Save to vector DB for semantic search
        if msg_id != -1 and len(content.strip()) > 10:
            doc_id = f"{self.session_id}_{msg_id}"
            metadata = {"role": role, "session_id": self.session_id}
            self.chroma.add_memory(doc_id, content, metadata)

    def get_context(self, current_query: str = "") -> List[Dict[str, str]]:
        """
        Returns the context combining recent and semantically relevant messages + vault references.
        """
        return self.retrieve_context(current_query, session_id=self.session_id)

    def clear_memory(self):
        """Phase 4 cleanup - retains long-term vectors and vault notes."""
        logger.info(f"Memory clear requested for {self.session_id}. Retaining long-term vectors and vault.")
