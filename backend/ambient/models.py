"""
Ambient Intelligence Mode Models.
Prompt 74 — Ambient Intelligence Mode.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time


class AmbientOperatingMode(str, Enum):
    DISABLED = "DISABLED"
    STANDBY = "STANDBY"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


@dataclass
class AmbientSuggestion:
    suggestion_id: str
    title: str
    rationale: str
    action_type: Optional[str] = None
    action_payload: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8
    requires_approval: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "title": self.title,
            "rationale": self.rationale,
            "action_type": self.action_type,
            "action_payload": dict(self.action_payload),
            "confidence": self.confidence,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at
        }


@dataclass
class AmbientConfiguration:
    enabled: bool = False
    schedule_start: str = "09:00"
    schedule_end: str = "18:00"
    session_timeout_seconds: float = 3600.0  # 1 hour auto-standby
    cooldown_seconds: float = 300.0
    allowed_signals: List[str] = field(default_factory=lambda: [
        "system_health", "workflow_progress", "schedule_alerts"
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "schedule_start": self.schedule_start,
            "schedule_end": self.schedule_end,
            "session_timeout_seconds": self.session_timeout_seconds,
            "cooldown_seconds": self.cooldown_seconds,
            "allowed_signals": list(self.allowed_signals)
        }
