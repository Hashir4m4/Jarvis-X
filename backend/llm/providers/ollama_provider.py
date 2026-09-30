import json
import logging
import requests
from typing import List, Dict, Any, Generator, Optional

from ..interfaces import LLMProvider, LLMResponse, LLMErrorType

logger = logging.getLogger("JARVIS.LLM.Ollama")


class OllamaProvider(LLMProvider):
    """
    Provider adapter for local Ollama API.
    Handles streaming and synchronous chat with comprehensive error diagnostics.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:7b",
        temperature: float = 0.7,
        timeout: float = 60.0
    ):
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._timeout = timeout
        self._chat_url = f"{self._base_url}/api/chat"
        self._tags_url = f"{self._base_url}/api/tags"

    @property
    def name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    def list_models(self) -> List[str]:
        """Lists models currently installed and available in the local Ollama daemon."""
        try:
            resp = requests.get(self._tags_url, timeout=0.5)
            if resp.status_code == 200:
                data = resp.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
            return []
        except Exception:
            return []

    def is_available(self) -> bool:
        """Checks if local Ollama daemon is reachable and model is listed."""
        try:
            models = self.list_models()
            if not models:
                # If tags returned empty or request failed, check tags status code
                resp = requests.get(self._tags_url, timeout=0.5)
                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
            return any(self._model in m or m in self._model for m in models)
        except Exception:
            return False

    def health_check(self) -> Dict[str, Any]:
        """Returns detailed Ollama daemon and model health."""
        models = self.list_models()
        is_daemon_up = len(models) > 0
        if not is_daemon_up:
            try:
                resp = requests.get(self._tags_url, timeout=2.0)
                is_daemon_up = (resp.status_code == 200)
            except Exception:
                is_daemon_up = False
        model_present = any(self._model in m or m in self._model for m in models)
        return {
            "provider": self.name,
            "base_url": self._base_url,
            "configured_model": self._model,
            "daemon_online": is_daemon_up,
            "model_available": model_present,
            "available_models": models,
            "status": "healthy" if (is_daemon_up and model_present) else ("model_missing" if is_daemon_up else "offline"),
            "available": is_daemon_up and model_present
        }

    def chat_sync(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """Sends synchronous chat request to Ollama with graceful error diagnostics."""
        model = kwargs.get("model", self._model)
        temp = kwargs.get("temperature", self._temperature)
        timeout = kwargs.get("timeout", self._timeout)

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temp}
        }

        try:
            response = requests.post(self._chat_url, json=payload, timeout=timeout)
            
            # Check model missing 404
            if response.status_code == 404:
                err_msg = f"Ollama model '{model}' unavailable. Please run 'ollama pull {model}'."
                logger.error(f"[OLLAMA] {err_msg}")
                return LLMResponse(
                    content=f"[{err_msg}]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error=err_msg,
                    error_type=LLMErrorType.MODEL_UNAVAILABLE
                )

            response.raise_for_status()

            try:
                data = response.json()
            except json.JSONDecodeError as e:
                err_msg = f"Malformed JSON response from Ollama: {e}"
                logger.error(f"[OLLAMA] {err_msg}")
                return LLMResponse(
                    content=f"[{err_msg}]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error=err_msg,
                    error_type=LLMErrorType.MALFORMED_RESPONSE
                )

            # Check internal error payload in response
            if "error" in data:
                err_text = data["error"]
                err_type = LLMErrorType.MODEL_UNAVAILABLE if "not found" in err_text.lower() else LLMErrorType.UNKNOWN
                return LLMResponse(
                    content=f"[{err_text}]",
                    model=model,
                    provider=self.name,
                    success=False,
                    error=err_text,
                    error_type=err_type
                )

            content = data.get("message", {}).get("content", "")
            return LLMResponse(
                content=content,
                model=model,
                provider=self.name,
                success=True,
                usage={
                    "total_duration": data.get("total_duration"),
                    "eval_count": data.get("eval_count")
                },
                raw=data
            )

        except requests.exceptions.Timeout as e:
            err_msg = f"Ollama request timed out after {timeout}s: {e}"
            logger.error(f"[OLLAMA] {err_msg}")
            return LLMResponse(
                content=f"[{err_msg}]",
                model=model,
                provider=self.name,
                success=False,
                error=err_msg,
                error_type=LLMErrorType.TIMEOUT
            )

        except (requests.exceptions.ConnectionError, requests.exceptions.SSLError) as e:
            err_msg = f"Ollama service unavailable at {self._base_url}. Ensure Ollama daemon is running."
            logger.error(f"[OLLAMA] {err_msg}")
            return LLMResponse(
                content=f"[{err_msg}]",
                model=model,
                provider=self.name,
                success=False,
                error=err_msg,
                error_type=LLMErrorType.SERVICE_UNAVAILABLE
            )

        except requests.exceptions.RequestException as e:
            err_msg = f"Ollama HTTP error: {e}"
            logger.error(f"[OLLAMA] {err_msg}")
            return LLMResponse(
                content=f"[{err_msg}]",
                model=model,
                provider=self.name,
                success=False,
                error=err_msg,
                error_type=LLMErrorType.UNKNOWN
            )

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        """Streams chat tokens from Ollama with graceful error yielding."""
        model = kwargs.get("model", self._model)
        temp = kwargs.get("temperature", self._temperature)
        timeout = kwargs.get("timeout", self._timeout)

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temp}
        }

        try:
            with requests.post(self._chat_url, json=payload, stream=True, timeout=timeout) as response:
                if response.status_code == 404:
                    yield f"\n[Error: Ollama model '{model}' unavailable. Please run 'ollama pull {model}']"
                    return

                response.raise_for_status()

                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        try:
                            data = json.loads(decoded_line)
                            if "error" in data:
                                yield f"\n[Ollama Error: {data['error']}]"
                                return
                            if "message" in data and "content" in data["message"]:
                                yield data["message"]["content"]
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to decode Ollama streaming JSON: {e}")

        except requests.exceptions.Timeout:
            yield f"\n[Error: Ollama request timed out after {timeout}s]"
        except (requests.exceptions.ConnectionError, requests.exceptions.SSLError):
            yield f"\n[Error: Ollama service unavailable at {self._base_url}]"
        except requests.exceptions.RequestException as e:
            yield f"\n[Error communicating with Ollama: {e}]"
