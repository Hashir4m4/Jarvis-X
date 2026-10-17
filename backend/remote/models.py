"""
Secure Remote JARVIS Access - Domain Models.
Prompt 82 — Secure Remote Access.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class RemoteAccessRole(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


class RemoteSessionState(str, Enum):
    ACTIVE = "active"
    TERMINATED = "terminated"
    REVOKED = "revoked"
    LOCKED_OUT = "locked_out"


@dataclass
class RemoteAccessConfig:
    enabled: bool = False  # Disabled by default
    require_tls: bool = True
    max_failed_attempts: int = 5
    lockout_duration_seconds: int = 900  # 15 minutes
    session_timeout_seconds: int = 3600  # 1 hour
    allowed_roles: List[RemoteAccessRole] = field(default_factory=lambda: [RemoteAccessRole.OPERATOR, RemoteAccessRole.ADMIN])


@dataclass
class RemoteAccessSession:
    session_id: str
    client_id: str
    client_ip: str
    role: RemoteAccessRole
    token: str
    created_at: float = field(default_factory=time.time)
    expires_at: float = field(default_factory=lambda: time.time() + 3600)
    state: RemoteSessionState = RemoteSessionState.ACTIVE

    def is_valid(self) -> bool:
        if self.state != RemoteSessionState.ACTIVE:
            return False
        if time.time() > self.expires_at:
            self.state = RemoteSessionState.TERMINATED
            return False
        return True


@dataclass
class RemoteAuthResult:
    success: bool
    session: Optional[RemoteAccessSession] = None
    error_message: Optional[str] = None
    is_locked_out: bool = False
