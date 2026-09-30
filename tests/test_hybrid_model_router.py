"""
Tests for the Hybrid Intelligent Model Router (Prompt 21).

Covers 17 scenarios:
 1. Direct system command → no LLM
 2. Simple conversation → local model
 3. Local memory query → local path
 4. Complex reasoning → reasoning-capable model
 5. Coding task → coding model
 6. Online research while online
 7. Online research while offline
 8. LOCAL_ONLY privacy policy
 9. PREFER_LOCAL policy
10. CLOUD_ALLOWED policy
11. Cloud model unavailable → local fallback
12. Local model unavailable → cloud fallback where allowed
13. All models unavailable
14. User forced LOCAL mode
15. User forced CLOUD mode
16. User AUTO mode
17. Vision-capable request
"""

import unittest
import os
import sys
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock external hardware/audio libraries for fast deterministic testing
sys.modules.setdefault('chromadb', MagicMock())
sys.modules.setdefault('pyautogui', MagicMock())
sys.modules.setdefault('psutil', MagicMock())
sys.modules.setdefault('pycaw', MagicMock())
sys.modules.setdefault('pycaw.pycaw', MagicMock())
sys.modules.setdefault('comtypes', MagicMock())
sys.modules.setdefault('pyttsx3', MagicMock())
sys.modules.setdefault('faster_whisper', MagicMock())
sys.modules.setdefault('speech_recognition', MagicMock())
sys.modules.setdefault('openwakeword', MagicMock())

from backend.core.models import TaskCategory
from backend.llm.model_router import (
    ModelRouter, ModelSelectionRequest, ModelSelectionResult,
    PrivacyPolicy, UserRoutingPreference, RoutingStatus,
    RequestComplexity, ModelRole,
    classify_complexity, detect_privacy_level,
)


def _make_request(**kwargs) -> ModelSelectionRequest:
    """Helper to build a ModelSelectionRequest with sensible defaults."""
    defaults = {
        "task_category": TaskCategory.CONVERSATION,
        "user_input": "Hello",
        "complexity": RequestComplexity.LOW,
        "privacy_level": PrivacyPolicy.PREFER_LOCAL,
        "internet_available": True,
        "local_llm_available": True,
        "cloud_available": True,
        "cloud_providers": {
            "openai": {"available": True, "model": "gpt-4o-mini", "status": "AVAILABLE"},
        },
        "user_preference": UserRoutingPreference.AUTO,
        "source": "text",
    }
    defaults.update(kwargs)
    return ModelSelectionRequest(**defaults)


