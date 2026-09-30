import unittest
import os
import sys
import json
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

from backend.llm.interfaces import LLMProvider, LLMResponse, LLMErrorType, ProviderStatus
from backend.llm.providers.openai_provider import OpenAICompatibleProvider
from backend.llm.providers.anthropic_provider import AnthropicProvider
from backend.llm.providers.gemini_provider import GeminiProvider
from backend.llm.cloud_models import CloudModelConfig
from backend.llm.privacy_boundary import PrivacyBoundary, ContextPrivacyLevel
from backend.llm.cloud_manager import CloudProviderManager
from backend.core.models import TaskCategory


class TestCloudAIProviders(unittest.TestCase):

    def setUp(self):
        self.privacy = PrivacyBoundary()

    # 1. Cloud provider available
    def test_01_cloud_provider_available(self):
        provider = OpenAICompatibleProvider(api_key="sk-mock-valid-key-12345678901234567890")
        self.assertTrue(provider.is_available())
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "gpt-4o-mini"}]}
        with patch("requests.get", return_value=mock_resp):
            health = provider.health_check()
            self.assertEqual(health["status"], ProviderStatus.AVAILABLE.value)
            self.assertTrue(health["available"])

    # 2. Cloud provider misconfigured (missing API key)
    def test_02_cloud_provider_misconfigured(self):
        provider = OpenAICompatibleProvider(api_key="", base_url="https://api.openai.com/v1")
        self.assertFalse(provider.is_available())
        health = provider.health_check()
        self.assertEqual(health["status"], ProviderStatus.MISCONFIGURED.value)
        self.assertFalse(health["available"])

        res = provider.chat_sync([{"role": "user", "content": "Hello"}])
        self.assertFalse(res.success)
        self.assertEqual(res.error_type, LLMErrorType.MISCONFIGURED)

    # 3. Invalid API key (HTTP 401)
    def test_03_invalid_api_key_auth_error(self):
        provider = AnthropicProvider(api_key="ant-api-invalid-key-1234567890")
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        with patch("requests.post", return_value=mock_resp):
            res = provider.chat_sync([{"role": "user", "content": "Hello"}])
            self.assertFalse(res.success)
            self.assertEqual(res.error_type, LLMErrorType.AUTH_ERROR)

    # 4. Provider timeout
    def test_04_provider_timeout(self):
        import requests
        provider = GeminiProvider(api_key="AIzaSy-mock-key-12345678901234567890")
        with patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out")):
            res = provider.chat_sync([{"role": "user", "content": "Hello"}])
            self.assertFalse(res.success)
            self.assertEqual(res.error_type, LLMErrorType.TIMEOUT)

    # 5. Rate limiting (HTTP 429)
    def test_05_rate_limiting(self):
        provider = OpenAICompatibleProvider(api_key="sk-mock-key-12345678901234567890")
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        with patch("requests.post", return_value=mock_resp):
            res = provider.chat_sync([{"role": "user", "content": "Hello"}])
            self.assertFalse(res.success)
            self.assertEqual(res.error_type, LLMErrorType.RATE_LIMITED)

    # 6. Provider unavailable (HTTP 500/503 / ConnectionError)
    def test_06_provider_unavailable(self):
        import requests
        provider = AnthropicProvider(api_key="ant-api-mock-key-1234567890")
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Server unreachable")):
            res = provider.chat_sync([{"role": "user", "content": "Hello"}])
            self.assertFalse(res.success)
            self.assertEqual(res.error_type, LLMErrorType.SERVICE_UNAVAILABLE)

    # 7. Successful generation (generate() method)
    def test_07_successful_generation(self):
        provider = OpenAICompatibleProvider(api_key="sk-mock-key-12345678901234567890")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Generated cloud response."}}],
            "usage": {"total_tokens": 42}
        }
        with patch("requests.post", return_value=mock_resp):
            res = provider.generate("Write a poem", system_prompt="You are an assistant.")
            self.assertTrue(res.success)
            self.assertEqual(res.content, "Generated cloud response.")
            self.assertEqual(res.usage["total_tokens"], 42)

    # 8. Successful chat (chat_sync() method)
    def test_08_successful_chat(self):
        provider = GeminiProvider(api_key="AIzaSy-mock-key-12345678901234567890")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "Gemini answer."}]}}],
            "usageMetadata": {"totalTokenCount": 25}
        }
        with patch("requests.post", return_value=mock_resp):
            res = provider.chat_sync([{"role": "user", "content": "What is AI?"}])
            self.assertTrue(res.success)
            self.assertEqual(res.content, "Gemini answer.")

    # 9. Streaming response
    def test_09_streaming_response(self):
        provider = OpenAICompatibleProvider(api_key="sk-mock-key-12345678901234567890")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = [
            b'data: {"choices": [{"delta": {"content": "Hello"}}]}',
            b'data: {"choices": [{"delta": {"content": " world!"}}]}',
            b'data: [DONE]'
        ]
        with patch("requests.post", return_value=MagicMock(__enter__=MagicMock(return_value=mock_resp))):
            chunks = list(provider.chat_stream([{"role": "user", "content": "Hi"}]))
            self.assertEqual("".join(chunks), "Hello world!")

    # 10. Sensitive context filtering (Privacy Boundary)
    def test_10_sensitive_context_filtering(self):
        secret_prompt = "My OpenAI key is sk-1234567890abcdef1234567890 and my password is password = 'SuperSecret123!'"
        sanitized = self.privacy.redact_secrets(secret_prompt)
        self.assertNotIn("sk-1234567890abcdef1234567890", sanitized)
        self.assertIn("[REDACTED_SECRET]", sanitized)

        # Message array sanitization
        messages = [
            {"role": "system", "content": "System instruction with token: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"},
            {"role": "user", "content": "Here is ghp_123456789012345678901234567890123456 for my repo"}
        ]
        cleaned = self.privacy.sanitize_messages(messages)
        self.assertNotIn("ghp_123456789012345678901234567890123456", cleaned[1]["content"])
        self.assertIn("[REDACTED_SECRET]", cleaned[1]["content"])

        # Context classification
        self.assertEqual(self.privacy.classify_context("Normal query"), ContextPrivacyLevel.CLOUD_ALLOWED_CONTEXT)
        self.assertEqual(self.privacy.classify_context("API key sk-abcdef1234567890123456"), ContextPrivacyLevel.SENSITIVE_LOCAL_CONTEXT)
        self.assertEqual(self.privacy.classify_context("config", source=".env"), ContextPrivacyLevel.SENSITIVE_LOCAL_CONTEXT)

    # 11. Provider capability detection
    def test_11_provider_capability_detection(self):
        openai_p = OpenAICompatibleProvider(api_key="sk-mock", model="gpt-4o")
        self.assertTrue(openai_p.supports_streaming())
        self.assertTrue(openai_p.supports_tools())
        self.assertTrue(openai_p.supports_vision())

        anthropic_p = AnthropicProvider(api_key="ant-mock", model="claude-3-5-sonnet-20241022")
        caps = anthropic_p.get_capabilities()
        self.assertTrue(caps.streaming)
        self.assertTrue(caps.tool_calling)
        self.assertTrue(caps.vision)

    # 12. Multiple providers configured
    def test_12_multiple_providers_configured(self):
        cfg = {
            "llm": {
                "openai_api_key": "sk-mock-key-12345678901234567890",
                "anthropic_api_key": "ant-mock-key-12345678901234567890",
                "gemini_api_key": "AIzaSy-mock-key-12345678901234567890"
            }
        }
        manager = CloudProviderManager(config=cfg)
        self.assertIsNotNone(manager.get_provider("openai"))
        self.assertIsNotNone(manager.get_provider("anthropic"))
        self.assertIsNotNone(manager.get_provider("gemini"))

        statuses = manager.get_all_statuses()
        self.assertIn("openai", statuses)
        self.assertIn("anthropic", statuses)
        self.assertIn("gemini", statuses)

    # 13. Only one provider configured
    def test_13_only_one_provider_configured(self):
        cfg = {
            "llm": {
                "openai_api_key": "sk-mock-single-key-1234567890",
                "anthropic_api_key": "",
                "gemini_api_key": ""
            }
        }
        manager = CloudProviderManager(config=cfg)
        self.assertTrue(manager.get_provider("openai").is_available())
        self.assertFalse(manager.get_provider("anthropic").is_available())
        self.assertFalse(manager.get_provider("gemini").is_available())

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"id": "gpt-4o-mini"}]}
        with patch("requests.get", return_value=mock_resp):
            payload = manager.to_hud_payload()
            self.assertEqual(payload["available_providers_count"], 1)
            self.assertEqual(payload["overall_status"], ProviderStatus.AVAILABLE.value)

    # 14. No cloud providers configured / Cloud disabled
    def test_14_no_cloud_providers_configured_or_disabled(self):
        cfg = {"cloud_enabled": False}
        manager = CloudProviderManager(config=cfg)
        self.assertFalse(manager.cloud_enabled)
        self.assertEqual(len(manager.get_available_providers()), 0)
        self.assertIsNone(manager.get_primary_cloud_provider())

        payload = manager.to_hud_payload()
        self.assertEqual(payload["overall_status"], "DISABLED")
        self.assertEqual(payload["available_providers_count"], 0)

    # Model Roles validation
    def test_cloud_model_roles(self):
        cfg = CloudModelConfig()
        self.assertEqual(cfg.get_model_for_task(TaskCategory.CODING_TASK), "claude-3-5-sonnet-20241022")
        self.assertEqual(cfg.get_model_for_task(TaskCategory.PLANNING_TASK), "o3-mini")
        self.assertEqual(cfg.get_model_for_task(TaskCategory.COMMAND), "gpt-4o-mini")
        self.assertEqual(cfg.get_model_for_task(TaskCategory.VISION_TASK), "gpt-4o")


if __name__ == "__main__":
    unittest.main()
