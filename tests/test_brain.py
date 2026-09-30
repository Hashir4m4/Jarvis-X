import unittest
import sys
import os
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock chromadb since MemoryManager now imports it
sys.modules['chromadb'] = MagicMock()

from backend.brain import Brain

class TestBrain(unittest.TestCase):
    def setUp(self):
        self.config = {
            "llm": {
                "provider": "test",
                "system_prompt": "Test persona"
            },
            "memory": {
                "max_context_messages": 5
            },
            "memory_advanced": {
                "sqlite_db_path": ":memory:",
                "chroma_db_path": "mock",
                "embedding_model": "mock",
                "retrieval_top_k": 2
            }
        }
        self.brain = Brain(self.config, "test_brain_session")

    def test_initialization(self):
        self.assertTrue(self.brain.system_prompt.startswith("Test persona"))

    def tearDown(self):
        self.brain.memory.close()

if __name__ == "__main__":
    unittest.main()