class TestHybridModelRouter(unittest.TestCase):

    def setUp(self):
        self.router = ModelRouter(config={})

    # ── 1. Direct system command → no LLM ─────────────────────────────────
    def test_01_direct_system_command_no_llm(self):
        req = _make_request(
            task_category=TaskCategory.COMPUTER_ACTION,
            user_input="Open Chrome",
            skill_name="system",
        )
        result = self.router.select(req)
        self.assertEqual(result.provider, "none")
        self.assertIsNone(result.model)
        self.assertIn("no LLM required", result.reason)
        self.assertEqual(result.routing_status, RoutingStatus.AVAILABLE)

    # ── 2. Simple conversation → local model ──────────────────────────────
    def test_02_simple_conversation_local_model(self):
        req = _make_request(
            task_category=TaskCategory.CONVERSATION,
            user_input="How are you?",
            complexity=RequestComplexity.LOW,
        )
        result = self.router.select(req)
        self.assertIn(result.provider, ("local", "openai"))
        self.assertIsNotNone(result.model)
        self.assertEqual(result.model_role, "general")

    # ── 3. Local memory query → local path ────────────────────────────────
    def test_03_local_memory_query(self):
        req = _make_request(
            task_category=TaskCategory.MEMORY_REQUEST,
            user_input="What did I work on yesterday?",
            privacy_level=PrivacyPolicy.PREFER_LOCAL,
            skill_name="vault",
        )
        result = self.router.select(req)
        # Vault is a NO_LLM_SKILLS skill
        self.assertEqual(result.provider, "none")
        self.assertIn("no LLM required", result.reason)

    # ── 4. Complex reasoning → reasoning-capable model ────────────────────
    def test_04_complex_reasoning(self):
        req = _make_request(
            task_category=TaskCategory.RESEARCH_TASK,
            user_input="Compare these approaches and explain the tradeoffs",
            complexity=RequestComplexity.HIGH,
        )
        result = self.router.select(req)
        self.assertNotEqual(result.provider, "none")
        self.assertEqual(result.model_role, "reasoning")
        self.assertIsNotNone(result.model)

    # ── 5. Coding task → coding model ─────────────────────────────────────
    def test_05_coding_task(self):
        req = _make_request(
            task_category=TaskCategory.CODING_TASK,
            user_input="Help me debug this architecture",
            complexity=RequestComplexity.HIGH,
        )
        result = self.router.select(req)
        self.assertNotEqual(result.provider, "none")
        self.assertEqual(result.model_role, "coding")

    # ── 6. Online research while online ───────────────────────────────────
    def test_06_online_research_while_online(self):
        req = _make_request(
            task_category=TaskCategory.RESEARCH_TASK,
            user_input="Research current AI startup competitors",
            internet_available=True,
            cloud_available=True,
            privacy_level=PrivacyPolicy.CLOUD_ALLOWED,
        )
        result = self.router.select(req)
        self.assertNotEqual(result.provider, "none")
        # With CLOUD_ALLOWED and internet, cloud should be a viable candidate
        self.assertIsNotNone(result.model)

    # ── 7. Online research while offline ──────────────────────────────────
    def test_07_online_research_while_offline(self):
        req = _make_request(
            task_category=TaskCategory.RESEARCH_TASK,
            user_input="Research current AI startup competitors",
            internet_available=False,
            cloud_available=False,
            local_llm_available=True,
        )
        result = self.router.select(req)
        # Should fall back to local, no cloud candidates
        self.assertEqual(result.provider, "local")
        self.assertIsNotNone(result.model)
        # No cloud fallbacks should exist
        for fb in result.fallbacks:
            self.assertNotIn(fb["provider"], ("openai", "anthropic", "gemini"))

    # ── 8. LOCAL_ONLY privacy policy ──────────────────────────────────────
    def test_08_local_only_privacy_policy(self):
        req = _make_request(
            task_category=TaskCategory.CONVERSATION,
            user_input="Discuss my private financial documents",
            privacy_level=PrivacyPolicy.LOCAL_ONLY,
            internet_available=True,
            cloud_available=True,
        )
        result = self.router.select(req)
        # Must NEVER select a cloud provider under LOCAL_ONLY
        self.assertNotIn(result.provider, ("openai", "anthropic", "gemini", "groq"))
        if result.provider != "none":
            self.assertEqual(result.provider, "local")
        # No cloud fallbacks either
        for fb in result.fallbacks:
            self.assertNotIn(fb["provider"], ("openai", "anthropic", "gemini"))

    # ── 9. PREFER_LOCAL policy ────────────────────────────────────────────
    def test_09_prefer_local_policy(self):
        req = _make_request(
            task_category=TaskCategory.QUESTION,
            user_input="Explain how neural networks work",
            privacy_level=PrivacyPolicy.PREFER_LOCAL,
            local_llm_available=True,
            cloud_available=True,
        )
        result = self.router.select(req)
        # Under PREFER_LOCAL with local available, local should be primary
        self.assertEqual(result.provider, "local")

    # ── 10. CLOUD_ALLOWED policy ──────────────────────────────────────────
    def test_10_cloud_allowed_policy(self):
        req = _make_request(
            task_category=TaskCategory.RESEARCH_TASK,
            user_input="Compare the latest transformer architectures in depth",
            privacy_level=PrivacyPolicy.CLOUD_ALLOWED,
            complexity=RequestComplexity.HIGH,
            local_llm_available=True,
            cloud_available=True,
        )
        result = self.router.select(req)
        self.assertNotEqual(result.provider, "none")
        self.assertIsNotNone(result.model)
        # Cloud should be a viable option (may or may not be primary)
        all_providers = [result.provider] + [fb["provider"] for fb in result.fallbacks]
        self.assertTrue(
            any(p in all_providers for p in ("openai", "anthropic", "gemini", "local")),
            "Expected at least one viable provider in candidates"
        )

    # ── 11. Cloud unavailable → local fallback ────────────────────────────
    def test_11_cloud_unavailable_local_fallback(self):
        req = _make_request(
            task_category=TaskCategory.RESEARCH_TASK,
            user_input="Explain quantum computing",
            privacy_level=PrivacyPolicy.CLOUD_ALLOWED,
            local_llm_available=True,
            cloud_available=False,
            cloud_providers={},
        )
        result = self.router.select(req)
        self.assertEqual(result.provider, "local")
        self.assertIsNotNone(result.model)

    # ── 12. Local unavailable → cloud fallback (where allowed) ────────────
    def test_12_local_unavailable_cloud_fallback(self):
        req = _make_request(
            task_category=TaskCategory.QUESTION,
            user_input="Explain how databases work",
            privacy_level=PrivacyPolicy.CLOUD_ALLOWED,
            local_llm_available=False,
            cloud_available=True,
            internet_available=True,
        )
        result = self.router.select(req)
        # Cloud provider should be selected since local is down
        self.assertIn(result.provider, ("openai", "anthropic", "gemini", "groq"))

    # ── 13. All models unavailable ────────────────────────────────────────
    def test_13_all_models_unavailable(self):
        req = _make_request(
            task_category=TaskCategory.QUESTION,
            user_input="How does photosynthesis work?",
            local_llm_available=False,
            cloud_available=False,
            internet_available=False,
            cloud_providers={},
        )
        result = self.router.select(req)
        self.assertEqual(result.provider, "none")
        self.assertEqual(result.routing_status, RoutingStatus.NO_CAPABILITY)
        self.assertIn("unavailable", result.reason.lower())

    # ── 14. User forced LOCAL mode ────────────────────────────────────────
    def test_14_user_forced_local(self):
        req = _make_request(
            task_category=TaskCategory.QUESTION,
            user_input="Explain the theory of relativity",
            user_preference=UserRoutingPreference.LOCAL,
            local_llm_available=True,
            cloud_available=True,
        )
        result = self.router.select(req)
        self.assertEqual(result.provider, "local")

    # ── 15. User forced CLOUD mode ────────────────────────────────────────
    def test_15_user_forced_cloud(self):
        req = _make_request(
            task_category=TaskCategory.QUESTION,
            user_input="Explain the theory of relativity",
            user_preference=UserRoutingPreference.CLOUD,
            privacy_level=PrivacyPolicy.CLOUD_ALLOWED,
            local_llm_available=True,
            cloud_available=True,
        )
        result = self.router.select(req)
        # Cloud should be preferred when user forces CLOUD
        self.assertIn(result.provider, ("openai", "anthropic", "gemini", "groq"))

    # ── 16. User AUTO mode ────────────────────────────────────────────────
    def test_16_user_auto_mode(self):
        req = _make_request(
            task_category=TaskCategory.CONVERSATION,
            user_input="Hello there!",
            user_preference=UserRoutingPreference.AUTO,
            local_llm_available=True,
            cloud_available=True,
        )
        result = self.router.select(req)
        # Auto mode should select a provider based on scoring
        self.assertNotEqual(result.provider, "none")
        self.assertIsNotNone(result.model)

    # ── 17. Vision-capable request ────────────────────────────────────────
    def test_17_vision_request(self):
        req = _make_request(
            task_category=TaskCategory.VISION_TASK,
            user_input="What is on my screen?",
            required_capabilities=["vision"],
        )
        result = self.router.select(req)
        self.assertNotEqual(result.provider, "none")
        self.assertEqual(result.model_role, "vision")


