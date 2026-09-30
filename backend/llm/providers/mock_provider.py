from typing import List, Dict, Any, Generator, Optional
from ..interfaces import LLMProvider, LLMResponse, LLMErrorType


class MockLLMProvider(LLMProvider):
    """
    Mock LLM Provider for unit tests, offline operation, and predictable testing.
    """

    def __init__(
        self,
        default_response: str = "Mock LLM Response: Operational.",
        model: str = "mock-model",
        simulate_error: Optional[LLMErrorType] = None
    ):
        self._default_response = default_response
        self._model = model
        self._simulate_error = simulate_error
        self.call_history: List[List[Dict[str, str]]] = []

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model

    def set_simulate_error(self, error_type: Optional[LLMErrorType]):
        self._simulate_error = error_type

    def is_available(self) -> bool:
        return self._simulate_error != LLMErrorType.SERVICE_UNAVAILABLE

    def chat_sync(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        self.call_history.append(messages)

        if self._simulate_error:
            err_type = self._simulate_error
            err_msg = f"Simulated error: {err_type.value}"
            return LLMResponse(
                content=f"[{err_msg}]",
                model=self._model,
                provider=self.name,
                success=False,
                error=err_msg,
                error_type=err_type
            )

        return LLMResponse(
            content=self._default_response,
            model=self._model,
            provider=self.name,
            success=True,
            usage={"total_tokens": 42}
        )

    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]:
        self.call_history.append(messages)

        if self._simulate_error:
            yield f"\n[Simulated error: {self._simulate_error.value}]"
            return

        words = self._default_response.split(" ")
        for w in words:
            yield w + " "
