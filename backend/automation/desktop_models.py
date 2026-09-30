import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


class ActionType(str, enum.Enum):
    OPEN_APPLICATION = "OPEN_APPLICATION"
    CLOSE_APPLICATION = "CLOSE_APPLICATION"
    OPEN_FILE = "OPEN_FILE"
    OPEN_FOLDER = "OPEN_FOLDER"
    CREATE_FOLDER = "CREATE_FOLDER"
    CREATE_FILE = "CREATE_FILE"
    RENAME_FILE = "RENAME_FILE"
    MOVE_FILE = "MOVE_FILE"
    COPY_FILE = "COPY_FILE"
    DELETE_FILE = "DELETE_FILE"
    LIST_DIRECTORY = "LIST_DIRECTORY"
    ORGANIZE_FILES = "ORGANIZE_FILES"
    GET_SYSTEM_INFO = "GET_SYSTEM_INFO"
    WINDOW_ACTION = "WINDOW_ACTION"
    GUI_ACTION = "GUI_ACTION"
    AUTOMATION_WORKFLOW = "AUTOMATION_WORKFLOW"


class WindowActionType(str, enum.Enum):
    MINIMIZE = "MINIMIZE"
    MAXIMIZE = "MAXIMIZE"
    RESTORE = "RESTORE"
    FOCUS = "FOCUS"
    CLOSE = "CLOSE"
    SWITCH = "SWITCH"


class RiskLevel(str, enum.Enum):
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    RESTRICTED = "RESTRICTED"


class ActionStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMING = "CONFIRMING"
    EXECUTING = "EXECUTING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DENIED = "DENIED"


@dataclass
class DesktopAction:
    """
    Structured Desktop Action representing an intent to control computer resources.
    The AI specifies WHAT is desired; controlled tools determine HOW.
    """
    action_type: ActionType
    target: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: f"act_{uuid.uuid4().hex[:8]}")
    risk_level: RiskLevel = RiskLevel.SAFE
    requires_confirmation: bool = False
    status: ActionStatus = ActionStatus.PENDING
    source: str = "orchestrator"
    timestamp: float = field(default_factory=time.time)
    error: Optional[str] = None
    verified: bool = False

    def __post_init__(self):
        # Automatically assign default risk level and confirmation requirement based on action type if not explicitly set
        if self.action_type in (
            ActionType.DELETE_FILE,
            ActionType.CLOSE_APPLICATION,
        ):
            self.risk_level = RiskLevel.RESTRICTED
            self.requires_confirmation = True
        elif self.action_type == ActionType.ORGANIZE_FILES:
            self.risk_level = RiskLevel.RESTRICTED
            self.requires_confirmation = True
        elif self.action_type in (
            ActionType.CREATE_FOLDER,
            ActionType.CREATE_FILE,
            ActionType.RENAME_FILE,
            ActionType.MOVE_FILE,
            ActionType.COPY_FILE,
        ):
            self.risk_level = RiskLevel.CONFIRM
            if self.parameters.get("bulk", False) or len(self.parameters.get("files", [])) > 1:
                self.risk_level = RiskLevel.RESTRICTED
                self.requires_confirmation = True
        elif self.action_type in (
            ActionType.OPEN_APPLICATION,
            ActionType.OPEN_FILE,
            ActionType.OPEN_FOLDER,
            ActionType.LIST_DIRECTORY,
            ActionType.GET_SYSTEM_INFO,
            ActionType.WINDOW_ACTION,
        ):
            self.risk_level = RiskLevel.SAFE
            self.requires_confirmation = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value if hasattr(self.action_type, "value") else str(self.action_type),
            "target": self.target,
            "parameters": self.parameters,
            "risk_level": self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level),
            "requires_confirmation": self.requires_confirmation,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "source": self.source,
            "timestamp": self.timestamp,
            "error": self.error,
            "verified": self.verified,
        }


@dataclass
class DesktopActionResult:
    """Represents the outcome of a desktop action execution."""
    success: bool
    action_id: str
    action_type: ActionType
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    verified: bool = False
    risk_level: RiskLevel = RiskLevel.SAFE
    status: ActionStatus = ActionStatus.VERIFIED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action_id": self.action_id,
            "action_type": self.action_type.value if hasattr(self.action_type, "value") else str(self.action_type),
            "message": self.message,
            "data": self.data,
            "verified": self.verified,
            "risk_level": self.risk_level.value if hasattr(self.risk_level, "value") else str(self.risk_level),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
        }
