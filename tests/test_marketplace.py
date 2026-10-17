"""
Unit Tests for Prompt 85 — JARVIS Extension Marketplace Architecture.
"""
import pytest
import hashlib
from backend.marketplace.models import ExtensionStatus, ExtensionPermissionScope
from backend.marketplace.service import ExtensionRegistryService


def test_extension_install_permission_consent_enforcement():
    service = ExtensionRegistryService()
    manifest_data = {
        "extension_id": "ext_weather_tracker",
        "name": "Live Weather Extension",
        "version": "1.0.0",
        "required_permissions": ["read:status", "network:access"]
    }

    # Installation blocked if user did not approve all requested permissions
    success, record, err = service.install_extension(
        manifest_data,
        approved_permissions=[ExtensionPermissionScope.READ_STATUS]
    )
    assert success is False
    assert "network:access" in err

    # Installation succeeds with full consent
    success_ok, record_ok, msg = service.install_extension(
        manifest_data,
        approved_permissions=[ExtensionPermissionScope.READ_STATUS, ExtensionPermissionScope.NETWORK_ACCESS]
    )
    assert success_ok is True
    assert record_ok.status == ExtensionStatus.ENABLED
    assert service.verify_action_permission("ext_weather_tracker", ExtensionPermissionScope.NETWORK_ACCESS) is True


def test_extension_integrity_checksum_verification():
    service = ExtensionRegistryService()
    pkg_bytes = b"import sys\nprint('Weather Extension Runtime')"
    correct_hash = hashlib.sha256(pkg_bytes).hexdigest()

    manifest_data = {
        "extension_id": "ext_calc",
        "name": "Calculator",
        "version": "1.0.0",
        "required_permissions": ["read:status"]
    }

    # Failed checksum mismatch
    success, _, err = service.install_extension(
        manifest_data,
        package_bytes=pkg_bytes,
        expected_checksum="bad_checksum_hash_12345",
        approved_permissions=[ExtensionPermissionScope.READ_STATUS]
    )
    assert success is False
    assert "Integrity verification failed" in err

    # Successful integrity check
    success_ok, rec, _ = service.install_extension(
        manifest_data,
        package_bytes=pkg_bytes,
        expected_checksum=correct_hash,
        approved_permissions=[ExtensionPermissionScope.READ_STATUS]
    )
    assert success_ok is True


def test_extension_lifecycle_disable_quarantine_uninstall():
    service = ExtensionRegistryService()
    manifest_data = {
        "extension_id": "ext_notes",
        "name": "Quick Notes",
        "version": "1.0.0",
        "required_permissions": ["read:status"]
    }
    service.install_extension(manifest_data, approved_permissions=[ExtensionPermissionScope.READ_STATUS])

    # Disable
    assert service.disable_extension("ext_notes") is True
    assert service.verify_action_permission("ext_notes", ExtensionPermissionScope.READ_STATUS) is False

    # Quarantine
    assert service.quarantine_extension("ext_notes", reason="Suspicious activity") is True
    assert service.verify_action_permission("ext_notes", ExtensionPermissionScope.READ_STATUS) is False

    # Uninstall
    assert service.uninstall_extension("ext_notes") is True
    assert len(service.list_extensions()) == 0
