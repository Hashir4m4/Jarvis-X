import unittest
import asyncio
import os
import sys
import tempfile
import shutil
import datetime
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock external heavy dependencies
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

from backend.core.models import UserInput, InputChannel
from backend.skills.registry import SkillRegistry
from backend.skills.brief_skill import BriefSkill
from backend.skills.plan_skill import PlanSkill
from backend.skills.metrics_skill import MetricsSkill
from backend.skills.close_day_skill import CloseDaySkill
from backend.router.intent_router import IntentRouter
from backend.router.central_router import CentralRouter
from backend.memory.memory_api import MemoryAPI


class TestDailyWorkflows(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            "memory_advanced": {
                "sqlite_db_path": os.path.join(self.test_dir, "test.sqlite"),
                "chroma_db_path": os.path.join(self.test_dir, "chroma"),
                "vault_path": os.path.join(self.test_dir, "vault")
            }
        }
        self.memory = MemoryAPI(self.config, session_id="daily_session")

        # Mock controllers
        self.mock_sys_ctrl = MagicMock()
        self.mock_sys_ctrl.get_system_info.return_value = {
            "os": "Windows", "cpu_percent": 14, "ram_used_percent": 38, "ram_total_gb": 16.0
        }
        self.mock_sys_ctrl.get_battery.return_value = {"percent": 90, "power_plugged": True}
        self.mock_sys_ctrl.get_wifi_status.return_value = {"connected": True}

        self.brief_skill = BriefSkill(sqlite_manager=self.memory.sqlite)
        self.plan_skill = PlanSkill(planner=None)
        self.metrics_skill = MetricsSkill(system_controller=self.mock_sys_ctrl)
        self.close_day_skill = CloseDaySkill(sqlite_manager=self.memory.sqlite)

        self.skill_registry = SkillRegistry()
        self.skill_registry.register(self.brief_skill)
        self.skill_registry.register(self.plan_skill)
        self.skill_registry.register(self.metrics_skill)
        self.skill_registry.register(self.close_day_skill)

        self.intent_router = IntentRouter(skill_registry=self.skill_registry)
        self.central_router = CentralRouter(
            skill_registry=self.skill_registry,
            intent_router=self.intent_router,
            memory_api=self.memory
        )

    async def asyncTearDown(self):
        self.memory.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_morning_brief_workflow(self):
        """Verify Morning Brief aggregates inbox, memory, and reports unconfigured connectors honestly."""
        # Add sample dialogue
        self.memory.add_message("user", "Remember to prepare deployment package.")

        res = await self.central_router.execute(
            UserInput(content="Give me my morning brief", channel=InputChannel.TEXT)
        )

        self.assertEqual(res.status, "success")
        self.assertEqual(res.skill, "brief")
        self.assertIn("Morning Intelligence Brief", res.response)
        # Verify honest reporting of disconnected services
        self.assertIn("calendar connector configured", res.response)
        self.assertIn("No external RSS", res.response)

    async def test_plan_today_workflow(self):
        """Verify Plan Today extracts top 3 priorities and stores in vault/daily/."""
        res = await self.central_router.execute(
            UserInput(content="Plan today's priorities", channel=InputChannel.TEXT)
        )

        self.assertEqual(res.status, "success")
        self.assertEqual(res.skill, "plan")
        self.assertIn("Daily Execution Plan", res.response)
        self.assertIn("Top 3 Priorities", res.response)

        # Verify daily note stored in vault/daily/
        daily_files = os.listdir(os.path.join(self.test_dir, "vault", "daily"))
        self.assertTrue(len(daily_files) > 0)
        today_file = f"{datetime.date.today().isoformat()}.md"
        self.assertIn(today_file, daily_files)

    async def test_metrics_pull_workflow(self):
        """Verify Metrics Pull captures hardware telemetry and stores in vault/outputs/."""
        res = await self.central_router.execute(
            UserInput(content="Pull metrics report", channel=InputChannel.TEXT)
        )

        self.assertEqual(res.status, "success")
        self.assertEqual(res.skill, "metrics")
        self.assertIn("System Metrics Report", res.response)
        self.assertIn("CPU", res.response)

        # Verify report archived in vault/outputs/
        output_files = os.listdir(os.path.join(self.test_dir, "vault", "outputs"))
        self.assertTrue(len(output_files) > 0)

    async def test_close_the_day_workflow(self):
        """Verify Close the Day synthesizes completed work, reflections, and tomorrow's priorities."""
        # Add past commands
        self.memory.add_message("user", "Build Python analyzer script")
        self.memory.add_message("user", "Show system status")

        res = await self.central_router.execute(
            UserInput(content="Close the day", channel=InputChannel.TEXT)
        )

        self.assertEqual(res.status, "success")
        self.assertEqual(res.skill, "close_day")
        self.assertIn("Close the Day Digest", res.response)
        self.assertIn("Completed Work", res.response)
        self.assertIn("Tomorrow's Top Priorities", res.response)

        # Verify daily note exists in vault/daily/
        daily_files = os.listdir(os.path.join(self.test_dir, "vault", "daily"))
        self.assertTrue(len(daily_files) > 0)


if __name__ == "__main__":
    unittest.main()
