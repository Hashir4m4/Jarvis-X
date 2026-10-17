"""
Smart Home Integration Domain Models.
Prompt 77 — Smart Home Integration.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time


class SmartDeviceType(str, Enum):
    LIGHT = "LIGHT"
    SWITCH = "SWITCH"
    THERMOSTAT = "THERMOSTAT"
    SENSOR = "SENSOR"
    LOCK = "LOCK"
    MEDIA_PLAYER = "MEDIA_PLAYER"
    SECURITY_GATEWAY = "SECURITY_GATEWAY"


class SmartDeviceSafetyTier(str, Enum):
    STANDARD = "STANDARD"      # Lights, media volume, query status (Auto-allowed)
    CONTROLLED = "CONTROLLED"  # Thermostat target, switches (Assisted)
    HIGH_IMPACT = "HIGH_IMPACT" # Door locks, garage doors, security disarm (Explicit confirmation required)


@dataclass
class SmartDevice:
    device_id: str
    name: str
    device_type: SmartDeviceType
    provider: str
    safety_tier: SmartDeviceSafetyTier = SmartDeviceSafetyTier.STANDARD
    is_available: bool = True
    current_state: Dict[str, Any] = field(default_factory=dict)
    supported_commands: List[str] = field(default_factory=list)
    last_seen: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_stale(self, max_stale_seconds: float = 300.0) -> bool:
        return time.time() - self.last_seen > max_stale_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type.value,
            "provider": self.provider,
            "safety_tier": self.safety_tier.value,
            "is_available": self.is_available,
            "current_state": dict(self.current_state),
            "supported_commands": list(self.supported_commands),
            "last_seen": self.last_seen,
            "is_stale": self.is_stale(),
            "metadata": dict(self.metadata)
        }


@dataclass
class SmartHomeCommandResult:
    device_id: str
    command: str
    success: bool
    requires_confirmation: bool = False
    confirmation_id: Optional[str] = None
    output_message: str = ""
    new_state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "command": self.command,
            "success": self.success,
            "requires_confirmation": self.requires_confirmation,
            "confirmation_id": self.confirmation_id,
            "output_message": self.output_message,
            "new_state": self.new_state
        }
