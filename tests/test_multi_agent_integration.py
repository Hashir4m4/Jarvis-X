import unittest
import os
import sys
import tempfile
import shutil
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy libraries
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['pycaw'] = MagicMock()
sys.modules['pycaw.pycaw'] = MagicMock()
sys.modules['comtypes'] = MagicMock()

from backend.core.models import UserInput, InputChannel
from backend.agents.agent_manager import AgentManager
from backend.skills.coding_skill import CodingSkill
from backend.router.tool_registry import ToolRegistry
from backend.router.intent_router import IntentRouter
from backend.router.central_router import CentralRouter
from backend.skills.registry import SkillRegistry
from backend.skills.system_skill import SystemSkill
from backend.skills.metrics_skill import MetricsSkill
from backend.memory.memory_api import MemoryAPI
from backend.automation.security_proxy import SecurityProxy


class TestMultiAgentIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            "memory_advanced": {
                "sqlite_db_path": os.path.join(self.test_dir, "test.sqlite"),
                "chroma_db_path": os.path.join(self.test_dir, "chroma"),
                "vault_path": os.path.join(self.test_dir, "vault")
            }
        }
        self.memory_api = MemoryAPI(self.config, session_id="test_agent_session")

        self.mock_llm = MagicMock()
        self.mock_llm.chat_sync.return_value = '```json\n[{"step_num": 1, "action": "CREATE", "file": "analyzer.py", "description": "CSV parser"}]\n```'

        self.state_updates = []
        def on_state(payload):
            self.state_updates.append(payload)

        self.security = SecurityProxy(self.config)
        self.agent_manager = AgentManager(
            llm=self.mock_llm,
            security=self.security,
            working_dir=self.test_dir,
            state_callback=on_state
        )

        self.coding_skill = CodingSkill(agent_manager=self.agent_manager)
        self.mock_sys_ctrl = MagicMock()
        self.mock_sys_ctrl.get_system_info.return_value = {"cpu_percent": 18, "ram_used_percent": 35}
        self.system_skill = SystemSkill(system_controller=self.mock_sys_ctrl)
        self.metrics_skill = MetricsSkill(system_controller=self.mock_sys_ctrl)

        self.skill_registry = SkillRegistry()
        self.skill_registry.register(self.coding_skill)
        self.skill_registry.register(self.system_skill)
        self.skill_registry.register(self.metrics_skill)

        self.tool_registry = ToolRegistry(agent_manager=self.agent_manager)
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

    async def test_decision_policy_routing(self):
        """Verify that coding tasks invoke Multi-Agent Swarm, while CPU queries DO NOT."""
        # 1. Coding task -> MUST route to coding skill
        coding_input = UserInput(content="Build a Python script that analyzes this CSV.", channel=InputChannel.TEXT)
        intent_code = self.intent_router.route(coding_input)
        self.assertEqual(intent_code.skill_name, "coding")
        self.assertEqual(intent_code.action, "run_task")

        # 2. CPU query -> MUST route to metrics and NEVER invoke coding skill
        cpu_input = UserInput(content="What is my CPU usage?", channel=InputChannel.TEXT)
        intent_cpu = self.intent_router.route(cpu_input)
        self.assertEqual(intent_cpu.skill_name, "metrics")
        self.assertEqual(intent_cpu.action, "get_cpu_load")
        self.assertNotEqual(intent_cpu.skill_name, "coding")

    async def test_multi_agent_pipeline_execution(self):
        """Verify Planner -> Coder -> Reviewer -> Executor flow with memory output."""
        # Mock planner response
        self.agent_manager.planner.plan = MagicMock(return_value=[
            {"step_num": 1, "action": "CREATE", "file": "script.py", "description": "CSV statistics parser"}
        ])
        self.agent_manager.coder.generate = MagicMock(return_value="import csv\nprint('Done')")
        self.agent_manager.reviewer.review = MagicMock(return_value={"approved": True, "grade": "A", "feedback": "Clean code"})

        res = await self.router.execute(
            UserInput(content="Build a Python script that analyzes this CSV.", channel=InputChannel.TEXT)
        )

        self.assertEqual(res.status, "success")
        self.assertEqual(res.skill, "coding")
        self.assertIn("Multi-Agent Coding Result", res.response)

        # Verify state telemetry was emitted for HUD
        agent_names = [s.get("agent") for s in self.state_updates]
        self.assertIn("planner", agent_names)
        self.assertIn("coder", agent_names)
        self.assertIn("reviewer", agent_names)

        # Verify deliverable report was created in vault/outputs/
        output_files = os.listdir(os.path.join(self.test_dir, "vault", "outputs"))
        self.assertTrue(len(output_files) > 0)

    async def test_agent_cancellation(self):
        """Verify cancellation token stops multi-agent pipeline immediately."""
        self.agent_manager.planner.plan = MagicMock(return_value=[
            {"step_num": 1, "action": "CREATE", "file": "step1.py", "description": "Step 1"},
            {"step_num": 2, "action": "CREATE", "file": "step2.py", "description": "Step 2"}
        ])
        self.agent_manager.coder.generate = MagicMock(side_effect=lambda *a, **k: (self.agent_manager.cancel(), "code")[1])

        report = self.agent_manager.run_task("Build massive web crawler")
        self.assertEqual(report["status"], "cancelled")
        self.assertEqual(len(report["steps"]), 1)

    async def test_agent_timeout(self):
        """Verify timeout guard stops long-running agent tasks."""
        def slow_plan(*args, **kwargs):
            import time
            time.sleep(0.3)
            return [{"step_num": 1, "action": "CREATE", "file": "slow.py", "description": "Slow"}]

        self.agent_manager.planner.plan = slow_plan
        report = self.agent_manager.run_task("Task with short timeout", timeout=0.1)
        self.assertEqual(report["status"], "timeout")

    def test_tool_registry_agent_tools(self):
        """Verify all multi-agent capabilities are accessible via ToolRegistry."""
        tools = self.tool_registry.list_tools()
        tool_names = [t["name"] for t in tools]

        self.assertIn("agent.pipeline", tool_names)
        self.assertIn("agent.planner", tool_names)
        self.assertIn("agent.coder", tool_names)
        self.assertIn("agent.reviewer", tool_names)
        self.assertIn("agent.executor", tool_names)


if __name__ == "__main__":
    unittest.main()
