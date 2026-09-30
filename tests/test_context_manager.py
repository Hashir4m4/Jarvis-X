import unittest
import time
from backend.memory.context_manager import ContextManager, TaskStatus
from backend.core.models import TaskCategory

class TestContextManager(unittest.TestCase):

    def setUp(self):
        self.cm = ContextManager({"context_max_history_turns": 3, "context_max_results": 2})
        self.session_id = "test_session_123"

    def test_01_missing_session_creates_new(self):
        """Scenario 14: Missing session"""
        prep = self.cm.prepare_context("hello", self.session_id)
        self.assertIn("history_window", prep)
        self.assertEqual(len(prep["history_window"]), 0)

    def test_02_basic_history_update(self):
        self.cm.update_context(self.session_id, "hello", "success", "hi there", TaskCategory.CONVERSATION)
        prep = self.cm.prepare_context("next message", self.session_id)
        self.assertEqual(len(prep["history_window"]), 2)
        self.assertEqual(prep["history_window"][0]["role"], "user")
        self.assertEqual(prep["history_window"][1]["role"], "assistant")

    def test_03_active_task_creation_and_completion(self):
        """Scenarios 4, 5: Active task lifecycle"""
        # Start task
        self.cm.update_context(self.session_id, "research startups", "success", "working on it", TaskCategory.RESEARCH_TASK)
        prep = self.cm.prepare_context("what did you find?", self.session_id)
        
        self.assertIsNotNone(prep["active_task"])
        self.assertEqual(prep["active_task"]["task_type"], TaskCategory.RESEARCH_TASK)
        self.assertEqual(prep["active_task"]["status"], TaskStatus.ACTIVE)

        # Complete task
        self.cm.update_context(self.session_id, "what did you find?", "success", "here is the completed research", TaskCategory.RESEARCH_TASK)
        session = self.cm.sessions[self.session_id]
        self.assertEqual(session.active_task.status, TaskStatus.COMPLETED)

    def test_04_active_task_cancellation(self):
        """Scenario 6: Cancelled task"""
        self.cm.update_context(self.session_id, "write a book", "success", "starting", TaskCategory.MULTI_STEP_TASK)
        self.cm.update_context(self.session_id, "stop", "cancelled", "stopping", TaskCategory.MULTI_STEP_TASK)
        session = self.cm.sessions[self.session_id]
        self.assertEqual(session.active_task.status, TaskStatus.CANCELLED)

    def test_05_reference_resolution_single(self):
        """Scenario 1: Follow-up reference ('Make it shorter')"""
        # Inject a result
        data = {"plan": "long plan"}
        self.cm.update_context(self.session_id, "create plan", "success", "here it is", TaskCategory.PLANNING_TASK, data)
        
        prep = self.cm.prepare_context("make it shorter", self.session_id)
        self.assertIn("[context: the generated document]", prep["resolved_input"])
        self.assertFalse(prep["requires_clarification"])

    def test_06_reference_resolution_ambiguous(self):
        """Scenario 3: Ambiguous reference requiring clarification"""
        # Inject two results
        self.cm.update_context(self.session_id, "create doc 1", "success", "done", TaskCategory.COMMAND, {"file": "doc1.txt"})
        self.cm.update_context(self.session_id, "create doc 2", "success", "done", TaskCategory.COMMAND, {"file": "doc2.txt"})
        
        # We now have two results in recent_results. A raw "Open it" should trigger ambiguity.
        prep = self.cm.prepare_context("open it", self.session_id)
        self.assertTrue(prep["requires_clarification"])
        self.assertEqual(prep["resolved_input"], self.cm.AMBIGUOUS_MARKER)

    def test_07_context_compression(self):
        """Scenario 7: Long conversation context compression"""
        # Limit is 3 turns (6 messages). We add 5 turns (10 messages).
        for i in range(5):
            self.cm.update_context(self.session_id, f"q{i}", "success", f"a{i}")
            
        prep = self.cm.prepare_context("test", self.session_id)
        # Should be truncated to max_history_turns * 2 (3 * 2 = 6 messages)
        self.assertEqual(len(prep["history_window"]), 6)
        
    def test_08_privacy_redaction(self):
        """Scenario 10, 11: Privacy protections in history"""
        # Test that secrets are scrubbed before entering history
        self.cm.update_context(self.session_id, "my password: Password123!", "success", "got it")
        prep = self.cm.prepare_context("next", self.session_id)
        last_input = prep["history_window"][-2]["content"]
        self.assertNotIn("Password123!", last_input)
        self.assertIn("[REDACTED_SECRET]", last_input)

    def test_09_multi_source(self):
        """Scenarios 12, 13: Context from voice/HUD sources"""
        # In this implementation, sessions are keyed by session_id, regardless of source.
        self.cm.update_context("session_v", "hello from voice", "success", "hi")
        self.cm.update_context("session_h", "hello from hud", "success", "hi")
        self.assertIn("session_v", self.cm.sessions)
        self.assertIn("session_h", self.cm.sessions)

if __name__ == '__main__':
    unittest.main()
