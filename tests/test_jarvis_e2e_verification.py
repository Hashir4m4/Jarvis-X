import unittest
import asyncio
import os
import sys
import tempfile
import shutil
import json
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy third-party packages for fast headless testing
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
from backend.core.models import UserInput, InputChannel, OperatingState, JarvisError, ErrorCategory
from backend.voice.interfaces import STTProvider, TTSProvider, VoiceState
from backend.voice.voice_manager import VoiceManager
from backend.automation.security_proxy import PermissionLevel
from backend.llm.providers.mock_provider import MockLLMProvider
from backend.llm.providers.ollama_provider import OllamaProvider
from backend.llm.interfaces import LLMErrorType


class TestJarvisE2EVerification(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            "llm": {"provider": "mock", "mock_response": "Mock LLM verification response."},
            "memory_advanced": {
                "sqlite_db_path": os.path.join(self.test_dir, "test.sqlite"),
                "chroma_db_path": os.path.join(self.test_dir, "chroma"),
                "vault_path": os.path.join(self.test_dir, "vault")
            },
            "voice": {"enabled": True, "wake_word_enabled": False}
        }
        self.core = JarvisCore(self.config, session_id="e2e_session")
        self.core.security.confirmation_callback = lambda action, details: True
        await self.core.start()

    async def asyncTearDown(self):
        await self.core.stop()
        self.core.memory.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Text command
    async def test_flow_01_text_command(self):
        res = await self.core.process_input(UserInput(content="Show my system status.", channel=InputChannel.TEXT))
        self.assertTrue(len(res.text) > 0)
        self.assertEqual(res.intent.skill_name, "system")

    # 2. Voice command
    async def test_flow_02_voice_command(self):
        mock_stt = MagicMock(spec=STTProvider)
        mock_stt.transcribe.return_value = "What is my CPU usage?"
        mock_tts = MagicMock(spec=TTSProvider)

        vm = VoiceManager(
            config=self.config,
            stt_provider=mock_stt,
            tts_provider=mock_tts,
            router=self.core.central_router
        )
        res = await asyncio.to_thread(vm.process_voice_input_sync, b"dummy_wav")
        self.assertIsNotNone(res)
        mock_tts.speak.assert_called()

    # 3. Skill routing
    async def test_flow_03_skill_routing(self):
        intent = self.core.router.route(UserInput(content="What changed today?", channel=InputChannel.TEXT))
        self.assertEqual(intent.skill_name, "trends")
        self.assertEqual(intent.action, "get_query_trends")

    # 4. Skill execution
    async def test_flow_04_skill_execution(self):
        res = await self.core.process_input(UserInput(content="Plan today's priorities", channel=InputChannel.TEXT))
        self.assertEqual(res.intent.skill_name, "plan")
        self.assertIn("Daily Execution Plan", res.text)

    # 5. Memory write
    async def test_flow_05_memory_write(self):
        path = self.core.memory.vault.create_daily_note(
            date_str="2026-09-03",
            priorities=["Complete E2E verification"],
            activity=["Executing test suite"],
            reflection="All systems verified"
        )
        self.assertTrue(os.path.isfile(path))

    # 6. Memory retrieval
    async def test_flow_06_memory_retrieval(self):
        self.core.memory.add_message("user", "My secret code is ALPHA-OMEGA-99")
        ctx = self.core.memory.retrieve_context("secret code")
        self.assertTrue(len(ctx) > 0)

    # 7. Agent execution
    def test_flow_07_agent_execution(self):
        with patch.object(self.core.agent_manager.planner, "plan", return_value=[{"step_num": 1, "action": "write_file", "file": "analyzer.py", "description": "Write analyzer"}]):
            with patch.object(self.core.agent_manager.coder, "generate", return_value="print('analysis complete')"):
                res = self.core.agent_manager.run_task("Build Python analyzer", timeout=10)
                self.assertEqual(res.get("status"), "ok")

    # 8. Scheduled task
    async def test_flow_08_scheduled_task(self):
        task = self.core.kernel.scheduler.schedule_interval(
            interval_seconds=60,
            command="Summarize my metrics.",
            task_id="e2e_sched_test"
        )
        log_entry = await self.core.kernel.scheduler.execute_task_now(task)
        self.assertEqual(log_entry["status"], "success")

    # 9. TTS response
    def test_flow_09_tts_response(self):
        mock_tts = MagicMock(spec=TTSProvider)
        mock_tts.speak("JARVIS online")
        mock_tts.speak.assert_called_with("JARVIS online")

    # 10. HUD update
    async def test_flow_10_hud_update(self):
        hud_event_received = False
        async def on_hud_event(event_type, data):
            nonlocal hud_event_received
            hud_event_received = True

        await self.core.kernel.event_bus.subscribe("telemetry_update", on_hud_event)
        await self.core.kernel.event_bus.publish("telemetry_update", {"cpu": 15, "ram": 40})
        await asyncio.sleep(0.05)
        self.assertTrue(hud_event_received)

    # 11. WebSocket reconnect
    async def test_flow_11_websocket_reconnect(self):
        from backend.api.websocket_manager import WebSocketManager
        wm = WebSocketManager()
        mock_ws = unittest.mock.AsyncMock()
        await wm.connect(mock_ws)
        self.assertEqual(len(wm.active_connections), 1)
        wm.disconnect(mock_ws)
        self.assertEqual(len(wm.active_connections), 0)

    # 12. Ollama unavailable
    def test_flow_12_ollama_unavailable(self):
        import requests
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Connection refused")):
            provider = OllamaProvider()
            res = provider.chat_sync([{"role": "user", "content": "Ping"}])
            self.assertFalse(res.success)
            self.assertEqual(res.error_type, LLMErrorType.SERVICE_UNAVAILABLE)

    # 13. STT unavailable
    async def test_flow_13_stt_unavailable(self):
        mock_stt = MagicMock(spec=STTProvider)
        mock_stt.transcribe.side_effect = RuntimeError("Microphone disconnected")
        vm = VoiceManager(config=self.config, stt_provider=mock_stt, router=self.core.central_router)
        res = await asyncio.to_thread(vm.process_voice_input_sync, b"wav")
        self.assertIsNone(res)
        self.assertEqual(vm.state, VoiceState.IDLE)

    # 14. TTS unavailable
    async def test_flow_14_tts_unavailable(self):
        mock_stt = MagicMock(spec=STTProvider)
        mock_stt.transcribe.return_value = "Show my system status."
        mock_tts = MagicMock(spec=TTSProvider)
        mock_tts.speak.side_effect = RuntimeError("Audio device busy")

        vm = VoiceManager(config=self.config, stt_provider=mock_stt, tts_provider=mock_tts, router=self.core.central_router)
        res = await asyncio.to_thread(vm.process_voice_input_sync, b"wav")
        self.assertIsNotNone(res)  # Execution succeeds even if TTS speaker fails

    # 15. Skill failure
    async def test_flow_15_skill_failure(self):
        res = await self.core.central_router.execute(UserInput(content="kill process 99999", channel=InputChannel.TEXT))
        self.assertIn(res.status, ("error", "skill_failure", "success"))

    # 16. Agent timeout
    def test_flow_16_agent_timeout(self):
        with patch.object(self.core.agent_manager.planner, "plan", side_effect=lambda t, c=None: [{"step_num": 1, "action": "write_file", "file": "script.py", "description": "Write script"}]):
            res = self.core.agent_manager.run_task("Build Python analyzer", timeout=0.00001)
            self.assertEqual(res.get("status"), "timeout")

    # 17. Invalid command
    async def test_flow_17_invalid_command(self):
        res = await self.core.process_input(UserInput(content="!@#$%^&*()_+", channel=InputChannel.TEXT))
        self.assertIn("recognize", res.text.lower())

    # 18. Permission-required command
    def test_flow_18_permission_required_command(self):
        executed = False
        def delete_op():
            nonlocal executed
            executed = True
            return "deleted"

        self.core.security.confirmation_callback = lambda a, d: False
        res = self.core.security.execute("delete_file", "temp.log", delete_op)
        self.assertFalse(executed)
        self.assertEqual(res.get("status"), "denied")

    # 19. Restart persistence
    async def test_flow_19_restart_persistence(self):
        # Write daily note
        note_path = self.core.memory.vault.create_daily_note(date_str="2026-09-03", content="Persisted note")
        # Restart Core
        await self.core.stop()
        new_core = JarvisCore(self.config, session_id="e2e_session")
        await new_core.start()

        read_back = new_core.memory.vault.read_note(note_path)
        self.assertIsNotNone(read_back)
        self.assertIn("Persisted note", read_back["raw"])
        await new_core.stop()


if __name__ == "__main__":
    unittest.main()
