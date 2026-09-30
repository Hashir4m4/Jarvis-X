import logging
from typing import List, Dict, Any, Generator, Optional, Union

from backend.llm.interfaces import LLMProvider, LLMResponse
from backend.llm.factory import create_llm_provider

logger = logging.getLogger("JARVIS.LLMClient")


class LLMClient:
    """
    Provider-Agnostic LLM Client for JARVIS OS.
    Delegates all chat and streaming operations to configured LLMProvider adapters (Ollama, OpenAI, Mock).
    Maintains 100% backward compatibility for existing callers.
    """

    def __init__(self, config_or_provider: Optional[Union[Dict[str, Any], LLMProvider]] = None):
        if isinstance(config_or_provider, LLMProvider):
            self.provider = config_or_provider
        else:
            self.provider = create_llm_provider(config_or_provider or {})

        # Backward compatibility properties
        self.model = self.provider.model_name
        self.provider_name = self.provider.name

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Sends streaming chat request through the active provider adapter."""
        return self.provider.chat_stream(messages, **kwargs)

    def chat_sync(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Sends synchronous chat request and returns content string."""
        response: LLMResponse = self.provider.chat_sync(messages, **kwargs)
        return response.content

    def is_available(self) -> bool:
        """Checks if active provider backend is healthy and available."""
        return self.provider.is_available()
