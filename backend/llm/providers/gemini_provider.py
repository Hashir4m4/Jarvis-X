import json
import logging
import requests
from typing import List, Dict, Any, Generator, Optional

from ..interfaces import LLMProvider, LLMResponse, LLMErrorType, ProviderStatus

logger = logging.getLogger("JARVIS.LLM.Gemini")


class GeminiProvider(LLMProvider):
    """
    Provider adapter for Google Gemini REST API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        model: str = "gemini-1.5-flash",
        temperature: float = 0.7,
        timeout: float = 30.0
    ):
        self._api_key = api_key or ""
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._timeout = timeout

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def is_available(self) -> bool:
        """Checks if Gemini API key is provided."""
        return bool(self._api_key)

    def supports_streaming(self) -> bool:
        return True

    def supports_tools(self) -> bool:
        return True

    def supports_vision(self) -> bool:
        return True

    def list_models(self) -> List[str]:
        return [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-2.0-flash",
            self._model
        ]

    def health_check(self) -> Dict[str, Any]:
        """Performs non-blocking diagnostic health check for Gemini API."""
        if not self.is_available():
            return {
                "provider": self.name,
                "model": self.model_name,
                "status": ProviderStatus.MISCONFIGURED.value,
                "available": False,
                "error": "Missing GEMINI_API_KEY",
                "capabilities": self.get_capabilities()
            }
        return {
            "provider": self.name,
            "model": self.model_name,
            "status": ProviderStatus.AVAILABLE.value,
            "available": True,
            "capabilities": self.get_capabilities()
        }

    def _prepare_contents(self, messages: List[Dict[str, str]]) -> tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        contents = []
        system_instruction = None

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            else:
                gemini_role = "model" if role in ("assistant", "system_reply") else "user"
                contents.append({
                    "role": gemini_role,
                    "parts": [{"text": content}]
                })

        if not contents:
            contents.append({"role": "user", "parts": [{"text": "Hello"}]})

        return contents, system_instruction

    def chat_sync(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        model = kwargs.get("model", self._model)
        temp = kwargs.get("temperature", self._temperature)
        timeout = kwargs.get("timeout", self._timeout)

        if not self.is_available():
            return LLMResponse(
                content="[Gemini provider is misconfigured: Missing GEMINI_API_KEY]",
                model=model,
                provider=self.name,
                success=False,
                error="Missing API key",
                error_type=LLMErrorType.MISCONFIGURED
            )

        contents, system_inst = self._prepare_contents(messages)
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temp}
        }
        if system_inst:
            payload["systemInstruction"] = system_inst

        url = f"{self._base_url}/models/{model}:generateContent?key={self._api_key}"

        try:
            resp = requests.post(url, json=payload, timeout=timeout)

            if resp.status_code in (400, 403):
                return LLMResponse(
                    content="[Authentication error: Invalid Gemini API key]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error="Invalid API key",
                    error_type=LLMErrorType.AUTH_ERROR
                )
            elif resp.status_code == 429:
                return LLMResponse(
                    content="[Gemini rate limit exceeded]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error="Rate limit exceeded",
                    error_type=LLMErrorType.RATE_LIMITED
                )
            elif resp.status_code == 404:
                return LLMResponse(
                    content=f"[Gemini model '{model}' not found]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error=f"Model '{model}' not found",
                    error_type=LLMErrorType.MODEL_UNAVAILABLE
                )

            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            text_parts = []
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for p in parts:
                    if "text" in p:
                        text_parts.append(p["text"])
            content_text = "".join(text_parts)

            return LLMResponse(
                content=content_text,
                model=model,
                provider=self.name,
                success=True,
                usage=data.get("usageMetadata", {}),
                raw=data
            )

        except requests.exceptions.Timeout as e:
            return LLMResponse(
                content=f"[Gemini request timed out: {e}]",
                model=model,
                provider=self.name,
                success=False,
                error=str(e),
                error_type=LLMErrorType.TIMEOUT
            )
        except requests.exceptions.ConnectionError as e:
            return LLMResponse(
                content=f"[Gemini endpoint unavailable: {e}]",
                model=model,
                provider=self.name,
                success=False,
                error=str(e),
                error_type=LLMErrorType.SERVICE_UNAVAILABLE
            )
        except Exception as e:
            return LLMResponse(
                content=f"[Gemini API error: {e}]",
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
            yield "\n[Gemini provider is misconfigured: Missing GEMINI_API_KEY]"
            return

        contents, system_inst = self._prepare_contents(messages)
        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temp}
        }
        if system_inst:
            payload["systemInstruction"] = system_inst

        url = f"{self._base_url}/models/{model}:streamGenerateContent?alt=sse&key={self._api_key}"

        try:
            with requests.post(url, json=payload, stream=True, timeout=timeout) as resp:
                if resp.status_code in (400, 403):
                    yield "\n[Authentication error: Invalid Gemini API key]"
                    return
                elif resp.status_code == 429:
                    yield "\n[Gemini rate limit exceeded]"
                    return
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        decoded = line.decode('utf-8').strip()
                        if decoded.startswith("data: "):
                            raw_data = decoded[6:].strip()
                            try:
                                chunk = json.loads(raw_data)
                                candidates = chunk.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    for p in parts:
                                        if "text" in p:
                                            yield p["text"]
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            yield f"\n[Error communicating with Gemini provider: {e}]"
