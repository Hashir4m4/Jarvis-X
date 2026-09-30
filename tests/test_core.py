import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy deps
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['pycaw'] = MagicMock()
sys.modules['pycaw.pycaw'] = MagicMock()
sys.modules['comtypes'] = MagicMock()

from backend.core.core import JarvisCore
from backend.core.models import UserInput, InputChannel, IntentType


class TestJarvisCore(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.config = {
            "llm": {"provider": "test"},
            "memory": {},
            "memory_advanced": {
                "sqlite_db_path": ":memory:",
                "chroma_db_path": "mock"
            }
        }
        self.sys_info_patch = patch('backend.automation.system_controller.SystemController.get_system_info', return_value={"cpu_percent": 0, "ram_used_percent": 0})
        self.sys_info_patch.start()
        self.core = JarvisCore(self.config, session_id="test_core_session")
        await self.core.start()

    async def asyncTearDown(self):
        await self.core.stop()
        self.sys_info_patch.stop()

    async def test_text_channel_system_command(self):
        # User asks for system info via text channel
        with patch.object(self.core.skill_registry.get_skill("system").system_ctrl, 'get_system_info') as mock_info:
            mock_info.return_value = {"os": "Windows", "cpu_percent": 20, "ram_used_percent": 50, "ram_total_gb": 32.0}
            user_input = UserInput(content="system info", channel=InputChannel.TEXT)
            response = await self.core.process_input(user_input)

            self.assertEqual(response.channel, InputChannel.TEXT)
            self.assertEqual(response.intent.intent_type, IntentType.SYSTEM_CONTROL)
            self.assertIn("CPU usage is 20%", response.text)

    async def test_voice_channel_volume_command(self):
        # User issues a volume command via voice channel
        with patch.object(self.core.skill_registry.get_skill("system").system_ctrl, 'set_volume') as mock_vol:
            mock_vol.return_value = {"status": "ok", "volume": 80}
            user_input = UserInput(content="set volume to 80", channel=InputChannel.VOICE)
            response = await self.core.process_input(user_input)

            self.assertEqual(response.channel, InputChannel.VOICE)
            self.assertIn("Volume set to 80%", response.text)

    async def test_scheduled_channel_command(self):
        # A scheduled recurring job queries battery status
        with patch.object(self.core.skill_registry.get_skill("system").system_ctrl, 'get_battery') as mock_batt:
            mock_batt.return_value = {"percent": 95, "plugged_in": True}
            user_input = UserInput(content="battery status", channel=InputChannel.SCHEDULED)
            response = await self.core.process_input(user_input)

            self.assertEqual(response.channel, InputChannel.SCHEDULED)
            self.assertIn("Battery is at 95%", response.text)

    async def test_ui_channel_command(self):
        # UI quick action sends wifi check
        with patch.object(self.core.skill_registry.get_skill("system").system_ctrl, 'get_wifi_status') as mock_wifi:
            mock_wifi.return_value = {"wifi_connected": True}
            user_input = UserInput(content="check wifi", channel=InputChannel.UI)
            response = await self.core.process_input(user_input)

            self.assertEqual(response.channel, InputChannel.UI)
            self.assertIn("WiFi is connected", response.text)

    async def test_streaming_pipeline(self):
        # Test streaming response generator
        with patch.object(self.core.skill_registry.get_skill("system").system_ctrl, 'get_volume') as mock_vol:
            mock_vol.return_value = {"status": "ok", "volume": 50, "muted": False}
            user_input = UserInput(content="get volume", channel=InputChannel.TEXT)

            events = []
            async for event in self.core.process_stream(user_input):
                events.append(event)

            self.assertTrue(len(events) >= 2)
            self.assertEqual(events[0]["type"], "intent_routed")
            self.assertEqual(events[-1]["type"], "chat_complete")
            self.assertIn("50%", events[-1]["data"]["content"])


if __name__ == "__main__":
    unittest.main()
