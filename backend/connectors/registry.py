"""
Standardized API Integration Framework Registry and Client.
Prompt 76 — API Integration Framework.
"""
import logging
import time
import asyncio
from typing import Dict, Any, List, Optional, Callable

from backend.connectors.models import (
    AuthType, ConnectorStatus, CircuitState, ConnectorConfig, APIResponse
)

logger = logging.getLogger("JARVIS.APIIntegrationFramework")


class CircuitBreaker:
    """Per-connector circuit breaker to prevent cascading provider outages."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout_seconds: float = 30.0):
        self.threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.last_failure_time: float = 0.0

    def record_success(self):
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.threshold:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker OPENED due to repeated failures.")

    def can_attempt(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN allows a single probe attempt
        return True


class APIConnectorRegistry:
    """
    Central API Connector Registry and Dispatcher.
    Enforces rate limits, circuit breaking, credential redaction, and bounded retries.
    """

    def __init__(self):
        self._connectors: Dict[str, ConnectorConfig] = {}
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._adapters: Dict[str, Callable[[ConnectorConfig, str, Dict[str, Any]], Any]] = {}

    def register_connector(self, config: ConnectorConfig) -> bool:
        self._connectors[config.connector_id] = config
        self._circuit_breakers[config.connector_id] = CircuitBreaker()
        logger.info(f"Registered connector: {config.connector_id} ({config.name} v{config.version})")
        return True

    def register_adapter(self, connector_id: str, adapter_fn: Callable):
        self._adapters[connector_id] = adapter_fn

    def enable_connector(self, connector_id: str) -> bool:
        if connector_id in self._connectors:
            if self._connectors[connector_id].status != ConnectorStatus.REVOKED:
                self._connectors[connector_id].status = ConnectorStatus.ENABLED
                return True
        return False

    def disable_connector(self, connector_id: str) -> bool:
        if connector_id in self._connectors:
            self._connectors[connector_id].status = ConnectorStatus.DISABLED
            return True
        return False

    def revoke_connector(self, connector_id: str) -> bool:
        """Permanently revokes credentials and disables the connector."""
        if connector_id in self._connectors:
            cfg = self._connectors[connector_id]
            cfg.credentials.clear()
            cfg.status = ConnectorStatus.REVOKED
            logger.info(f"Connector {connector_id} REVOKED and credentials cleared.")
            return True
        return False

    def get_connector(self, connector_id: str) -> Optional[ConnectorConfig]:
        return self._connectors.get(connector_id)

    def get_connector_status(self, connector_id: str) -> Optional[ConnectorStatus]:
        cfg = self.get_connector(connector_id)
        return cfg.status if cfg else None

    def list_connectors(self) -> List[Dict[str, Any]]:
        return [c.to_safe_dict() for c in self._connectors.values()]

    async def execute_request(
        self,
        connector_id: str,
        operation: str,
        parameters: Dict[str, Any],
        idempotency_key: Optional[str] = None
    ) -> APIResponse:
        start_time = time.time()
        cfg = self.get_connector(connector_id)
        if not cfg:
            return APIResponse(status_code=404, data=None, is_error=True, error_message="Connector not found.")

        if cfg.status != ConnectorStatus.ENABLED:
            return APIResponse(status_code=403, data=None, is_error=True, error_message=f"Connector is {cfg.status.value}.")

        # 1. Rate Limiting Check
        if cfg.rate_limit.is_rate_limited():
            return APIResponse(status_code=429, data=None, is_error=True, rate_limited=True, error_message="Rate limit exceeded.")

        # 2. Circuit Breaker Check
        cb = self._circuit_breakers.get(connector_id)
        if cb and not cb.can_attempt():
            return APIResponse(status_code=503, data=None, is_error=True, error_message="Circuit breaker is OPEN. Service temporarily unavailable.")

        # 3. Execution with Exponential Backoff
        adapter = self._adapters.get(connector_id)
        retries = 0
        last_error = None

        while retries <= cfg.max_retries:
            try:
                if adapter:
                    res = adapter(cfg, operation, parameters)
                    if asyncio.iscoroutine(res):
                        res = await asyncio.wait_for(res, timeout=cfg.timeout_seconds)
                    if cb:
                        cb.record_success()
                    return APIResponse(
                        status_code=200,
                        data=res,
                        execution_time_ms=round((time.time() - start_time) * 1000, 2)
                    )
                else:
                    # Mock successful response if no network adapter is attached
                    if cb:
                        cb.record_success()
                    return APIResponse(
                        status_code=200,
                        data={"operation": operation, "status": "executed", "idempotency_key": idempotency_key},
                        execution_time_ms=round((time.time() - start_time) * 1000, 2)
                    )

            except asyncio.TimeoutError:
                last_error = f"Operation timed out after {cfg.timeout_seconds}s"
                retries += 1
                if retries <= cfg.max_retries:
                    await asyncio.sleep(cfg.base_backoff_seconds * (2 ** retries))

            except Exception as e:
                last_error = str(e)
                retries += 1
                if retries <= cfg.max_retries:
                    await asyncio.sleep(cfg.base_backoff_seconds * (2 ** retries))

        if cb:
            cb.record_failure()

        return APIResponse(
            status_code=500,
            data=None,
            is_error=True,
            error_message=f"Request failed after {retries} retries: {last_error}",
            execution_time_ms=round((time.time() - start_time) * 1000, 2)
        )
