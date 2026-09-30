import os
import logging
from typing import Dict, Any, Optional

from .interfaces import LLMProvider
from .providers.ollama_provider import OllamaProvider
from .providers.openai_provider import OpenAICompatibleProvider
from .providers.anthropic_provider import AnthropicProvider
from .providers.gemini_provider import GeminiProvider
from .providers.mock_provider import MockLLMProvider

logger = logging.getLogger("JARVIS.LLM.Factory")


def create_llm_provider(config: Optional[Dict[str, Any]] = None) -> LLMProvider:
    """
    Factory function instantiating the configured LLM provider adapter.
    Priority:
      1. Config dictionary (`llm` or `llm_provider` block)
      2. Environment variables (`LLM_PROVIDER`, `OLLAMA_MODEL`, `OPENAI_API_KEY`, etc.)
      3. Default fallback (Ollama)
    """
    cfg = config or {}
    llm_cfg = cfg.get("llm", {})

    # Determine provider name
    provider_name = (
        llm_cfg.get("provider")
        or cfg.get("llm_provider")
        or os.getenv("LLM_PROVIDER", "ollama")
    ).lower()

    if provider_name == "ollama":
        base_url = (
            llm_cfg.get("base_url")
            or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        )
        model = (
            llm_cfg.get("model")
            or os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
        )
        temperature = float(llm_cfg.get("temperature", 0.7))
        timeout = float(llm_cfg.get("timeout", 60.0))
        logger.info(f"Instantiating Ollama LLM provider (Model: {model} @ {base_url})")
        return OllamaProvider(base_url=base_url, model=model, temperature=temperature, timeout=timeout)

    elif provider_name in ("openai", "openai_compatible", "groq", "vllm"):
        api_key = llm_cfg.get("api_key") or os.getenv("OPENAI_API_KEY", "")
        base_url = llm_cfg.get("base_url") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = llm_cfg.get("model") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        temperature = float(llm_cfg.get("temperature", 0.7))
        timeout = float(llm_cfg.get("timeout", 60.0))
        logger.info(f"Instantiating OpenAI-compatible LLM provider (Model: {model})")
        return OpenAICompatibleProvider(api_key=api_key, base_url=base_url, model=model, temperature=temperature, timeout=timeout, name=provider_name)

    elif provider_name == "anthropic":
        api_key = llm_cfg.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
        base_url = llm_cfg.get("base_url") or os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com/v1")
        model = llm_cfg.get("model") or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        temperature = float(llm_cfg.get("temperature", 0.7))
        timeout = float(llm_cfg.get("timeout", 60.0))
        logger.info(f"Instantiating Anthropic LLM provider (Model: {model})")
        return AnthropicProvider(api_key=api_key, base_url=base_url, model=model, temperature=temperature, timeout=timeout)

    elif provider_name in ("gemini", "google"):
        api_key = llm_cfg.get("api_key") or os.getenv("GEMINI_API_KEY", "")
        base_url = llm_cfg.get("base_url") or os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
        model = llm_cfg.get("model") or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        temperature = float(llm_cfg.get("temperature", 0.7))
        timeout = float(llm_cfg.get("timeout", 60.0))
        logger.info(f"Instantiating Google Gemini LLM provider (Model: {model})")
        return GeminiProvider(api_key=api_key, base_url=base_url, model=model, temperature=temperature, timeout=timeout)

    elif provider_name == "mock":
        default_resp = llm_cfg.get("mock_response", "Mock LLM response.")
        model = llm_cfg.get("model", "mock-model")
        return MockLLMProvider(default_response=default_resp, model=model)

    else:
        logger.warning(f"Unknown LLM provider '{provider_name}'. Falling back to Ollama.")
        return OllamaProvider()
