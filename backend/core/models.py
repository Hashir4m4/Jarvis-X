from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
import time
import uuid


class InputChannel(str, Enum):
    """Supported input ingestion channels."""
    TEXT = "text"
    VOICE = "voice"
    HUD = "hud"
    SCHEDULED = "scheduled"
    API = "api"
    UI = "ui"


class IntentType(str, Enum):
    """High-level categories of user intent."""
    SYSTEM_CONTROL = "system_control"
    APP_CONTROL = "app_control"
    FILE_MANAGEMENT = "file_management"
    CODING_TASK = "coding_task"
    VISION_QUERY = "vision_query"
    PLUGIN = "plugin"
    CONVERSATION = "conversation"
    UNKNOWN = "unknown"


class TaskCategory(str, Enum):
    """Granular categorization of tasks determined by the Intelligence Orchestrator."""
    CONVERSATION = "conversation"
    QUESTION = "question"
    COMMAND = "command"
    RESEARCH_TASK = "research_task"
    COMPUTER_ACTION = "computer_action"
    CODING_TASK = "coding_task"
    PLANNING_TASK = "planning_task"
    MEMORY_REQUEST = "memory_request"
    VISION_TASK = "vision_task"
    MULTI_STEP_TASK = "multi_step_task"
    SCHEDULED_TASK = "scheduled_task"
    UNKNOWN = "unknown"


class TaskStatus(str, Enum):
    """Status of an active multi-step task."""
    ACTIVE = "ACTIVE"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class OperatingState(str, Enum):
    """HUD and Core Operating States."""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"


class ExecutionState(str, Enum):
    """Fine-grained lifecycle states within the Orchestrator pipeline."""
    IDLE = "IDLE"
    RECEIVED = "RECEIVED"
    UNDERSTANDING = "UNDERSTANDING"
    RETRIEVING_CONTEXT = "RETRIEVING_CONTEXT"
    PLANNING = "PLANNING"
    ROUTING = "ROUTING"
    WAITING_FOR_CONFIRMATION = "WAITING_FOR_CONFIRMATION"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    REMEMBERING = "REMEMBERING"
    RESPONDING = "RESPONDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ErrorCategory(str, Enum):
    """Consistent Error Categories for Fault-Tolerant Operations."""
    LLM_OFFLINE = "llm_offline"
    VOICE_FAILURE = "voice_failure"
    SKILL_MISSING = "skill_missing"
    PLUGIN_FAILURE = "plugin_failure"
    SCHEDULE_FAILURE = "schedule_failure"
    WEBSOCKET_DISCONNECT = "websocket_disconnect"
    MEMORY_FAILURE = "memory_failure"
    TIMEOUT = "timeout"
    SECURITY_DENIED = "security_denied"
    UNKNOWN = "unknown"


@dataclass
class JarvisError:
    """Consistent error model for graceful failures."""
    category: ErrorCategory
    message: str
    action: Optional[str] = None
    recoverable: bool = True
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category.value,
            "message": self.message,
            "action": self.action,
            "recoverable": self.recoverable,
            "details": self.details,
            "timestamp": self.timestamp
        }


@dataclass
class UserInput:
    """Unified user input object entering JARVIS Core."""
    content: str
    channel: InputChannel = InputChannel.TEXT
    session_id: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)


@dataclass
class Intent:
    """Classified intent produced by IntentRouter."""
    intent_type: IntentType
    skill_name: str
    action: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    raw_input: str = ""


class SkillCategory(str, Enum):
    """Categorization of skills for discovery and HUD presentation."""
    SYSTEM = "system"
    MEMORY = "memory"
    RESEARCH = "research"
    CODING = "coding"
    FILES = "files"
    AUTOMATION = "automation"
    BROWSER = "browser"
    VOICE = "voice"
    VISION = "vision"
    PRODUCTIVITY = "productivity"
    KNOWLEDGE = "knowledge"
    COMMUNICATION = "communication"
    SCHEDULING = "scheduling"
    UNCATEGORIZED = "uncategorized"


class SkillStatus(str, Enum):
    """Current capability state of a skill in the CapabilityRegistry."""
    REGISTERED = "REGISTERED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    FAILED = "FAILED"


@dataclass
class SkillResult:
    """Standardized output produced by a Skill execution."""
    success: bool
    status: str = "success"
    data: Dict[str, Any] = field(default_factory=dict)
    message: str = ""
    output_text: str = ""
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[JarvisError] = field(default_factory=list)
    execution_time_ms: float = 0.0


@dataclass
class CoreResponse:
    """Unified response returned by JARVIS Core."""
    text: str
    channel: InputChannel
    intent: Optional[Intent] = None
    data: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0
    request_id: str = ""
    state: OperatingState = OperatingState.SUCCESS
    error: Optional[JarvisError] = None
