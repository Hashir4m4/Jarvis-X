"""
Unit Tests for Prompt 80 — Mobile Companion System.
"""
import pytest
import time
from backend.mobile.models import MobileDevicePlatform, MobileSessionStatus
from backend.mobile.service import MobileCompanionService


def test_mobile_device_registration_and_session():
    service = MobileCompanionService(token_ttl_seconds=3600)
    device = service.register_device(
        user_id="user_admin",
        device_name="Pixel 9 Pro",
        platform=MobileDevicePlatform.ANDROID
    )
    assert device.device_id.startswith("mob_")
    assert device.revoked is False

    session = service.create_session(
        device_id=device.device_id,
        user_id="user_admin",
        scopes=["read:status", "exec:commands"]
    )
    assert session is not None
    assert session.status == MobileSessionStatus.ACTIVE

    # Authenticate with valid scope
    auth_res = service.authenticate_token(session.token, required_scope="read:status")
    assert auth_res is not None
    assert auth_res.session_id == session.session_id

    # Reject unauthorized scope
    scope_fail = service.authenticate_token(session.token, required_scope="admin:firmware")
    assert scope_fail is None


def test_mobile_device_revocation():
    service = MobileCompanionService()
    device = service.register_device(
        user_id="user_test",
        device_name="iPhone 16",
        platform=MobileDevicePlatform.IOS
    )
    session = service.create_session(device_id=device.device_id, user_id="user_test")
    assert session is not None

    # Verify session works
    assert service.authenticate_token(session.token) is not None

    # Revoke device
    revoked = service.revoke_device(device.device_id)
    assert revoked is True

    # Immediate session invalidation
    assert service.authenticate_token(session.token) is None

    # New session creation blocked
    new_sess = service.create_session(device_id=device.device_id, user_id="user_test")
    assert new_sess is None


def test_mobile_session_expiration():
    # 1 second TTL
    service = MobileCompanionService(token_ttl_seconds=1)
    device = service.register_device(user_id="u1", device_name="PWA Client", platform=MobileDevicePlatform.PWA)
    session = service.create_session(device_id=device.device_id, user_id="u1")
    assert session is not None

    time.sleep(1.2)
    # Session expired
    assert service.authenticate_token(session.token) is None
