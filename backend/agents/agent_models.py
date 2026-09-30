import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


class AgentStatus(str, enum.Enum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    UNAVAILABLE = "UNAVAILABLE"


class OfflineSupport(str, enum.Enum):
    FULL = "FULL"
    LIMITED = "LIMITED"
    NONE = "NONE"


class AgentCapability(str, enum.Enum):
    WEB_RESEARCH = "WEB_RESEARCH"
    SOURCE_ANALYSIS = "SOURCE_ANALYSIS"
    CODE_GENERATION = "CODE_GENERATION"
    CODE_ANALYSIS = "CODE_ANALYSIS"
    DEBUGGING = "DEBUGGING"
    TASK_DECOMPOSITION = "TASK_DECOMPOSITION"
    PROJECT_PLANNING = "PROJECT_PLANNING"
    TECHNICAL_ANALYSIS = "TECHNICAL_ANALYSIS"
    COMPARISON = "COMPARISON"
    SYSTEM_DIAGNOSTICS = "SYSTEM_DIAGNOSTICS"
    PRODUCTIVITY_PLANNING = "PRODUCTIVITY_PLANNING"


@dataclass
class AgentMetadata:
    """Metadata describing a specialized agent registered in the system."""
    agent_id: str
    name: str
    description: str
    specialization: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    allowed_skills: List[str] = field(default_factory=list)
    model_role: str = "general"
    offline_support: OfflineSupport = OfflineSupport.FULL
    status: AgentStatus = AgentStatus.IDLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "description": self.description,
            "specialization": self.specialization,
            "capabilities": [c.value if hasattr(c, "value") else str(c) for c in self.capabilities],
            "allowed_tools": self.allowed_tools,
            "allowed_skills": self.allowed_skills,
            "model_role": self.model_role,
            "offline_support": self.offline_support.value if hasattr(self.offline_support, "value") else str(self.offline_support),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status)
        }


@dataclass
class AgentTaskContext:
    """Structured, bounded context passed to an agent for task execution."""
    task_id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    user_goal: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    relevant_context: Optional[str] = None
    privacy_policy: str = "PREFER_LOCAL"
    timeout_seconds: float = 30.0
    delegation_depth: int = 1
    max_depth: int = 2
    parent_task_id: Optional[str] = None
    internet_available: bool = True
    local_llm_available: bool = True

    def can_delegate_further(self) -> bool:
        """Enforces delegation depth limits to prevent runaway recursion."""
        return self.delegation_depth < self.max_depth


@dataclass
class AgentResult:
    """Standardized output produced by a specialized agent."""
    success: bool
    agent_id: str
    task_id: str
    status: AgentStatus = AgentStatus.COMPLETED
    summary: str = ""
    findings: List[str] = field(default_factory=list)
    artifacts: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    errors: List[str] = field(default_factory=list)
    execution_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "agent_id": self.agent_id,
            "task_id": self.task_id,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "summary": self.summary,
            "findings": self.findings,
            "artifacts": self.artifacts,
            "confidence": self.confidence,
            "errors": self.errors,
            "execution_time": self.execution_time
        }
