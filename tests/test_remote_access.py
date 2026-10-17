"""
Unit Tests for Prompt 82 — Secure Remote JARVIS Access.
"""
import pytest
import time
from backend.remote.models import RemoteAccessRole, RemoteSessionState, RemoteAccessConfig
from backend.remote.service import SecureRemoteAccessGateway


def test_remote_access_default_disabled():
    gateway = SecureRemoteAccessGateway()
    gateway.register_client_credential("client_test", "super_secret_key_123")

    # Disabled by default
    res = gateway.authenticate_client("client_test", "super_secret_key_123", "192.168.1.50")
    assert res.success is False
    assert "disabled" in res.error_message.lower()

    # Enable and authenticate
    gateway.enable_remote_access()
    res_enabled = gateway.authenticate_client("client_test", "super_secret_key_123", "192.168.1.50")
    assert res_enabled.success is True
    assert res_enabled.session is not None


def test_remote_access_brute_force_lockout():
    config = RemoteAccessConfig(enabled=True, max_failed_attempts=3, lockout_duration_seconds=10)
    gateway = SecureRemoteAccessGateway(config)
    gateway.register_client_credential("admin_box", "correct_passcode")

    # 3 bad attempts
    for _ in range(3):
        res = gateway.authenticate_client("admin_box", "wrong_passcode", "10.0.0.99")
        assert res.success is False

    # 4th attempt is locked out even with correct password
    res_lockout = gateway.authenticate_client("admin_box", "correct_passcode", "10.0.0.99")
    assert res_lockout.success is False
    assert res_lockout.is_locked_out is True


def test_remote_session_role_validation_and_disable():
    gateway = SecureRemoteAccessGateway(RemoteAccessConfig(enabled=True))
    gateway.register_client_credential("operator_client", "op_secret")

    res = gateway.authenticate_client("operator_client", "op_secret", "192.168.1.10", role=RemoteAccessRole.OPERATOR)
    assert res.success is True
    token = res.session.token

    # Validate operator role
    valid_op = gateway.validate_request(token, required_role=RemoteAccessRole.OPERATOR)
    assert valid_op is not None

    # Reject elevation to ADMIN
    valid_admin = gateway.validate_request(token, required_role=RemoteAccessRole.ADMIN)
    assert valid_admin is None

    # Global emergency kill switch
    gateway.disable_remote_access()
    assert gateway.validate_request(token) is None
