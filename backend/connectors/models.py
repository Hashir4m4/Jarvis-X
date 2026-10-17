"""
Standardized API Integration Framework Models.
Prompt 76 — API Integration Framework.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class AuthType(str, Enum):
    API_KEY = "API_KEY"
    BEARER_TOKEN = "BEARER_TOKEN"
    OAUTH2 = "OAUTH2"
    BASIC = "BASIC"
    NONE = "NONE"


class ConnectorStatus(str, Enum):
    CONFIGURED = "CONFIGURED"
    ENABLED = "ENABLED"
    DISABLED = "DISABLED"
    DEGRADED = "DEGRADED"
    REVOKED = "REVOKED"


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class RateLimitConfig:
    max_requests_per_minute: int = 60
    current_count: int = 0
    window_start: float = field(default_factory=time.time)

    def is_rate_limited(self) -> bool:
        now = time.time()
        if now - self.window_start >= 60.0:
            self.window_start = now
            self.current_count = 0
        if self.current_count >= self.max_requests_per_minute:
            return True
        self.current_count += 1
        return False


@dataclass
class ConnectorConfig:
    connector_id: str
    name: str
    version: str
    provider: str
    auth_type: AuthType = AuthType.API_KEY
    credentials: Dict[str, str] = field(default_factory=dict)
    permission_scopes: List[str] = field(default_factory=list)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    timeout_seconds: float = 10.0
    max_retries: int = 3
    base_backoff_seconds: float = 0.5
    status: ConnectorStatus = ConnectorStatus.CONFIGURED
    supported_capabilities: List[str] = field(default_factory=list)

    def to_safe_dict(self) -> Dict[str, Any]:
        """Returns safe dictionary with secrets completely scrubbed."""
        return {
            "connector_id": self.connector_id,
            "name": self.name,
            "version": self.version,
            "provider": self.provider,
            "auth_type": self.auth_type.value,
            "permission_scopes": list(self.permission_scopes),
            "status": self.status.value,
            "supported_capabilities": list(self.supported_capabilities),
            "timeout_seconds": self.timeout_seconds,
            "has_credentials": bool(self.credentials)
        }


@dataclass
class APIResponse:
    status_code: int
    data: Any
    headers: Dict[str, str] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    is_error: bool = False
    error_message: Optional[str] = None
    rate_limited: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status_code": self.status_code,
            "data": self.data,
            "execution_time_ms": self.execution_time_ms,
            "is_error": self.is_error,
            "error_message": self.error_message,
            "rate_limited": self.rate_limited
        }