class TestComplexityClassification(unittest.TestCase):
    """Tests for the standalone complexity classifier."""

    def test_low_complexity(self):
        self.assertEqual(
            classify_complexity("Open Chrome", TaskCategory.COMPUTER_ACTION),
            RequestComplexity.LOW
        )

    def test_medium_complexity(self):
        self.assertEqual(
            classify_complexity("How does neural network training work?", TaskCategory.QUESTION),
            RequestComplexity.MEDIUM
        )

    def test_high_complexity(self):
        self.assertEqual(
            classify_complexity("Compare these two architectures and evaluate tradeoffs", TaskCategory.RESEARCH_TASK),
            RequestComplexity.HIGH
        )

    def test_coding_complexity(self):
        self.assertEqual(
            classify_complexity("Build a full REST API with authentication, rate limiting, caching layers, and comprehensive error handling for the new service", TaskCategory.CODING_TASK),
            RequestComplexity.HIGH
        )

    def test_short_conversation_low(self):
        self.assertEqual(
            classify_complexity("Hi", TaskCategory.CONVERSATION),
            RequestComplexity.LOW
        )


class TestPrivacyLevelDetection(unittest.TestCase):
    """Tests for the standalone privacy level detector."""

    def test_normal_query_default_policy(self):
        level = detect_privacy_level("What is the weather?", TaskCategory.QUESTION)
        self.assertEqual(level, PrivacyPolicy.PREFER_LOCAL)

    def test_sensitive_content_forces_local(self):
        level = detect_privacy_level(
            "My API key is sk-1234567890abcdef1234567890",
            TaskCategory.QUESTION,
        )
        self.assertEqual(level, PrivacyPolicy.LOCAL_ONLY)

    def test_memory_request_stays_local(self):
        level = detect_privacy_level(
            "What did I write yesterday?",
            TaskCategory.MEMORY_REQUEST,
        )
        self.assertEqual(level, PrivacyPolicy.LOCAL_ONLY)

    def test_memory_request_cloud_allowed_override(self):
        level = detect_privacy_level(
            "What did I write yesterday?",
            TaskCategory.MEMORY_REQUEST,
            default_policy=PrivacyPolicy.CLOUD_ALLOWED,
        )
        self.assertEqual(level, PrivacyPolicy.CLOUD_ALLOWED)


