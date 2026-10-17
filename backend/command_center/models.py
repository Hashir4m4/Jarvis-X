"""
Desktop Command Center Domain Models.
Prompt 67 — Desktop Command Center.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class CommandExecutionState(str, Enum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class DesktopCommandRequest:
    raw_input: str
    user_id: str = "local_user"
    session_id: str = "desktop_session"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "raw_input": self.raw_input,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata)
        }


@dataclass
class DesktopCommandResult:
    request_id: str
    state: CommandExecutionState
    output_text: str
    intent_skill: Optional[str] = None
    intent_action: Optional[str] = None
    approval_required: bool = False
    approval_id: Optional[str] = None
    error_message: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "state": self.state.value if isinstance(self.state, CommandExecutionState) else str(self.state),
            "output_text": self.output_text,
            "intent_skill": self.intent_skill,
            "intent_action": self.intent_action,
            "approval_required": self.approval_required,
            "approval_id": self.approval_id,
            "error_message": self.error_message,
            "data": dict(self.data),
            "execution_time_ms": self.execution_time_ms
        }
