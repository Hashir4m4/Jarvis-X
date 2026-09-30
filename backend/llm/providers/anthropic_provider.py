import json
import logging
import requests
from typing import List, Dict, Any, Generator, Optional

from ..interfaces import LLMProvider, LLMResponse, LLMErrorType, ProviderStatus

logger = logging.getLogger("JARVIS.LLM.Anthropic")


class AnthropicProvider(LLMProvider):
    """
    Provider adapter for Anthropic Claude REST Messages API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.anthropic.com/v1",
        model: str = "claude-3-5-sonnet-20241022",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        timeout: float = 30.0
    ):
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout = timeout
        self._messages_url = f"{self._base_url}/messages"

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def model_name(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Checks if Anthropic API key is provided."""
        return bool(self._api_key)

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    def supports_streaming(self) -> bool:
        return True

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    def list_models(self) -> List[str]:
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            self._model
        ]

    def health_check(self) -> Dict[str, Any]:
        """Performs non-blocking diagnostic health check for Anthropic API."""
        if not self.is_available():
            return {
                "provider": self.name,
                "model": self.model_name,
                "status": ProviderStatus.MISCONFIGURED.value,
                "available": False,
                "error": "Missing Anthropic API Key",
                "capabilities": self.get_capabilities()
            }
        return {
            "provider": self.name,
            "model": self.model_name,
            "status": ProviderStatus.AVAILABLE.value,
            "available": True,
            "capabilities": self.get_capabilities()
        }

    def _prepare_payload(self, messages: List[Dict[str, str]], model: str, temp: float, stream: bool) -> Dict[str, Any]:
        system_prompt = ""
        user_assistant_msgs = []

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_prompt = (system_prompt + "\n" + content).strip()
            else:
                user_assistant_msgs.append({"role": role, "content": content})

        if not user_assistant_msgs:
            user_assistant_msgs.append({"role": "user", "content": "Hello"})

        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": self._max_tokens,
            "messages": user_assistant_msgs,
            "temperature": temp,
            "stream": stream
        }
        if system_prompt:
            payload["system"] = system_prompt
        return payload

    def chat_sync(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        model = kwargs.get("model", self._model)
        temp = kwargs.get("temperature", self._temperature)
        timeout = kwargs.get("timeout", self._timeout)

        if not self.is_available():
            return LLMResponse(
                content="[Anthropic provider is misconfigured: Missing ANTHROPIC_API_KEY]",
                model=model,
                provider=self.name,
                success=False,
                error="Missing API key",
                error_type=LLMErrorType.MISCONFIGURED
            )

        payload = self._prepare_payload(messages, model, temp, stream=False)

        try:
            resp = requests.post(self._messages_url, headers=self._get_headers(), json=payload, timeout=timeout)

            if resp.status_code == 401:
                return LLMResponse(
                    content="[Authentication error: Invalid Anthropic API key]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error="Invalid API key",
                    error_type=LLMErrorType.AUTH_ERROR
                )
            elif resp.status_code == 429:
                return LLMResponse(
                    content="[Anthropic rate limit exceeded]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error="Rate limit exceeded",
                    error_type=LLMErrorType.RATE_LIMITED
                )
            elif resp.status_code == 404:
                return LLMResponse(
                    content=f"[Anthropic model '{model}' not found]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error=f"Model '{model}' not found",
                    error_type=LLMErrorType.MODEL_UNAVAILABLE
                )

            resp.raise_for_status()
            data = resp.json()
            content_blocks = data.get("content", [])
            content_text = "".join([b.get("text", "") for b in content_blocks if b.get("type") == "text"])

            return LLMResponse(
                content=content_text,
                model=model,
                provider=self.name,
                success=True,
                usage=data.get("usage", {}),
                raw=data
            )

        except requests.exceptions.Timeout as e:
            return LLMResponse(
                content=f"[Anthropic request timed out: {e}]",
                model=model,
                provider=self.name,
                success=False,
                error=str(e),
                error_type=LLMErrorType.TIMEOUT
            )
        except requests.exceptions.ConnectionError as e:
            return LLMResponse(
                content=f"[Anthropic endpoint unavailable: {e}]",
                model=model,
                provider=self.name,
                success=False,
                error=str(e),
                error_type=LLMErrorType.SERVICE_UNAVAILABLE
            )
        except Exception as e:
            return LLMResponse(
                content=f"[Anthropic API error: {e}]",
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
            yield "\n[Anthropic provider is misconfigured: Missing ANTHROPIC_API_KEY]"
            return

        payload = self._prepare_payload(messages, model, temp, stream=True)

        try:
            with requests.post(self._messages_url, headers=self._get_headers(), json=payload, stream=True, timeout=timeout) as resp:
                if resp.status_code == 401:
                    yield "\n[Authentication error: Invalid Anthropic API key]"
                    return
                elif resp.status_code == 429:
                    yield "\n[Anthropic rate limit exceeded]"
                    return
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        decoded = line.decode('utf-8').strip()
                        if decoded.startswith("data: "):
                            raw_data = decoded[6:].strip()
                            try:
                                chunk = json.loads(raw_data)
                                if chunk.get("type") == "content_block_delta":
                                    delta = chunk.get("delta", {})
                                    if delta.get("type") == "text_delta":
                                        yield delta.get("text", "")
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            yield f"\n[Error communicating with Anthropic provider: {e}]"
