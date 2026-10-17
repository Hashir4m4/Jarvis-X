"""
Unit Tests for Prompt 83 — Personal Cloud Intelligence.
"""
import pytest
from backend.cloud.models import CloudSyncScope, BackupStatus, PersonalCloudConfig
from backend.cloud.service import PersonalCloudService


def test_cloud_service_optional_default_disabled():
    cloud = PersonalCloudService()
    # When disabled, backup creation returns None safely
    meta = cloud.create_encrypted_backup("u1", CloudSyncScope.VAULT_NOTES, {"note_1": "Content"})
    assert meta is None

    # Enable and create
    cloud.enable_cloud_sync()
    meta_enabled = cloud.create_encrypted_backup("u1", CloudSyncScope.VAULT_NOTES, {"note_1": "Content"})
    assert meta_enabled is not None
    assert meta_enabled.status == BackupStatus.COMPLETED
    assert meta_enabled.checksum != ""


def test_cloud_backup_restoration_and_integrity():
    cloud = PersonalCloudService(PersonalCloudConfig(enabled=True))
    payload = {"goals": ["Ship Phase 6", "Verify Prompts 76-85"]}
    meta = cloud.create_encrypted_backup("u2", CloudSyncScope.GOALS_AND_PLANS, payload)
    assert meta is not None

    # Verify restoration
    success, restored_data, msg = cloud.restore_backup("u2", meta.backup_id)
    assert success is True
    assert restored_data == payload
    assert meta.status == BackupStatus.RESTORED


def test_cloud_user_isolation_and_deletion():
    cloud = PersonalCloudService(PersonalCloudConfig(enabled=True))
    meta1 = cloud.create_encrypted_backup("user_alice", CloudSyncScope.SETTINGS_AND_CONFIG, {"theme": "dark"})
    meta2 = cloud.create_encrypted_backup("user_bob", CloudSyncScope.SETTINGS_AND_CONFIG, {"theme": "light"})

    # Alice cannot access Bob's backup
    success, data, msg = cloud.restore_backup("user_alice", meta2.backup_id)
    assert success is False
    assert data is None

    # Deletion
    deleted = cloud.delete_user_backup("user_alice", meta1.backup_id)
    assert deleted is True
    assert len(cloud.list_user_backups("user_alice")) == 0
