"""
Cross-Device Synchronization Engine.
Prompt 81 — Cross-Device Synchronization.
"""
import logging
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict

from backend.sync.models import (
    SyncCategory, ConflictResolutionPolicy, SyncRecord, SyncPushResult
)

logger = logging.getLogger("JARVIS.SyncEngine")


class CrossDeviceSyncEngine:
    """
    Multi-client state synchronizer with conflict resolution, soft-deletions (tombstones),
    bounded offline queues, and user isolation.
    """

    def __init__(self):
        # user_id -> record_id -> SyncRecord
        self._store: Dict[str, Dict[str, SyncRecord]] = defaultdict(dict)
        # device_id -> List[SyncRecord]
        self._offline_queues: Dict[str, List[SyncRecord]] = defaultdict(list)
        self._max_offline_queue = 500

    def push_record(
        self,
        user_id: str,
        record_id: str,
        category: SyncCategory,
        version: int,
        payload: Dict[str, Any],
        source_device_id: str,
        policy: ConflictResolutionPolicy = ConflictResolutionPolicy.PRESERVE_HIGHER_VERSION,
        is_tombstone: bool = False
    ) -> SyncPushResult:
        user_records = self._store[user_id]
        existing = user_records.get(record_id)

        if not existing:
            new_record = SyncRecord(
                record_id=record_id,
                user_id=user_id,
                category=category,
                version=version,
                payload=payload,
                source_device_id=source_device_id,
                is_tombstone=is_tombstone
            )
            user_records[record_id] = new_record
            return SyncPushResult(record_id=record_id, success=True, current_version=version)

        # Conflict check
        if version <= existing.version:
            # Incoming version is older or same
            if policy == ConflictResolutionPolicy.REJECT_ON_CONFLICT:
                return SyncPushResult(
                    record_id=record_id,
                    success=False,
                    current_version=existing.version,
                    conflict_detected=True,
                    resolution_applied="rejected",
                    error_message=f"Conflict: Incoming version {version} <= existing version {existing.version}"
                )
            elif policy == ConflictResolutionPolicy.LAST_WRITE_WINS:
                existing.version = existing.version + 1
                existing.payload = payload
                existing.source_device_id = source_device_id
                existing.updated_at = time.time()
                existing.is_tombstone = is_tombstone
                return SyncPushResult(
                    record_id=record_id,
                    success=True,
                    current_version=existing.version,
                    conflict_detected=True,
                    resolution_applied="last_write_wins_incremented"
                )
            else:  # PRESERVE_HIGHER_VERSION
                return SyncPushResult(
                    record_id=record_id,
                    success=False,
                    current_version=existing.version,
                    conflict_detected=True,
                    resolution_applied="preserved_existing"
                )

        # Normal upgrade
        existing.version = version
        existing.payload = payload
        existing.source_device_id = source_device_id
        existing.updated_at = time.time()
        existing.is_tombstone = is_tombstone

        return SyncPushResult(record_id=record_id, success=True, current_version=version)

    def pull_changes(
        self,
        user_id: str,
        category: Optional[SyncCategory] = None,
        since_timestamp: float = 0.0,
        include_tombstones: bool = True
    ) -> List[Dict[str, Any]]:
        user_records = self._store.get(user_id, {})
        results = []
        for rec in user_records.values():
            if rec.updated_at >= since_timestamp:
                if category and rec.category != category:
                    continue
                if not include_tombstones and rec.is_tombstone:
                    continue
                results.append(rec.to_dict())
        return results

    def enqueue_offline_change(self, device_id: str, record: SyncRecord) -> bool:
        queue = self._offline_queues[device_id]
        if len(queue) >= self._max_offline_queue:
            logger.warning(f"Offline queue full for device {device_id}. Dropping oldest.")
            queue.pop(0)
        queue.append(record)
        return True

    def flush_offline_queue(self, device_id: str) -> List[SyncRecord]:
        queue = self._offline_queues.pop(device_id, [])
        return queue
