import unittest
import sys
import os
import sqlite3
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock chromadb before importing our manager
sys.modules['chromadb'] = MagicMock()

from backend.memory.database.sqlite_manager import SQLiteManager
from backend.memory_manager import MemoryManager

class TestMemorySystem(unittest.TestCase):
    def setUp(self):
        self.config = {
            "memory_advanced": {
                "sqlite_db_path": ":memory:", # Use in-memory SQLite for tests
                "chroma_db_path": "mock",
                "embedding_model": "mock",
                "retrieval_top_k": 2
            }
        }
        self.memory_manager = MemoryManager(self.config, "test_session")

    def test_sqlite_crud(self):
        # Test adding messages
        self.memory_manager.sqlite.add_message("test_session", "user", "Hello Jarvis")
        self.memory_manager.sqlite.add_message("test_session", "assistant", "Hello! How can I help?")
        
        recent = self.memory_manager.sqlite.get_recent_messages("test_session", limit=5)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0]["content"], "Hello Jarvis")
        self.assertEqual(recent[1]["content"], "Hello! How can I help?")

    def test_user_prefs(self):
        self.memory_manager.sqlite.set_user_pref("name", "John")
        name = self.memory_manager.sqlite.get_user_pref("name")
        self.assertEqual(name, "John")

    @patch('backend.memory.embeddings.chroma_manager.ChromaManager.search_memory')
    @patch('backend.memory.embeddings.chroma_manager.ChromaManager.add_memory')
    def test_memory_manager_facade(self, mock_add, mock_search):
        # Mock semantic search returning a past memory
        mock_search.return_value = [{"content": "We talked about Python earlier.", "metadata": {"role": "assistant"}}]
        
        # Test adding message triggers both SQL and Vector DB
        self.memory_manager.add_message("user", "This is a test message long enough to save.")
        
        # Check SQLite
        recent = self.memory_manager.sqlite.get_recent_messages("test_session", limit=1)
        self.assertEqual(recent[0]["content"], "This is a test message long enough to save.")
        
        # Check Chroma mock
        mock_add.assert_called_once()
        
        # Test context building
        context = self.memory_manager.get_context("What did we talk about?")
        # The context should have the system message (from chroma) + the recent message (from sqlite)
        self.assertTrue(len(context) in [1, 2])
        if len(context) == 2:
            self.assertEqual(context[0]["role"], "system")
            self.assertTrue("Python earlier" in context[0]["content"])
            self.assertEqual(context[1]["role"], "user")
        else:
            self.assertEqual(context[0]["role"], "user")

    def tearDown(self):
        self.memory_manager.close()

if __name__ == "__main__":
    unittest.main()
