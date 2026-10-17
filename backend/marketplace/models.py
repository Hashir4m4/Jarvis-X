"""
JARVIS Extension Marketplace Architecture - Domain Models.
Prompt 85 — Extension Marketplace Architecture.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class ExtensionStatus(str, Enum):
    UNINSTALLED = "uninstalled"
    INSTALLED = "installed"
    ENABLED = "enabled"
    DISABLED = "disabled"
    QUARANTINED = "quarantined"


class ExtensionPermissionScope(str, Enum):
    READ_NOTIFICATIONS = "read:notifications"
    POST_NOTIFICATIONS = "post:notifications"
    READ_STATUS = "read:status"
    READ_WORKSPACE = "read:workspace"
    EXEC_COMMANDS = "exec:commands"
    HARDWARE_CONTROL = "hardware:control"
    NETWORK_ACCESS = "network:access"


@dataclass
class ExtensionManifest:
    extension_id: str
    name: str
    version: str
    author: str
    description: str
    required_permissions: List[ExtensionPermissionScope]
    min_jarvis_version: str = "1.0.0"
    signature: Optional[str] = None
    checksum: str = ""
    dependencies: List[str] = field(default_factory=list)

    def validate(self) -> tuple[bool, Optional[str]]:
        if not self.extension_id or not self.name or not self.version:
            return False, "Missing mandatory manifest metadata (extension_id, name, or version)."
        # Prohibit unrestricted wildcard permissions
        if "*" in [p.value if isinstance(p, ExtensionPermissionScope) else p for p in self.required_permissions]:
            return False, "Dangerous permission manifest: Wildcard permissions '*' are prohibited."
        return True, None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "extension_id": self.extension_id,
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "required_permissions": [p.value if isinstance(p, ExtensionPermissionScope) else p for p in self.required_permissions],
            "min_jarvis_version": self.min_jarvis_version,
            "signature": self.signature,
            "checksum": self.checksum,
            "dependencies": self.dependencies
        }


@dataclass
class InstalledExtensionRecord:
    manifest: ExtensionManifest
    status: ExtensionStatus = ExtensionStatus.INSTALLED
    installed_at: float = field(default_factory=time.time)
    approved_permissions: List[ExtensionPermissionScope] = field(default_factory=list)
    audit_events: List[str] = field(default_factory=list)
