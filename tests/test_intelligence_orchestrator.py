import unittest
import asyncio
import os
import sys
import tempfile
import shutil
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock external dependencies for fast deterministic testing
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['pycaw'] = MagicMock()
sys.modules['pycaw.pycaw'] = MagicMock()
sys.modules['comtypes'] = MagicMock()
sys.modules['pyttsx3'] = MagicMock()
sys.modules['faster_whisper'] = MagicMock()
sys.modules['speech_recognition'] = MagicMock()
sys.modules['openwakeword'] = MagicMock()

from backend.core.core import JarvisCore
from backend.core.models import (
    UserInput, InputChannel, ExecutionState, TaskCategory, OperatingState
)
from backend.orchestrator.orchestrator import JarvisOrchestrator
from backend.orchestrator.decision_engine import DecisionEngine
from backend.automation.security_proxy import PermissionLevel


class TestIntelligenceOrchestrator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            "llm": {"provider": "mock", "mock_response": "Mock orchestrator test response."},
            "memory_advanced": {
                "sqlite_db_path": os.path.join(self.test_dir, "test.sqlite"),
                "chroma_db_path": os.path.join(self.test_dir, "chroma"),
                "vault_path": os.path.join(self.test_dir, "vault")
            },
            "voice": {"enabled": True, "wake_word_enabled": False}
        }
        self.core = JarvisCore(self.config, session_id="orchestrator_test_session")
        self.orchestrator = self.core.orchestrator
        self.core.security.confirmation_callback = lambda action, details: True
        await self.core.start()

    async def asyncTearDown(self):
        await self.core.stop()
        self.core.memory.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Simple conversation request
    async def test_01_simple_conversation_request(self):
        user_input = UserInput(content="Hello Jarvis, how are you?", channel=InputChannel.TEXT)
        res = await self.orchestrator.process_request(user_input)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.state, ExecutionState.COMPLETED)
        self.assertEqual(res.skill, "conversation")

    # 2. System command
    async def test_02_system_command(self):
        user_input = UserInput(content="Show my system status.", channel=InputChannel.TEXT)
        res = await self.orchestrator.process_request(user_input)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.skill, "system")
        self.assertIn("System Status", res.response)

    # 3. Memory retrieval request
    async def test_03_memory_retrieval_request(self):
        self.core.memory.add_message("user", "My project codename is PROJECT-HORIZON")
        user_input = UserInput(content="What is my project codename?", channel=InputChannel.TEXT)
        res = await self.orchestrator.process_request(user_input)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.state, ExecutionState.COMPLETED)

    # 4. Skill execution request
    async def test_04_skill_execution_request(self):
        user_input = UserInput(content="Plan today's priorities", channel=InputChannel.TEXT)
        res = await self.orchestrator.process_request(user_input)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.skill, "plan")
        self.assertIn("Daily Execution Plan", res.response)

    # 5. Tool execution request
    async def test_05_tool_execution_request(self):
        user_input = UserInput(content="Set volume to 50", channel=InputChannel.TEXT)
        res = await self.orchestrator.process_request(user_input)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.skill, "system")

    # 6. Agent-based request
    async def test_06_agent_based_request(self):
        user_input = UserInput(content="Build a Python script that parses CSV data", channel=InputChannel.TEXT)
        with patch.object(self.core.agent_manager.planner, "plan", return_value=[{"step_num": 1, "action": "write_file", "file": "csv_parser.py", "description": "Write CSV parser"}]):
            with patch.object(self.core.agent_manager.coder, "generate", return_value="import csv\nprint('parsed')"):
                res = await self.orchestrator.process_request(user_input)
                self.assertEqual(res.status, "success")
                self.assertIn("Multi-agent coding task completed", res.response)

    # 7. Unknown request
    async def test_07_unknown_request(self):
        user_input = UserInput(content="!@#$%^&*()_+ invalid gibberish", channel=InputChannel.TEXT)
        res = await self.orchestrator.process_request(user_input)
        self.assertEqual(res.status, "unknown")
        self.assertIn("did not recognize a valid skill", res.response)

    # 8. Permission-required request
    async def test_08_permission_required_request(self):
        # 8a. Denied confirmation
        self.core.security.confirmation_callback = lambda action, details: False
        user_input = UserInput(content="kill process 1234", channel=InputChannel.TEXT)
        res_denied = await self.orchestrator.process_request(user_input)
        self.assertEqual(res_denied.status, "permission_denied")
        self.assertEqual(res_denied.state, ExecutionState.CANCELLED)
        self.assertIn("cancelled", res_denied.response.lower())

        # 8b. Approved confirmation
        self.core.security.confirmation_callback = lambda action, details: True
        res_approved = await self.orchestrator.process_request(user_input)
        self.assertIn(res_approved.status, ("success", "error"))

    # 9. Failed execution
    async def test_09_failed_execution(self):
        user_input = UserInput(content="Show my system status.", channel=InputChannel.TEXT)
        system_skill = self.core.skill_registry.get("system")
        with patch.object(system_skill, "execute", side_effect=RuntimeError("Hardware sensor fault")):
            res = await self.orchestrator.process_request(user_input)
            self.assertEqual(res.status, "error")
            self.assertEqual(res.state, ExecutionState.FAILED)
            self.assertIn("Hardware sensor fault", res.response)

    # 10. Cancelled execution
    async def test_10_cancelled_execution(self):
        user_input = UserInput(content="Build a complex pipeline", channel=InputChannel.TEXT)
        self.orchestrator.cancel()
        res = await self.orchestrator.process_request(user_input)
        self.assertEqual(res.status, "cancelled")
        self.assertEqual(res.state, ExecutionState.CANCELLED)

    # 11. Request from voice source
    async def test_11_request_from_voice_source(self):
        user_input = UserInput(content="What time is it?", channel=InputChannel.VOICE)
        res = await self.orchestrator.process_request(user_input)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.state, ExecutionState.COMPLETED)

    # 12. Request from scheduler source
    async def test_12_request_from_scheduler_source(self):
        user_input = UserInput(content="Pull metrics report", channel=InputChannel.SCHEDULED)
        res = await self.orchestrator.process_request(user_input)
        self.assertEqual(res.status, "success")
        self.assertEqual(res.skill, "metrics")

    # Decision Engine Classification Unit Tests
    def test_decision_engine_rules(self):
        engine = DecisionEngine()
        self.assertEqual(engine.classify_task("Build a Python script for metrics"), TaskCategory.CODING_TASK)
        self.assertEqual(engine.classify_task("Plan today's tasks"), TaskCategory.PLANNING_TASK)
        self.assertEqual(engine.classify_task("Remember that my PIN is 1234"), TaskCategory.MEMORY_REQUEST)
        self.assertEqual(engine.classify_task("Research the best local LLM options"), TaskCategory.RESEARCH_TASK)
        self.assertEqual(engine.classify_task("Set volume to 80"), TaskCategory.COMPUTER_ACTION)


if __name__ == "__main__":
    unittest.main()
