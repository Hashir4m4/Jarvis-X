"""
Unit Tests for Prompt 81 — Cross-Device Synchronization.
"""
import pytest
from backend.sync.models import SyncCategory, ConflictResolutionPolicy, SyncRecord
from backend.sync.service import CrossDeviceSyncEngine


def test_cross_device_sync_versioning_and_pull():
    engine = CrossDeviceSyncEngine()

    res1 = engine.push_record(
        user_id="user_1",
        record_id="pref_theme",
        category=SyncCategory.USER_PREFERENCES,
        version=1,
        payload={"theme": "dark", "accent": "cyan"},
        source_device_id="desktop_primary"
    )
    assert res1.success is True
    assert res1.current_version == 1

    # Upgrade version from mobile
    res2 = engine.push_record(
        user_id="user_1",
        record_id="pref_theme",
        category=SyncCategory.USER_PREFERENCES,
        version=2,
        payload={"theme": "dark", "accent": "emerald"},
        source_device_id="mobile_companion"
    )
    assert res2.success is True
    assert res2.current_version == 2

    # Pull changes
    changes = engine.pull_changes("user_1", category=SyncCategory.USER_PREFERENCES)
    assert len(changes) == 1
    assert changes[0]["payload"]["accent"] == "emerald"


def test_cross_device_sync_conflict_handling():
    engine = CrossDeviceSyncEngine()

    engine.push_record(
        user_id="user_1",
        record_id="goal_101",
        category=SyncCategory.GOALS_AND_TASKS,
        version=5,
        payload={"title": "Deploy Phase 6", "done": False},
        source_device_id="desktop"
    )

    # Stale version push with REJECT_ON_CONFLICT policy
    res_stale = engine.push_record(
        user_id="user_1",
        record_id="goal_101",
        category=SyncCategory.GOALS_AND_TASKS,
        version=3,
        payload={"title": "Old Task", "done": False},
        source_device_id="laptop",
        policy=ConflictResolutionPolicy.REJECT_ON_CONFLICT
    )
    assert res_stale.success is False
    assert res_stale.conflict_detected is True
    assert res_stale.current_version == 5


def test_tombstone_soft_deletion_and_offline_queue():
    engine = CrossDeviceSyncEngine()

    # Create record
    engine.push_record(
        user_id="user_2",
        record_id="notif_99",
        category=SyncCategory.NOTIFICATION_STATE,
        version=1,
        payload={"text": "Alert"},
        source_device_id="dev_a"
    )

    # Soft delete (tombstone)
    engine.push_record(
        user_id="user_2",
        record_id="notif_99",
        category=SyncCategory.NOTIFICATION_STATE,
        version=2,
        payload={},
        source_device_id="dev_a",
        is_tombstone=True
    )

    # Pull excluding tombstones
    active = engine.pull_changes("user_2", include_tombstones=False)
    assert len(active) == 0

    # Offline queue buffering
    rec = SyncRecord(
        record_id="offline_rec_1",
        user_id="user_2",
        category=SyncCategory.USER_PREFERENCES,
        version=1,
        payload={"sync": True},
        source_device_id="dev_b"
    )
    engine.enqueue_offline_change("dev_b", rec)
    flushed = engine.flush_offline_queue("dev_b")
    assert len(flushed) == 1
    assert flushed[0].record_id == "offline_rec_1"