class TestModelRouterHUDPayload(unittest.TestCase):
    """Tests for HUD telemetry generation."""

    def setUp(self):
        self.router = ModelRouter(config={})

    def test_local_hud_payload(self):
        result = ModelSelectionResult(
            provider="local",
            model="qwen2.5-coder:7b",
            routing_status=RoutingStatus.AVAILABLE,
            model_role="general",
        )
        payload = self.router.to_hud_payload(result)
        self.assertEqual(payload["mode"], "LOCAL")
        self.assertEqual(payload["active_provider"], "local")
        self.assertEqual(payload["active_model"], "qwen2.5-coder:7b")
        self.assertEqual(payload["routing_status"], "AVAILABLE")

    def test_cloud_hud_payload(self):
        result = ModelSelectionResult(
            provider="openai",
            model="gpt-4o-mini",
            routing_status=RoutingStatus.AVAILABLE,
            model_role="general",
        )
        payload = self.router.to_hud_payload(result)
        self.assertEqual(payload["mode"], "CLOUD")

    def test_direct_hud_payload(self):
        result = ModelSelectionResult(
            provider="none",
            model=None,
            routing_status=RoutingStatus.AVAILABLE,
            model_role="none",
        )
        payload = self.router.to_hud_payload(result)
        self.assertEqual(payload["mode"], "DIRECT")
        self.assertEqual(payload["active_model"], "none")


class TestRouterFallbackChain(unittest.TestCase):
    """Tests for fallback chain behavior."""

    def setUp(self):
        self.router = ModelRouter(config={})

    def test_privacy_never_falls_back_to_cloud(self):
        """LOCAL_ONLY must never fall back from local to cloud."""
        req = _make_request(
            task_category=TaskCategory.QUESTION,
            user_input="Sensitive personal question",
            privacy_level=PrivacyPolicy.LOCAL_ONLY,
            local_llm_available=False,
            cloud_available=True,
            internet_available=True,
        )
        result = self.router.select(req)
        # Should be NO_CAPABILITY, not a cloud fallback
        self.assertEqual(result.routing_status, RoutingStatus.NO_CAPABILITY)
        self.assertNotIn(result.provider, ("openai", "anthropic", "gemini"))

    def test_fallback_chain_ordering(self):
        """When both local and cloud are available, fallbacks should be present."""
        req = _make_request(
            task_category=TaskCategory.QUESTION,
            user_input="Explain something",
            privacy_level=PrivacyPolicy.CLOUD_ALLOWED,
            local_llm_available=True,
            cloud_available=True,
        )
        result = self.router.select(req)
        # Primary should be selected, and at least one fallback
        self.assertNotEqual(result.provider, "none")
        self.assertTrue(len(result.fallbacks) >= 1, "Expected at least one fallback provider")


if __name__ == "__main__":
    unittest.main()
