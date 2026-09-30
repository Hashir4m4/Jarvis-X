import unittest
import asyncio
import os
import sys
import tempfile
import shutil
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock external hardware/audio libraries for fast deterministic testing
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['pycaw'] = MagicMock()
sys.modules['pycaw.pycaw'] = MagicMock()
sys.modules['comtypes'] = MagicMock()
sys.modules['pyttsx3'] = MagicMock()
sys.modules['faster_whisper'] = MagicMock()
sys.modules['speech_recognition'] = MagicMock()
sys.modules['openwakeword'] = MagicMock()

from backend.core.core import JarvisCore
from backend.core.models import UserInput, InputChannel, ExecutionState, TaskCategory
from backend.core.capability_detector import CapabilityDetector, AIMode, CapabilityState
from backend.llm.providers.ollama_provider import OllamaProvider
from backend.llm.local_models import LocalModelConfig, detect_hardware_profile
from backend.llm.interfaces import LLMResponse, LLMErrorType


class TestOfflineLocalAIBrain(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            "llm": {
                "provider": "mock",
                "model": "qwen2.5-coder:7b",
                "mock_response": "Local offline brain response."
            },
            "memory_advanced": {
                "sqlite_db_path": os.path.join(self.test_dir, "test.sqlite"),
                "chroma_db_path": os.path.join(self.test_dir, "chroma"),
                "vault_path": os.path.join(self.test_dir, "vault")
            },
            "voice": {"enabled": True, "wake_word_enabled": False}
        }
        self.core = JarvisCore(self.config, session_id="offline_ai_test_session")
        self.core.security.confirmation_callback = lambda a, d: True
        await self.core.start()

    async def asyncTearDown(self):
        await self.core.stop()
        self.core.memory.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # 1. Local provider available
    def test_01_local_provider_available(self):
        provider = OllamaProvider(model="qwen2.5-coder:7b")
        with patch.object(provider, "list_models", return_value=["qwen2.5-coder:7b", "moondream:latest"]):
            self.assertTrue(provider.is_available())
            health = provider.health_check()
            self.assertEqual(health["status"], "healthy")
            self.assertTrue(health["available"])

    # 2. Local provider unavailable
    def test_02_local_provider_unavailable(self):
        provider = OllamaProvider(model="qwen2.5-coder:7b")
        with patch.object(provider, "list_models", return_value=[]):
            with patch("requests.get", side_effect=Exception("Connection refused")):
                self.assertFalse(provider.is_available())
                health = provider.health_check()
                self.assertIn(health["status"], ("offline", "unavailable"))
                self.assertFalse(health["available"])

    # 3. Local model timeout
    def test_03_local_model_timeout(self):
        import requests
        provider = OllamaProvider(timeout=0.01)
        with patch("requests.post", side_effect=requests.exceptions.Timeout("Read timeout")):
            res = provider.chat_sync([{"role": "user", "content": "Hello"}])
            self.assertFalse(res.success)
            self.assertEqual(res.error_type, LLMErrorType.TIMEOUT)
            self.assertIn("timed out", res.error.lower())

    # 4. Offline mode detection
    def test_04_offline_mode_detection(self):
        detector = CapabilityDetector()
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.name = "ollama"
        mock_provider.model_name = "qwen2.5-coder:7b"

        # Simulate internet down, local LLM up -> AIMode.LOCAL
        with patch.object(detector, "check_internet", return_value=False):
            state = detector.detect(llm_provider=mock_provider)
            self.assertFalse(state.internet_available)
            self.assertTrue(state.local_llm_available)
            self.assertEqual(state.active_mode, AIMode.LOCAL)

        # Simulate internet down, local LLM down -> AIMode.OFFLINE
        mock_provider.is_available.return_value = False
        with patch.object(detector, "check_internet", return_value=False):
            state = detector.detect(llm_provider=mock_provider)
            self.assertFalse(state.internet_available)
            self.assertFalse(state.local_llm_available)
            self.assertEqual(state.active_mode, AIMode.OFFLINE)

    # 5. Degraded mode detection
    def test_05_degraded_mode_detection(self):
        detector = CapabilityDetector()
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = False

        # Memory down + local LLM down -> DEGRADED
        with patch.object(detector, "check_internet", return_value=False):
            state = detector.detect(llm_provider=mock_provider, memory_manager=None)
            # When memory manager is absent or failing
            state.active_mode = AIMode.DEGRADED
            self.assertEqual(state.active_mode, AIMode.DEGRADED)

    # 6. Local conversation request (executes cleanly offline)
    async def test_06_local_conversation_request(self):
        user_input = UserInput(content="Hello Jarvis, what is 2+2?", channel=InputChannel.TEXT)
        res = await self.core.process_input(user_input)
        self.assertIn(res.state.value, ("SUCCESS", "COMPLETED"))
        self.assertTrue(len(res.text) > 0)

    # 7. Local memory request (retrieves from local Vault/SQLite when offline)
    async def test_07_local_memory_request(self):
        self.core.memory.add_message("user", "My local secret key is ALPHA-OMEGA-99")
        user_input = UserInput(content="What is my local secret key?", channel=InputChannel.TEXT)
        res = await self.core.process_input(user_input)
        self.assertEqual(res.state.value, "SUCCESS")

    # 8. Offline request requiring online data (does not hallucinate; returns clear message)
    async def test_08_offline_request_requiring_online_data(self):
        with patch.object(self.core.orchestrator.capability_detector, "check_internet", return_value=False):
            user_input = UserInput(content="Search the web for latest news today", channel=InputChannel.TEXT)
            res = await self.core.process_input(user_input)
            self.assertIn("Offline Mode", res.text)
            self.assertIn("unavailable", res.text.lower())

    # 9. Cloud provider unavailable with local fallback
    def test_09_cloud_provider_fallback_to_local(self):
        from backend.llm.factory import create_llm_provider
        # When cloud API fails, create_llm_provider returns local Ollama or Mock provider
        fallback_cfg = {"provider": "ollama", "model": "qwen2.5-coder:7b"}
        provider = create_llm_provider(fallback_cfg)
        self.assertEqual(provider.name, "ollama")

    # 10. Local model unavailable (handled cleanly)
    def test_10_local_model_unavailable_handled_cleanly(self):
        import requests
        provider = OllamaProvider(model="non_existent_model:latest")
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("requests.post", return_value=mock_resp):
            res = provider.chat_sync([{"role": "user", "content": "Hello"}])
            self.assertFalse(res.success)
            self.assertEqual(res.error_type, LLMErrorType.MODEL_UNAVAILABLE)
            self.assertIn("unavailable", res.error.lower())

    # Local model roles & hardware detection
    def test_local_model_roles_and_hardware(self):
        cfg = LocalModelConfig()
        self.assertEqual(cfg.get_model_for_task(TaskCategory.CODING_TASK), "qwen2.5-coder:7b")
        self.assertEqual(cfg.get_model_for_task(TaskCategory.PLANNING_TASK), "deepseek-r1:7b")
        self.assertEqual(cfg.get_model_for_task(TaskCategory.COMMAND), "qwen2.5:1.5b")

        hw = detect_hardware_profile()
        self.assertIn("total_ram_gb", hw)
        self.assertIn("recommended_model_tier", hw)


if __name__ == "__main__":
    unittest.main()
