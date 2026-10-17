"""
Unit and Integration Tests for Prompt 76 — API Integration Framework.
"""
import pytest
import asyncio
from backend.connectors.models import (
    AuthType, ConnectorStatus, CircuitState, ConnectorConfig, RateLimitConfig, APIResponse
)
from backend.connectors.registry import APIConnectorRegistry, CircuitBreaker


@pytest.mark.asyncio
async def test_api_connector_registration_lifecycle():
    reg = APIConnectorRegistry()
    cfg = ConnectorConfig(
        connector_id="conn_weather",
        name="Weather API",
        version="1.0.0",
        provider="OpenMeteo",
        auth_type=AuthType.API_KEY,
        credentials={"api_key": "secret_xyz"},
        supported_capabilities=["get_forecast"]
    )
    reg.register_connector(cfg)
    assert reg.get_connector("conn_weather") is not None

    # Safe dict must scrub secrets
    safe = reg.list_connectors()[0]
    assert "credentials" not in safe
    assert safe["has_credentials"] is True

    # Enable and execute
    reg.enable_connector("conn_weather")
    assert cfg.status == ConnectorStatus.ENABLED

    res = await reg.execute_request("conn_weather", "get_forecast", {"city": "New York"})
    assert res.status_code == 200
    assert res.data["operation"] == "get_forecast"

    # Revoke
    reg.revoke_connector("conn_weather")
    assert cfg.status == ConnectorStatus.REVOKED
    assert len(cfg.credentials) == 0

    res_revoked = await reg.execute_request("conn_weather", "get_forecast", {})
    assert res_revoked.status_code == 403


@pytest.mark.asyncio
async def test_api_connector_rate_limiting():
    reg = APIConnectorRegistry()
    rate = RateLimitConfig(max_requests_per_minute=2)
    cfg = ConnectorConfig(
        connector_id="conn_limited",
        name="Rate Limited API",
        version="1.0.0",
        provider="Mock",
        rate_limit=rate,
        status=ConnectorStatus.ENABLED
    )
    reg.register_connector(cfg)

    # 1st request: OK
    r1 = await reg.execute_request("conn_limited", "ping", {})
    assert r1.status_code == 200

    # 2nd request: OK
    r2 = await reg.execute_request("conn_limited", "ping", {})
    assert r2.status_code == 200

    # 3rd request: Rate Limited (429)
    r3 = await reg.execute_request("conn_limited", "ping", {})
    assert r3.status_code == 429
    assert r3.rate_limited is True


@pytest.mark.asyncio
async def test_api_connector_circuit_breaker():
    reg = APIConnectorRegistry()
    cfg = ConnectorConfig(
        connector_id="conn_failing",
        name="Failing API",
        version="1.0.0",
        provider="Mock",
        status=ConnectorStatus.ENABLED,
        max_retries=1,
        base_backoff_seconds=0.01
    )
    reg.register_connector(cfg)

    def failing_adapter(c, op, p):
        raise RuntimeError("Remote gateway 502")

    reg.register_adapter("conn_failing", failing_adapter)

    # Trigger repeated failures to open circuit
    cb = reg._circuit_breakers["conn_failing"]
    cb.threshold = 2

    r1 = await reg.execute_request("conn_failing", "op", {})
    assert r1.status_code == 500

    r2 = await reg.execute_request("conn_failing", "op", {})
    assert r2.status_code == 500
    assert cb.state == CircuitState.OPEN

    # Subsequent request rejected immediately by circuit breaker
    r3 = await reg.execute_request("conn_failing", "op", {})
    assert r3.status_code == 503
    assert "Circuit breaker is OPEN" in r3.error_message
