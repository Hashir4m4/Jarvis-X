import unittest
import os
import shutil
import tempfile
from unittest.mock import MagicMock, patch

from backend.memory.memory_api import MemoryAPI
from backend.skills.memory_skill import MemorySkill
from backend.core.models import Intent, IntentType, TaskCategory
from backend.orchestrator.decision_engine import DecisionEngine
from backend.memory.memory_models import MemoryDecision, MemoryCategory, MemoryImportance

class TestLongTermMemory(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            "memory_advanced": {
                "vault_path": os.path.join(self.test_dir, "vault"),
                "db_path": os.path.join(self.test_dir, "sqlite.db"),
                "chroma_path": os.path.join(self.test_dir, "chroma"),
                "retrieval_top_k": 3,
                "max_memories": 5
            }
        }
        
        self.memory_api = MemoryAPI(self.config, session_id="test_session")
        self.memory_skill = MemorySkill()
        self.decision_engine = DecisionEngine()
        
        # Mock ChromaManager
        self.memory_api.chroma.enabled = True
        self.memory_store = []
        
        def mock_add(doc_id, text, metadata):
            for i, mem in enumerate(self.memory_store):
                if mem["id"] == doc_id:
                    self.memory_store[i] = {"id": doc_id, "document": text, "metadata": metadata}
                    return
            self.memory_store.append({"id": doc_id, "document": text, "metadata": metadata})
            
        def mock_query(query, n_results):
            results = []
            for mem in self.memory_store:
                if query.lower() in mem["document"].lower() or "python" in query.lower():
                    results.append({"id": mem["id"], "document": mem["document"], "metadata": mem["metadata"], "distance": 0.1})
            return results[:n_results]
            
        def mock_search(query, n_results):
            results = []
            for mem in self.memory_store:
                if query.lower() in mem["document"].lower():
                    results.append({"content": mem["document"], "metadata": mem["metadata"]})
            return results[:n_results]

        self.memory_api.chroma.add_memory = MagicMock(side_effect=mock_add)
        self.memory_api.chroma.query_similar = MagicMock(side_effect=mock_query)
        self.memory_api.chroma.search_memory = MagicMock(side_effect=mock_search)

    def tearDown(self):
        self.memory_api.close()
        shutil.rmtree(self.test_dir)

    def test_01_explicit_memory_creation(self):
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="memory", action="remember", raw_input="Remember that my project is called JARVIS X", parameters={})
        res = self.memory_skill.execute(intent, context={"memory": self.memory_api})
        self.assertTrue(res.success)
        
        results = self.memory_api.search_memory("JARVIS X", limit=1, search_vault=False)
        self.assertTrue(len(results) > 0)
        self.assertIn("my project is called jarvis x", results[0]["content"].lower())

    def test_02_automatic_memory_extraction(self):
        self.memory_api.add_message("user", "Hello")
        res1 = self.memory_api.search_memory("Hello", limit=1, search_vault=False)
        self.assertEqual(len(res1), 0)
        
        self.memory_api.add_message("user", "Remember that my favourite color is blue")
        res2 = self.memory_api.search_memory("favourite color", limit=1, search_vault=False)
        self.assertEqual(len(res2), 1)

    def test_03_memory_retrieval_and_ranking(self):
        self.memory_api.write_memory("Important fact", memory_type="semantic", category="semantic", metadata={"importance": "critical", "confidence": "user_explicit"})
        self.memory_api.write_memory("Low priority fact", memory_type="semantic", category="semantic", metadata={"importance": "low"})
        
        ctx = self.memory_api.get_context("fact")
        context_str = str(ctx)
        self.assertIn("Important fact", context_str)

    def test_04_memory_deletion(self):
        res = self.memory_api.write_memory("I like apples", memory_type="semantic", category="semantic")
        mem_id = res["id"]
        
        # Test delete logic
        self.memory_api.forget_memory(mem_id)
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="memory", action="forget", raw_input="Forget that I like apples", parameters={})
        self.memory_skill.execute(intent, context={"memory": self.memory_api})

    def test_05_duplicate_detection(self):
        self.memory_api.write_memory("user prefers Python 3.11", memory_type="semantic", category="semantic")
        
        self.memory_api.chroma.add_memory.reset_mock()
        self.memory_api._deduplicate_and_save("test_id", "user uses Python 3.13 instead", {"category": "semantic"})
        
        # Should have updated existing memory instead of creating new
        args, _ = self.memory_api.chroma.add_memory.call_args
        self.assertNotEqual(args[0], "test_id")

    def test_06_sensitive_data_redaction(self):
        secret = "sk-xxxxxxxxxxxxxxx"
        content = f"My api key is {secret}"
        self.memory_api.add_message("user", content)
        
        messages = self.memory_api.sqlite.get_recent_messages(self.memory_api.session_id, limit=5)
        self.assertNotIn(secret, messages[-1]["content"])

    def test_07_decision_engine_categorization(self):
        decision = self.decision_engine.should_save_memory(
            TaskCategory.MEMORY_REQUEST, "memory", True, "Remember that JARVIS should prioritize local AI for private tasks."
        )
        self.assertTrue(decision.should_save)
        self.assertEqual(decision.importance, MemoryImportance.CRITICAL)
        self.assertEqual(decision.category, MemoryCategory.SEMANTIC)

        decision2 = self.decision_engine.should_save_memory(
            TaskCategory.QUESTION, None, True, "What's the capital of France?"
        )
        self.assertFalse(decision2.should_save)
        self.assertEqual(decision2.category, MemoryCategory.SHORT_TERM)

if __name__ == '__main__':
    unittest.main()
