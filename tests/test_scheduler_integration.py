import unittest
import asyncio
import os
import sys
import tempfile
import shutil
import time
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy ML and audio libraries
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

from backend.kernel.scheduler import Scheduler, ScheduledTask
from backend.kernel.event_bus import EventBus
from backend.core.models import UserInput, InputChannel, CoreResponse
from backend.router.tool_registry import ToolRegistry


class TestSchedulerIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.storage_path = os.path.join(self.test_dir, "test_schedules.json")
        self.event_bus = EventBus()
        self.events_received = []

        async def record_event(event_type, data):
            self.events_received.append((event_type, data))

        await self.event_bus.subscribe("scheduled_task_executed", record_event)
        await self.event_bus.subscribe("schedule_updated", record_event)
        await self.event_bus.subscribe("voice_speak_request", record_event)

        self.executed_inputs = []
        async def mock_core_executor(user_input: UserInput):
            self.executed_inputs.append(user_input)
            return CoreResponse(
                text=f"Executed command for {user_input.content}",
                channel=user_input.channel,
                execution_time_ms=12.5,
                request_id=user_input.request_id
            )

        self.scheduler = Scheduler(
            storage_path=self.storage_path,
            core_executor=mock_core_executor,
            event_bus=self.event_bus
        )

    async def asyncTearDown(self):
        self.scheduler.stop()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_schedules_created_and_persisted(self):
        """Verify default configurable schedules (07:00, 09:00, 14:00, 19:00) are populated and saved."""
        schedules = self.scheduler.get_active_schedules()
        task_ids = [s["task_id"] for s in schedules]

        self.assertIn("morning_brief", task_ids)
        self.assertIn("plan_today", task_ids)
        self.assertIn("metrics_pull", task_ids)
        self.assertIn("close_the_day", task_ids)
        self.assertTrue(os.path.isfile(self.storage_path))

    async def test_scheduled_task_core_execution_flow(self):
        """
        Verify: SCHEDULE -> JARVIS CORE -> ROUTER -> SKILL -> EXECUTION -> MEMORY -> NOTIFICATION/TTS
        """
        task = self.scheduler.schedule_daily("07:00", "What do I need to do today?", task_id="test_morning", tts_notify=True)
        log = await self.scheduler.execute_task_now(task)
        await asyncio.sleep(0.05)

        # 1. Verify executed through Core as SCHEDULED channel
        self.assertEqual(len(self.executed_inputs), 1)
        self.assertEqual(self.executed_inputs[0].channel, InputChannel.SCHEDULED)
        self.assertEqual(self.executed_inputs[0].content, "What do I need to do today?")

        # 2. Verify history entry
        self.assertEqual(log["status"], "success")
        self.assertIn("Executed command for What do I need to do today?", log["response"])

        # 3. Verify notification & TTS events published to EventBus
        event_names = [e[0] for e in self.events_received]
        self.assertIn("scheduled_task_executed", event_names)
        self.assertIn("voice_speak_request", event_names)

    async def test_recurring_interval_task(self):
        """Verify scheduling a recurring interval task."""
        task = self.scheduler.schedule_interval(interval_seconds=10, command="Summarize my metrics.", task_id="metrics_interval")
        self.assertEqual(task.schedule_type, "interval")
        self.assertEqual(task.schedule_value, 10)

        schedules = self.scheduler.get_active_schedules()
        self.assertTrue(any(s["task_id"] == "metrics_interval" for s in schedules))

    async def test_one_time_task(self):
        """Verify scheduling a one-time future task."""
        target_time = time.time() + 3600
        task = self.scheduler.schedule_at(run_at_timestamp=target_time, command="Backup files", task_id="backup_once")
        self.assertEqual(task.schedule_type, "one_time")

        schedules = self.scheduler.get_active_schedules()
        self.assertTrue(any(s["task_id"] == "backup_once" for s in schedules))

    async def test_task_cancellation(self):
        """Verify cancelling a scheduled task."""
        task = self.scheduler.schedule_interval(60, "Check inbox", task_id="inbox_check")
        self.assertTrue(any(s["task_id"] == "inbox_check" for s in self.scheduler.get_active_schedules()))

        cancelled = self.scheduler.cancel_task("inbox_check")
        self.assertTrue(cancelled)
        self.assertFalse(any(s["task_id"] == "inbox_check" for s in self.scheduler.get_active_schedules()))

    def test_tool_registry_scheduler_tools(self):
        """Verify scheduler management tools are registered and callable in ToolRegistry."""
        tools = ToolRegistry()
        tools.register_scheduler_tools(self.scheduler)

        active = tools.execute_tool("schedule.list")
        self.assertTrue(len(active) >= 4)

        history = tools.execute_tool("schedule.history")
        self.assertIsInstance(history, list)


if __name__ == "__main__":
    unittest.main()
