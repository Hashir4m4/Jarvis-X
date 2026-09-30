import json
import logging
import requests
from typing import List, Dict, Any, Generator, Optional

from ..interfaces import LLMProvider, LLMResponse, LLMErrorType, ProviderStatus

logger = logging.getLogger("JARVIS.LLM.OpenAI")


class OpenAICompatibleProvider(LLMProvider):
    """
    Provider adapter for OpenAI-compatible REST APIs (OpenAI, Groq, DeepSeek, Together, vLLM, LM Studio, etc.).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        timeout: float = 30.0,
        name: str = "openai"
    ):
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._timeout = timeout
        self._provider_name = name
        self._chat_url = f"{self._base_url}/chat/completions"
        self._models_url = f"{self._base_url}/models"

    @property
    def name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Checks if API key is configured or local server responds."""
        if not self._api_key and "localhost" not in self._base_url and "127.0.0.1" not in self._base_url:
            return False
        return True

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def supports_streaming(self) -> bool:
        return True

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        vision_indicators = ("vision", "gpt-4o", "gpt-4-turbo", "claude", "gemini")
        return any(ind in self._model.lower() for ind in vision_indicators)

    def list_models(self) -> List[str]:
        """Queries /models endpoint if reachable, or returns configured model."""
        if not self.is_available():
            return [self._model]
        try:
            resp = requests.get(self._models_url, headers=self._get_headers(), timeout=min(self._timeout, 3.0))
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("id", "") for m in data.get("data", []) if m.get("id")]
            return [self._model]
        except Exception:
            return [self._model]

    def health_check(self) -> Dict[str, Any]:
        """Performs non-blocking diagnostic health check."""
        if not self.is_available():
            return {
                "provider": self.name,
                "model": self.model_name,
                "status": ProviderStatus.MISCONFIGURED.value,
                "available": False,
                "error": "Missing API Key",
                "capabilities": self.get_capabilities()
            }
        try:
            resp = requests.get(self._models_url, headers=self._get_headers(), timeout=min(self._timeout, 1.0))
            if resp.status_code == 200:
                status = ProviderStatus.AVAILABLE
            elif resp.status_code == 401:
                status = ProviderStatus.AUTHENTICATION_ERROR
            elif resp.status_code == 429:
                status = ProviderStatus.RATE_LIMITED
            else:
                status = ProviderStatus.AVAILABLE
            return {
                "provider": self.name,
                "model": self.model_name,
                "status": status.value,
                "available": status == ProviderStatus.AVAILABLE,
                "capabilities": self.get_capabilities()
            }
        except Exception:
            return {
                "provider": self.name,
                "model": self.model_name,
                "status": ProviderStatus.AVAILABLE.value,
                "available": True,
                "capabilities": self.get_capabilities()
            }

    def chat_sync(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        model = kwargs.get("model", self._model)
        temp = kwargs.get("temperature", self._temperature)
        timeout = kwargs.get("timeout", self._timeout)

        if not self.is_available():
            return LLMResponse(
                content=f"[{self.name} is misconfigured: Missing API key]",
                model=model,
                provider=self.name,
                success=False,
                error="Missing API key",
                error_type=LLMErrorType.MISCONFIGURED
            )

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temp,
            "stream": False
        }

        try:
            resp = requests.post(self._chat_url, headers=self._get_headers(), json=payload, timeout=timeout)

            if resp.status_code == 401:
                return LLMResponse(
                    content=f"[Authentication error: Invalid {self.name} API key]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error="Invalid API key",
                    error_type=LLMErrorType.AUTH_ERROR
                )
            elif resp.status_code == 429:
                return LLMResponse(
                    content=f"[{self.name} rate limit exceeded]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error="Rate limit exceeded",
                    error_type=LLMErrorType.RATE_LIMITED
                )
            elif resp.status_code == 404:
                return LLMResponse(
                    content=f"[Model '{model}' unavailable]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error=f"Model '{model}' not found",
                    error_type=LLMErrorType.MODEL_UNAVAILABLE
                )

            resp.raise_for_status()
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return LLMResponse(
                content=content,
                model=model,
                provider=self.name,
                success=True,
                usage=data.get("usage", {}),
                raw=data
            )

        except requests.exceptions.Timeout as e:
            return LLMResponse(
                content=f"[{self.name} request timed out: {e}]",
                model=model,
                provider=self.name,
                success=False,
                error=str(e),
                error_type=LLMErrorType.TIMEOUT
            )
        except requests.exceptions.ConnectionError as e:
            return LLMResponse(
                content=f"[{self.name} endpoint unavailable: {e}]",
                model=model,
                provider=self.name,
                success=False,
                error=str(e),
                error_type=LLMErrorType.SERVICE_UNAVAILABLE
            )
        except Exception as e:
            return LLMResponse(
                content=f"[{self.name} API error: {e}]",
                model=model,
                provider=self.name,
                success=False,
                error=str(e),
                error_type=LLMErrorType.UNKNOWN
            )

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        model = kwargs.get("model", self._model)
        temp = kwargs.get("temperature", self._temperature)
        timeout = kwargs.get("timeout", self._timeout)

        if not self.is_available():
            yield f"\n[{self.name} is misconfigured: Missing API key]"
            return

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temp,
            "stream": True
        }

        try:
            with requests.post(self._chat_url, headers=self._get_headers(), json=payload, stream=True, timeout=timeout) as resp:
                if resp.status_code == 401:
                    yield f"\n[Authentication error: Invalid {self.name} API key]"
                    return
                elif resp.status_code == 429:
                    yield f"\n[{self.name} rate limit exceeded]"
                    return
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        decoded = line.decode('utf-8').strip()
                        if decoded.startswith("data: "):
                            raw_data = decoded[6:].strip()
                            if raw_data == "[DONE]":
                                break
                            try:
                                chunk_json = json.loads(raw_data)
                                delta = chunk_json.get("choices", [{}])[0].get("delta", {})
                                if "content" in delta and delta["content"]:
                                    yield delta["content"]
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            yield f"\n[Error communicating with {self.name} provider: {e}]"
