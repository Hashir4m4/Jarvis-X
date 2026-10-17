"""
Cross-Device Synchronization - Domain Models.
Prompt 81 — Cross-Device Synchronization.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class SyncCategory(str, Enum):
    USER_PREFERENCES = "user_preferences"
    CONVERSATION_METADATA = "conversation_metadata"
    GOALS_AND_TASKS = "goals_and_tasks"
    PROJECT_METADATA = "project_metadata"
    NOTIFICATION_STATE = "notification_state"
    DEVICE_REGISTRATIONS = "device_registrations"


class ConflictResolutionPolicy(str, Enum):
    LAST_WRITE_WINS = "last_write_wins"
    MERGE = "merge"
    PRESERVE_HIGHER_VERSION = "preserve_higher_version"
    REJECT_ON_CONFLICT = "reject_on_conflict"


@dataclass
class SyncRecord:
    record_id: str
    user_id: str
    category: SyncCategory
    version: int
    payload: Dict[str, Any]
    source_device_id: str
    updated_at: float = field(default_factory=time.time)
    is_tombstone: bool = False  # Soft delete

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "user_id": self.user_id,
            "category": self.category.value if isinstance(self.category, SyncCategory) else self.category,
            "version": self.version,
            "payload": self.payload,
            "source_device_id": self.source_device_id,
            "updated_at": self.updated_at,
            "is_tombstone": self.is_tombstone
        }


@dataclass
class SyncPushResult:
    record_id: str
    success: bool
    current_version: int
    conflict_detected: bool = False
    resolution_applied: Optional[str] = None
    error_message: Optional[str] = None
