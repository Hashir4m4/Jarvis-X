"""
Hardware Control Layer Domain Models.
Prompt 79 — Hardware Control Layer.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time


class HardwareCategory(str, Enum):
    AUDIO = "AUDIO"
    DISPLAY = "DISPLAY"
    POWER = "POWER"
    NETWORK_ADAPTER = "NETWORK_ADAPTER"
    STORAGE = "STORAGE"
    SYSTEM_CORE = "SYSTEM_CORE"


class HardwarePrivilegeLevel(str, Enum):
    READ_ONLY = "READ_ONLY"          # Status, volume query, battery query (Auto)
    SAFE_CONTROL = "SAFE_CONTROL"    # Volume adjust, brightness adjust (Standard)
    PRIVILEGED = "PRIVILEGED"        # Power plan, adapter restart, driver query (Requires approval)


@dataclass
class HardwareDeviceProfile:
    device_id: str
    name: str
    category: HardwareCategory
    privilege_level: HardwarePrivilegeLevel = HardwarePrivilegeLevel.READ_ONLY
    is_available: bool = True
    capabilities: List[str] = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    unsupported_features: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "category": self.category.value,
            "privilege_level": self.privilege_level.value,
            "is_available": self.is_available,
            "capabilities": list(self.capabilities),
            "state": dict(self.state),
            "unsupported_features": list(self.unsupported_features)
        }


@dataclass
class HardwareCommandResult:
    device_id: str
    action: str
    success: bool
    requires_approval: bool = False
    approval_token: Optional[str] = None
    output_message: str = ""
    resulting_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "action": self.action,
            "success": self.success,
            "requires_approval": self.requires_approval,
            "approval_token": self.approval_token,
            "output_message": self.output_message,
            "resulting_state": self.resulting_state
        }
