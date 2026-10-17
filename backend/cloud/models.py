"""
Personal Cloud Intelligence - Domain Models.
Prompt 83 — Personal Cloud Intelligence.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class CloudSyncScope(str, Enum):
    VAULT_NOTES = "vault_notes"
    GOALS_AND_PLANS = "goals_and_plans"
    SETTINGS_AND_CONFIG = "settings_and_config"
    FULL_SNAPSHOT = "full_snapshot"


class BackupStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    RESTORED = "restored"


@dataclass
class PersonalCloudConfig:
    enabled: bool = False  # Completely optional and disabled by default
    provider_name: str = "local_encrypted_cloud"
    encryption_algorithm: str = "AES-256-GCM"
    backup_retention_days: int = 30
    allowed_scopes: List[CloudSyncScope] = field(default_factory=lambda: [
        CloudSyncScope.VAULT_NOTES,
        CloudSyncScope.GOALS_AND_PLANS,
        CloudSyncScope.SETTINGS_AND_CONFIG
    ])


@dataclass
class CloudBackupMetadata:
    backup_id: str
    user_id: str
    scope: CloudSyncScope
    created_at: float = field(default_factory=time.time)
    size_bytes: int = 0
    checksum: str = ""
    status: BackupStatus = BackupStatus.PENDING
    is_encrypted: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "user_id": self.user_id,
            "scope": self.scope.value if isinstance(self.scope, CloudSyncScope) else self.scope,
            "created_at": self.created_at,
            "size_bytes": self.size_bytes,
            "checksum": self.checksum,
            "status": self.status.value if isinstance(self.status, BackupStatus) else self.status,
            "is_encrypted": self.is_encrypted
        }
