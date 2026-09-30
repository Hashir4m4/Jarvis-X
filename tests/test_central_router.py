import unittest
import asyncio
import os
import sys
import tempfile
import shutil
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock external heavy dependencies
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['pycaw'] = MagicMock()
sys.modules['pycaw.pycaw'] = MagicMock()
sys.modules['comtypes'] = MagicMock()

from backend.core.models import UserInput, InputChannel, IntentType
from backend.router.context import ExecutionContext, RouterExecutionResult
from backend.router.intent_router import IntentRouter
from backend.router.central_router import CentralRouter
from backend.router.tool_registry import ToolRegistry
from backend.skills.registry import SkillRegistry
from backend.skills.system_skill import SystemSkill
from backend.skills.metrics_skill import MetricsSkill
from backend.skills.plan_skill import PlanSkill
from backend.skills.vault_skill import VaultSkill
from backend.skills.trends_skill import TrendsSkill
from backend.skills.inbox_skill import InboxSkill
from backend.skills.conversation_skill import ConversationSkill
from backend.skills.memory_skill import MemorySkill
from backend.memory.memory_api import MemoryAPI


class TestCentralRouter(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            "memory_advanced": {
                "sqlite_db_path": os.path.join(self.test_dir, "test.sqlite"),
                "chroma_db_path": os.path.join(self.test_dir, "chroma"),
                "vault_path": os.path.join(self.test_dir, "vault")
            }
        }
        self.memory_api = MemoryAPI(self.config, session_id="test_router_session")
        self.skill_registry = SkillRegistry()

        # Mock controllers
        self.mock_sys_ctrl = MagicMock()
        self.mock_sys_ctrl.get_system_info.return_value = {
            "os": "Windows", "cpu_percent": 15, "ram_used_percent": 40, "ram_total_gb": 16.0
        }
        self.mock_sys_ctrl.set_volume.return_value = {"status": "ok", "volume": 65}

        self.system_skill = SystemSkill(system_controller=self.mock_sys_ctrl)
        self.metrics_skill = MetricsSkill(system_controller=self.mock_sys_ctrl)
        self.vault_skill = VaultSkill(sqlite_manager=self.memory_api.sqlite)
        self.trends_skill = TrendsSkill(sqlite_manager=self.memory_api.sqlite)
        self.inbox_skill = InboxSkill(sqlite_manager=self.memory_api.sqlite)
        self.memory_skill = MemorySkill()

        self.mock_planner = MagicMock()
        self.mock_planner.plan.return_value = [
            {"step_num": 1, "action": "PLAN", "file": "tasks.md", "description": "Daily roadmap"}
        ]
        self.plan_skill = PlanSkill(planner=self.mock_planner)

        self.mock_brain = MagicMock()
        self.mock_brain.chat_sync.return_value = "I am JARVIS."
        self.conversation_skill = ConversationSkill(brain=self.mock_brain)

        # Register all skills
        self.skill_registry.register(self.system_skill)
        self.skill_registry.register(self.metrics_skill)
        self.skill_registry.register(self.plan_skill)
        self.skill_registry.register(self.vault_skill)
        self.skill_registry.register(self.trends_skill)
        self.skill_registry.register(self.inbox_skill)
        self.skill_registry.register(self.conversation_skill)
        self.skill_registry.register(self.memory_skill)

        self.tool_registry = ToolRegistry(system_controller=self.mock_sys_ctrl)
        self.intent_router = IntentRouter(skill_registry=self.skill_registry)

        self.router = CentralRouter(
            skill_registry=self.skill_registry,
            intent_router=self.intent_router,
            memory_api=self.memory_api,
            tool_registry=self.tool_registry
        )

    async def asyncTearDown(self):
        self.memory_api.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_successful_routing_prompts(self):
        """Verify all 5 required user request patterns route and execute cleanly."""
        # 1. "What do I need to do today?" -> plan
        res1 = await self.router.execute(UserInput(content="What do I need to do today?", channel=InputChannel.TEXT))
        self.assertEqual(res1.status, "success")
        self.assertEqual(res1.skill, "plan")
        self.assertTrue("Plan" in res1.response)

        # 2. "Show my system status." -> system
        res2 = await self.router.execute(UserInput(content="Show my system status.", channel=InputChannel.VOICE))
        self.assertEqual(res2.status, "success")
        self.assertEqual(res2.skill, "system")
        self.assertIn("CPU usage is 15%", res2.response)

        # 3. "Remember that I need to finish the project." -> memory
        res3 = await self.router.execute(UserInput(content="Remember that I need to finish the project.", channel=InputChannel.TEXT))
        self.assertEqual(res3.status, "success")
        self.assertEqual(res3.skill, "memory")

        # 4. "Summarize my metrics." -> metrics
        res4 = await self.router.execute(UserInput(content="Summarize my metrics.", channel=InputChannel.UI))
        self.assertEqual(res4.status, "success")
        self.assertEqual(res4.skill, "metrics")
        self.assertIn("Telemetry Snapshot", res4.response)

        # 5. "What changed today?" -> trends
        res5 = await self.router.execute(UserInput(content="What changed today?", channel=InputChannel.SCHEDULED))
        self.assertEqual(res5.status, "success")
        self.assertEqual(res5.skill, "trends")
        self.assertIn("Interaction Trends", res5.response)

    async def test_unknown_intent_handling(self):
        """Verify handling of completely unrecognized / empty input."""
        res = await self.router.execute(UserInput(content="!@#$%^&*()_+", channel=InputChannel.TEXT))
        self.assertEqual(res.status, "error")
        self.assertEqual(res.skill, "unknown")
        self.assertIn("did not recognize", res.response)

    async def test_ambiguous_intent_handling(self):
        """Verify handling of ambiguous single keywords."""
        res = await self.router.execute(UserInput(content="status", channel=InputChannel.TEXT))
        self.assertEqual(res.status, "ambiguous")
        self.assertIn("ambiguous", res.response.lower())

    @patch('builtins.input', return_value='y')
    async def test_skill_failure_handling(self, mock_input):
        """Verify handling when a skill returns a failure response."""
        # System skill kill_process with non-existent process
        self.mock_sys_ctrl.kill_process.return_value = {"status": "error", "message": "Process 99999 not found"}
        res = await self.router.execute(UserInput(content="kill process 99999", channel=InputChannel.TEXT))
        self.assertEqual(res.status, "error")
        self.assertIn("Process 99999 not found", res.response)

    async def test_tool_failure_handling(self):
        """Verify tool execution exceptions are caught."""
        with patch.object(self.mock_sys_ctrl, 'get_system_info', side_effect=RuntimeError("Hardware sensor disconnected")):
            res = await self.router.execute(UserInput(content="Show my system status.", channel=InputChannel.TEXT))
            self.assertEqual(res.status, "error")
            self.assertIn("Hardware sensor disconnected", res.response)

    async def test_memory_failure_resilience(self):
        """Verify that a memory failure does not break the user response."""
        with patch.object(self.memory_api, 'add_message', side_effect=Exception("Disk full")):
            res = await self.router.execute(UserInput(content="Show my system status.", channel=InputChannel.TEXT))
            self.assertEqual(res.status, "success")
            self.assertIn("CPU usage is 15%", res.response)
            # Verify memory error was tracked
            error_updates = [u for u in res.memory_updates if u.get("type") == "memory_error"]
            self.assertTrue(len(error_updates) > 0)

    async def test_timeout_handling(self):
        """Verify that long-running operations hit the timeout guard."""
        # Define a slow skill
        async def slow_execution(*args, **kwargs):
            await asyncio.sleep(0.5)
            return None

        with patch.object(self.skill_registry, 'execute_intent', side_effect=lambda *a, **k: asyncio.run(slow_execution())):
            ctx = ExecutionContext(timeout_seconds=0.1)
            res = await self.router.execute(
                UserInput(content="Show my system status.", channel=InputChannel.TEXT),
                execution_context=ctx
            )
            self.assertEqual(res.status, "timeout")
            self.assertIn("timed out", res.response.lower())


if __name__ == "__main__":
    unittest.main()
