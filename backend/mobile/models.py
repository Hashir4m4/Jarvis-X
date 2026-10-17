"""
Mobile Companion System - Domain Models.
Prompt 80 — Mobile Companion System.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class MobileDevicePlatform(str, Enum):
    IOS = "ios"
    ANDROID = "android"
    PWA = "pwa"
    RESPONSIVE_WEB = "responsive_web"


class MobileSessionStatus(str, Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


@dataclass
class MobileDeviceRegistration:
    device_id: str
    user_id: str
    device_name: str
    platform: MobileDevicePlatform
    registered_at: float = field(default_factory=time.time)
    last_active_at: float = field(default_factory=time.time)
    push_token: Optional[str] = None
    is_trusted: bool = True
    revoked: bool = False

    def to_safe_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "user_id": self.user_id,
            "device_name": self.device_name,
            "platform": self.platform.value if isinstance(self.platform, MobileDevicePlatform) else self.platform,
            "registered_at": self.registered_at,
            "last_active_at": self.last_active_at,
            "is_trusted": self.is_trusted,
            "revoked": self.revoked
        }


@dataclass
class MobileSession:
    session_id: str
    device_id: str
    user_id: str
    token: str
    scopes: List[str]
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 86400)  # 24h
    status: MobileSessionStatus = MobileSessionStatus.ACTIVE

    def is_valid(self) -> bool:
        if self.status != MobileSessionStatus.ACTIVE:
            return False
        if time.time() > self.expires_at:
            self.status = MobileSessionStatus.EXPIRED
            return False
        return True
