import unittest
import os
import sys
import json
from unittest.mock import patch, MagicMock
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.llm.interfaces import LLMProvider, LLMResponse, LLMErrorType
from backend.llm.providers.ollama_provider import OllamaProvider
from backend.llm.providers.openai_provider import OpenAICompatibleProvider
from backend.llm.providers.mock_provider import MockLLMProvider
from backend.llm.factory import create_llm_provider
from backend.llm_client import LLMClient


class TestLLMProviderAgnostic(unittest.TestCase):
    def test_factory_provider_resolution(self):
        """Verify factory resolves provider based on configuration."""
        # 1. Ollama
        p1 = create_llm_provider({"llm": {"provider": "ollama", "model": "qwen2.5-coder:7b"}})
        self.assertIsInstance(p1, OllamaProvider)
        self.assertEqual(p1.name, "ollama")
        self.assertEqual(p1.model_name, "qwen2.5-coder:7b")

        # 2. OpenAI
        p2 = create_llm_provider({"llm": {"provider": "openai", "model": "gpt-4o"}})
        self.assertIsInstance(p2, OpenAICompatibleProvider)
        self.assertEqual(p2.name, "openai")
        self.assertEqual(p2.model_name, "gpt-4o")

        # 3. Mock
        p3 = create_llm_provider({"llm": {"provider": "mock", "mock_response": "Hello"}})
        self.assertIsInstance(p3, MockLLMProvider)
        self.assertEqual(p3.name, "mock")

    @patch("requests.post")
    def test_ollama_successful_chat(self, mock_post):
        """Verify successful synchronous and streaming chat with Ollama."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "model": "qwen2.5-coder:7b",
            "message": {"role": "assistant", "content": "Analysis complete."},
            "total_duration": 120000
        }
        mock_post.return_value = mock_resp

        provider = OllamaProvider(model="qwen2.5-coder:7b")
        res = provider.chat_sync([{"role": "user", "content": "Analyze system"}])

        self.assertTrue(res.success)
        self.assertEqual(res.content, "Analysis complete.")
        self.assertEqual(res.provider, "ollama")
        self.assertEqual(res.model, "qwen2.5-coder:7b")

    @patch("requests.post")
    def test_ollama_service_unavailable(self, mock_post):
        """Verify graceful reporting when Ollama daemon is unreachable."""
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        provider = OllamaProvider()
        res = provider.chat_sync([{"role": "user", "content": "Hello"}])

        self.assertFalse(res.success)
        self.assertEqual(res.error_type, LLMErrorType.SERVICE_UNAVAILABLE)
        self.assertIn("service unavailable", res.error.lower())
        self.assertIn("service unavailable", res.content.lower())

    @patch("requests.post")
    def test_ollama_model_unavailable(self, mock_post):
        """Verify graceful reporting when requested model is not found/pulled."""
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_post.return_value = mock_resp

        provider = OllamaProvider(model="non_existent_model:latest")
        res = provider.chat_sync([{"role": "user", "content": "Hello"}])

        self.assertFalse(res.success)
        self.assertEqual(res.error_type, LLMErrorType.MODEL_UNAVAILABLE)
        self.assertIn("unavailable", res.error)

    @patch("requests.post")
    def test_ollama_timeout(self, mock_post):
        """Verify graceful reporting when Ollama request times out."""
        mock_post.side_effect = requests.exceptions.Timeout("Read timeout")

        provider = OllamaProvider(timeout=5.0)
        res = provider.chat_sync([{"role": "user", "content": "Heavy task"}])

        self.assertFalse(res.success)
        self.assertEqual(res.error_type, LLMErrorType.TIMEOUT)
        self.assertIn("timed out", res.error.lower())

    @patch("requests.post")
    def test_ollama_malformed_response(self, mock_post):
        """Verify graceful reporting when Ollama returns invalid/corrupted JSON."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
        mock_post.return_value = mock_resp

        provider = OllamaProvider()
        res = provider.chat_sync([{"role": "user", "content": "Hello"}])

        self.assertFalse(res.success)
        self.assertEqual(res.error_type, LLMErrorType.MALFORMED_RESPONSE)
        self.assertIn("malformed", res.error.lower())

    @patch("requests.post")
    def test_openai_compatible_provider(self, mock_post):
        """Verify OpenAI-compatible provider adapter."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"role": "assistant", "content": "OpenAI Output"}}]
        }
        mock_post.return_value = mock_resp

        provider = OpenAICompatibleProvider(api_key="sk-test", model="gpt-4o")
        res = provider.chat_sync([{"role": "user", "content": "Test"}])

        self.assertTrue(res.success)
        self.assertEqual(res.content, "OpenAI Output")
        self.assertEqual(res.provider, "openai")

    def test_llm_client_backward_compatibility(self):
        """Verify existing LLMClient interface works seamlessly with provider adapters."""
        mock_p = MockLLMProvider(default_response="Seamless compatibility test")
        client = LLMClient(mock_p)

        self.assertEqual(client.provider_name, "mock")
        self.assertEqual(client.model, "mock-model")

        # Sync
        resp_text = client.chat_sync([{"role": "user", "content": "Ping"}])
        self.assertEqual(resp_text, "Seamless compatibility test")

        # Stream
        stream_chunks = list(client.chat_stream([{"role": "user", "content": "Ping"}]))
        self.assertTrue(len(stream_chunks) > 0)
        self.assertIn("Seamless ", "".join(stream_chunks))


if __name__ == "__main__":
    unittest.main()
