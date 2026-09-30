import unittest
import asyncio
import os
import sys
import tempfile
import shutil
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy external packages
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

from backend.core.models import UserInput, InputChannel, OperatingState, JarvisError, ErrorCategory
from backend.core.resilience import safe_retry, with_timeout, structured_log
from backend.llm.providers.ollama_provider import OllamaProvider
from backend.llm.interfaces import LLMErrorType
from backend.skills.registry import SkillRegistry
from backend.skills.system_skill import SystemSkill
from backend.router.intent_router import IntentRouter
from backend.router.central_router import CentralRouter
from backend.memory.memory_api import MemoryAPI


class TestReliabilityAndFaultTolerance(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {
            "memory_advanced": {
                "sqlite_db_path": os.path.join(self.test_dir, "test.sqlite"),
                "chroma_db_path": os.path.join(self.test_dir, "chroma"),
                "vault_path": os.path.join(self.test_dir, "vault")
            }
        }
        self.memory = MemoryAPI(self.config, session_id="reliability_session")
        self.skill_registry = SkillRegistry()
        self.skill_registry.register(SystemSkill())

        self.intent_router = IntentRouter(skill_registry=self.skill_registry)
        self.central_router = CentralRouter(
            skill_registry=self.skill_registry,
            intent_router=self.intent_router,
            memory_api=self.memory
        )

    async def asyncTearDown(self):
        self.memory.close()
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_ollama_offline_does_not_crash(self):
        """Verify system handles offline Ollama gracefully with structured error."""
        with patch("requests.post") as mock_post:
            import requests
            mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

            provider = OllamaProvider()
            res = provider.chat_sync([{"role": "user", "content": "Ping"}])

            self.assertFalse(res.success)
            self.assertEqual(res.error_type, LLMErrorType.SERVICE_UNAVAILABLE)
            self.assertIn("service unavailable", res.error.lower())

    async def test_missing_skill_graceful_recovery(self):
        """Verify requesting unknown action or missing skill fails gracefully without unhandled crash."""
        res = await self.central_router.execute(
            UserInput(content="!@#$%^&*()_+ invalid query", channel=InputChannel.TEXT)
        )
        self.assertIn(res.status, ("error", "unknown"))
        self.assertIn("did not recognize a valid skill", res.response)

    async def test_memory_failure_does_not_crash_core_pipeline(self):
        """Verify that a failure in SQLite memory layer does not crash execution."""
        with patch.object(self.memory, "add_message", side_effect=Exception("Database locked")):
            res = await self.central_router.execute(
                UserInput(content="Show my system status.", channel=InputChannel.TEXT)
            )
            # Memory failed, but skill execution succeeded
            self.assertIn(res.status, ("success", "memory_error"))
            self.assertIn("System Status", res.response)

    async def test_safe_retry_idempotent_vs_non_idempotent(self):
        """Verify safe_retry retries idempotent reads, but never retries destructive actions."""
        call_count = 0

        async def idempotent_read():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Transient read timeout")
            return "telemetry_success"

        # 1. Idempotent action should succeed on retry
        res = await safe_retry(idempotent_read, retries=2, backoff=0.01, is_idempotent=True)
        self.assertEqual(res, "telemetry_success")
        self.assertEqual(call_count, 2)

        # 2. Non-idempotent action (e.g. destructive delete) must NOT retry
        del_count = 0

        async def destructive_delete():
            nonlocal del_count
            del_count += 1
            raise RuntimeError("Delete failed")

        with self.assertRaises(RuntimeError):
            await safe_retry(destructive_delete, retries=3, is_idempotent=False)
        self.assertEqual(del_count, 1)  # Only called once!

    async def test_with_timeout_enforces_limit(self):
        """Verify with_timeout terminates hanging coroutines cleanly."""
        async def slow_operation():
            await asyncio.sleep(5.0)
            return "done"

        with self.assertRaises(TimeoutError):
            await with_timeout(slow_operation(), timeout_seconds=0.05, error_message="Task timeout")

    def test_consistent_error_model_and_structured_logs(self):
        """Verify consistent error model generation and structured logging."""
        err = JarvisError(
            category=ErrorCategory.TIMEOUT,
            message="Agent execution exceeded 30s limit",
            action="coding.pipeline",
            recoverable=True
        )

        d = err.to_dict()
        self.assertEqual(d["category"], "timeout")
        self.assertEqual(d["action"], "coding.pipeline")
        self.assertTrue(d["recoverable"])

        # Structured logging emits without exception
        structured_log("test_event", level="info", state=OperatingState.RUNNING, error=err)


if __name__ == "__main__":
    unittest.main()
