"""
Unit Tests for Prompt 84 — JARVIS Developer SDK.
"""
import pytest
from backend.sdk.client import SDKAuthScheme, SDKClientConfig, SDKResponse, JarvisSDKClient


def test_sdk_client_unauthorized_token_missing():
    config = SDKClientConfig(endpoint_url="http://localhost:8000", token="")
    client = JarvisSDKClient(config)

    res = client.get_system_status()
    assert res.is_success is False
    assert res.status_code == 401
    assert "Missing SDK token" in res.error


def test_sdk_client_typed_operations_with_transport():
    def mock_transport(method: str, path: str, payload: dict) -> SDKResponse:
        if path == "/api/v1/system/status":
            return SDKResponse(status_code=200, data={"core_status": "RUNNING", "version": "1.0.0"})
        elif path == "/api/v1/notifications":
            return SDKResponse(status_code=201, data={"notification_id": "notif_sdk_1", "title": payload["title"]})
        elif path == "/api/v1/goals":
            return SDKResponse(status_code=200, data={"goals": [{"id": "g1", "title": "Test Goal"}]})
        return SDKResponse(status_code=404, error="Endpoint not found")

    config = SDKClientConfig(endpoint_url="http://localhost:8000", token="valid_dev_token_xyz")
    client = JarvisSDKClient(config, transport_adapter=mock_transport)

    status_res = client.get_system_status()
    assert status_res.is_success is True
    assert status_res.data["core_status"] == "RUNNING"

    notif_res = client.post_notification("Build Succeeded", "All test suites passed.")
    assert notif_res.is_success is True
    assert notif_res.status_code == 201
    assert notif_res.data["notification_id"] == "notif_sdk_1"

    goals_res = client.list_goals()
    assert goals_res.is_success is True
    assert len(goals_res.data["goals"]) == 1


def test_sdk_client_command_execution():
    def mock_transport(method: str, path: str, payload: dict) -> SDKResponse:
        if "rm -rf" in payload.get("query", ""):
            return SDKResponse(status_code=400, error="Rejected by Command Safety Gate.")
        return SDKResponse(status_code=200, data={"result": "Command processed successfully."})

    config = SDKClientConfig(token="test_token")
    client = JarvisSDKClient(config, transport_adapter=mock_transport)

    # Safe query
    safe_res = client.execute_command("Show active tasks")
    assert safe_res.is_success is True

    # Dangerous query rejected
    dangerous_res = client.execute_command("rm -rf /")
    assert dangerous_res.is_success is False
    assert dangerous_res.status_code == 400
