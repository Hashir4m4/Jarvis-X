import enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Generator
from backend.llm.registry import ModelMetadata, ModelCapabilities


class ProviderStatus(enum.Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    MISCONFIGURED = "MISCONFIGURED"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    DEGRADED = "DEGRADED"


class LLMErrorType(enum.Enum):
    SERVICE_UNAVAILABLE = "service_unavailable"
    MODEL_UNAVAILABLE = "model_unavailable"
    TIMEOUT = "timeout"
    MALFORMED_RESPONSE = "malformed_response"
    AUTH_ERROR = "auth_error"
    RATE_LIMITED = "rate_limited"
    MISCONFIGURED = "misconfigured"
    UNKNOWN = "unknown"


class LLMException(Exception):
    """Base exception for provider-agnostic LLM communication errors."""
    def __init__(self, message: str, error_type: LLMErrorType = LLMErrorType.UNKNOWN, provider: str = "unknown"):
        super().__init__(message)
        self.message = message
        self.error_type = error_type
        self.provider = provider


@dataclass
class LLMResponse:
    """Unified LLM Response object across all providers."""
    content: str
    model: str
    provider: str
    success: bool = True
    error: Optional[str] = None
    error_type: Optional[LLMErrorType] = None
    usage: Dict[str, Any] = field(default_factory=dict)
    raw: Optional[Dict[str, Any]] = None


class LLMProvider(ABC):
    """
    Abstract LLM Provider interface.
    Decouples JARVIS core and agents from underlying AI backends (Ollama, OpenAI, Anthropic, Gemini, Mock).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g. 'ollama', 'openai', 'anthropic', 'gemini', 'mock')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Active model identifier."""
        pass

    @abstractmethod
    def chat_sync(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        Sends synchronous chat messages to the provider and returns structured LLMResponse.
        """
        pass

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """
        Sends streaming chat request and yields text chunks as they arrive.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Checks health and availability of the provider backend and configured model.
        """
        pass

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Convenience alias for chat_sync."""
        return self.chat_sync(messages, **kwargs)

    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse:
        """Sends a simple single-turn prompt to the model."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat_sync(messages, **kwargs)

    def list_models(self) -> List[str]:
        """Lists models supported or cached by this provider."""
        return [self.model_name]

    def list_available_models(self) -> List[str]:
        """Alias for list_models."""
        return self.list_models()

    def supports_streaming(self) -> bool:
        """Declares whether this provider supports token streaming."""
        return True

    def supports_tools(self) -> bool:
        """Declares whether this provider supports structured tool calling."""
        return True

    def supports_vision(self) -> bool:
        """Declares whether this provider supports multimodal vision input."""
        return False

    def get_capabilities(self) -> ModelCapabilities:
        """Returns ModelCapabilities dataclass of the current model."""
        return ModelCapabilities(
            text_generation=True,
            streaming=self.supports_streaming(),
            tool_calling=self.supports_tools(),
            vision=self.supports_vision(),
            structured_output=self.supports_tools()
        )

    def get_metadata(self) -> ModelMetadata:
        """Returns the full metadata for the current model. Default implementation."""
        caps = self.get_capabilities()
        return ModelMetadata(
            model_id=self.model_name,
            provider=self.name,
            local_or_online="online" if self.name in ("openai", "anthropic", "gemini") else "local",
            capabilities=caps,
            availability=self.is_available()
        )

    def health_check(self) -> Dict[str, Any]:
        """Returns structured diagnostic status of the provider."""
        available = self.is_available()
        meta = self.get_metadata()
        return {
            "provider": self.name,
            "model": self.model_name,
            "status": ProviderStatus.AVAILABLE.value if available else ProviderStatus.UNAVAILABLE.value,
            "available": available,
            "metadata": meta.to_dict()
        }
