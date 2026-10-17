import os
import time
import logging
from typing import Dict, Any, Optional, List

from .interfaces import LLMProvider, ProviderStatus
from .providers.openai_provider import OpenAICompatibleProvider
from .providers.anthropic_provider import AnthropicProvider
from .providers.gemini_provider import GeminiProvider
from .privacy_boundary import PrivacyBoundary
from .cloud_models import CloudModelConfig

logger = logging.getLogger("JARVIS.CloudManager")


class CloudProviderManager:
    """
    Central Manager for Online Cloud AI Providers.
    Manages provider lifecycles, health caches, status telemetry,
    and coordinates with the PrivacyBoundary for safe context transmission.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None, cache_ttl_seconds: float = 30.0):
        self.config = config or {}
        self.cache_ttl = cache_ttl_seconds
        self.privacy_boundary = PrivacyBoundary()
        self.cloud_models = CloudModelConfig.from_config(self.config)

        self._providers: Dict[str, LLMProvider] = {}
        self._health_cache: Dict[str, Dict[str, Any]] = {}
        self._last_health_check: float = 0.0

        # Check if cloud providers are globally enabled
        self.cloud_enabled: bool = (
            self.config.get("cloud_enabled", True)
            and os.getenv("CLOUD_PROVIDER_ENABLED", "true").lower() in ("true", "1", "yes")
        )

        self._initialize_providers()

    def _initialize_providers(self):
        """Discovers and initializes configured cloud providers without blocking startup."""
        if not self.cloud_enabled:
            logger.info("Cloud AI providers are globally disabled by configuration.")
            return

        llm_cfg = self.config.get("llm", {})

        # 1. OpenAI / OpenAI-Compatible Provider
        if "openai_api_key" in llm_cfg:
            openai_key = llm_cfg["openai_api_key"]
        else:
            openai_key = os.getenv("OPENAI_API_KEY", "")
        openai_base = llm_cfg.get("openai_base_url") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        openai_model = llm_cfg.get("openai_model") or os.getenv("OPENAI_MODEL", self.cloud_models.general_model)
        self._providers["openai"] = OpenAICompatibleProvider(
            api_key=openai_key,
            base_url=openai_base,
            model=openai_model,
            name="openai"
        )

        # 2. Anthropic Provider
        if "anthropic_api_key" in llm_cfg:
            anthropic_key = llm_cfg["anthropic_api_key"]
        else:
            anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        anthropic_model = llm_cfg.get("anthropic_model") or os.getenv("ANTHROPIC_MODEL", self.cloud_models.coding_model)
        self._providers["anthropic"] = AnthropicProvider(
            api_key=anthropic_key,
            model=anthropic_model
        )

        # 3. Google Gemini Provider
        if "gemini_api_key" in llm_cfg:
            gemini_key = llm_cfg["gemini_api_key"]
        else:
            gemini_key = os.getenv("GEMINI_API_KEY", "")
        gemini_model = llm_cfg.get("gemini_model") or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self._providers["gemini"] = GeminiProvider(
            api_key=gemini_key,
            model=gemini_model
        )

        # 4. Optional Groq (OpenAI-compatible) Provider
        if "groq_api_key" in llm_cfg:
            groq_key = llm_cfg["groq_api_key"]
        else:
            groq_key = os.getenv("GROQ_API_KEY", "")
        if groq_key:
            self._providers["groq"] = OpenAICompatibleProvider(
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
                model="llama-3.3-70b-versatile",
                name="groq"
            )

        logger.info(f"Cloud Provider Manager initialized with {len(self._providers)} providers registered.")

    def register_provider(self, name: str, provider: LLMProvider):
        """Allows dynamic registration of custom or mocked cloud providers."""
        self._providers[name] = provider
        self._health_cache.pop(name, None)

    def get_provider(self, name: str) -> Optional[LLMProvider]:
        """Retrieves a registered provider adapter by identifier."""
        return self._providers.get(name.lower())

    def get_available_providers(self) -> List[LLMProvider]:
        """Returns list of all currently available and authenticated cloud providers."""
        if not self.cloud_enabled:
            return []
        available = []
        statuses = self.get_all_statuses()
        for name, p in self._providers.items():
            st = statuses.get(name, {})
            if st.get("available", False):
                available.append(p)
        return available

    def get_primary_cloud_provider(self) -> Optional[LLMProvider]:
        """Returns the preferred or first available cloud provider."""
        available = self.get_available_providers()
        return available[0] if available else None

    def get_all_statuses(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """
        Gathers health and capability status across all cloud providers with non-blocking TTL caching.
        """
        now = time.time()
        if not force_refresh and (now - self._last_health_check < self.cache_ttl) and self._health_cache:
            return self._health_cache

        self._last_health_check = now
        results = {}

        if not self.cloud_enabled:
            for name in self._providers:
                results[name] = {
                    "provider": name,
                    "model": self._providers[name].model_name,
                    "status": ProviderStatus.UNAVAILABLE.value,
                    "available": False,
                    "error": "Cloud AI disabled"
                }
            self._health_cache = results
            return results

        for name, provider in self._providers.items():
            try:
                results[name] = provider.health_check()
            except Exception as e:
                results[name] = {
                    "provider": name,
                    "model": provider.model_name,
                    "status": ProviderStatus.UNAVAILABLE.value,
                    "available": False,
                    "error": str(e)
                }

        self._health_cache = results
        return results

    def to_hud_payload(self) -> Dict[str, Any]:
        """
        Produces clean, non-sensitive provider telemetry for HUD display.
        Guarantees no API keys or private endpoint URLs are exposed.
        """
        statuses = self.get_all_statuses()
        available_count = sum(1 for s in statuses.values() if s.get("available", False))

        cloud_status_summary = (
            ProviderStatus.AVAILABLE.value if available_count > 0
            else (ProviderStatus.UNAVAILABLE.value if self.cloud_enabled else "DISABLED")
        )

        provider_summaries = {}
        for name, st in statuses.items():
            provider_summaries[name] = {
                "status": st.get("status", ProviderStatus.UNAVAILABLE.value),
                "model": st.get("model", "unknown"),
                "available": st.get("available", False)
            }

        return {
            "cloud_enabled": self.cloud_enabled,
            "overall_status": cloud_status_summary,
            "available_providers_count": available_count,
            "providers": provider_summaries,
            "timestamp": time.time()
        }
