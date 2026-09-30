import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


class PlanStatus(str, enum.Enum):
    """Lifecycle states of an autonomous task plan."""
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"


class AutonomyLevel(int, enum.Enum):
    """Autonomy level controlling execution behavior."""
    MANUAL = 0               # Every action requires approval
    ASSISTED = 1             # Safe actions auto-execute, risky require approval
    CONTROLLED_AUTONOMY = 2  # Safe and previously approved execute automatically
    RESTRICTED_AUTONOMY = 3  # Configured task classes run autonomously


class StepStatus(str, enum.Enum):
    """Lifecycle states of an individual plan step."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class RiskLevel(str, enum.Enum):
    """Risk classification for safety governance."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RetryPolicy(str, enum.Enum):
    """Retry policy for transient or failing steps."""
    NO_RETRY = "NO_RETRY"
    LIMITED_RETRY = "LIMITED_RETRY"
    ALTERNATIVE_CAPABILITY = "ALTERNATIVE_CAPABILITY"


class ApprovalMode(str, enum.Enum):
    """Approval governance modes."""
    AUTO_EXECUTE_SAFE = "AUTO_EXECUTE_SAFE"
    REQUIRE_PLAN_APPROVAL = "REQUIRE_PLAN_APPROVAL"
    REQUIRE_RISKY_STEP_APPROVAL = "REQUIRE_RISKY_STEP_APPROVAL"


@dataclass
class TaskStep:
    """Individual atomic execution unit within a plan."""
    step_id: str
    description: str
    action_type: str = "custom"
    required_capability: Optional[str] = None
    required_agent: Optional[str] = None
    required_skill: Optional[str] = None
    required_tool: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    input_data: Dict[str, Any] = field(default_factory=dict)
    expected_output: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    requires_confirmation: bool = False
    status: StepStatus = StepStatus.PENDING
    retry_policy: RetryPolicy = RetryPolicy.NO_RETRY
    max_retries: int = 2
    retry_count: int = 0
    fallback_capability: Optional[str] = None
    output_data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "description": self.description,
            "action_type": self.action_type,
            "required_capability": self.required_capability,
            "required_agent": self.required_agent,
            "required_skill": self.required_skill,
            "required_tool": self.required_tool,
            "dependencies": self.dependencies,
            "input_data": self.input_data,
            "expected_output": self.expected_output,
            "risk_level": self.risk_level.value,
            "requires_confirmation": self.requires_confirmation,
            "status": self.status.value,
            "retry_policy": self.retry_policy.value,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "fallback_capability": self.fallback_capability,
            "output_data": self.output_data,
            "error": self.error,
            "execution_time": self.execution_time
        }


@dataclass
class TaskProgress:
    """Live progress telemetry for the HUD and User visibility."""
    plan_id: str
    goal: str
    current_step_id: Optional[str] = None
    completed_steps: int = 0
    total_steps: int = 0
    percentage: float = 0.0
    status_message: str = ""

    def to_hud_payload(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "current_step": self.current_step_id,
            "completed": self.completed_steps,
            "total": self.total_steps,
            "progress_pct": round(self.percentage, 1),
            "status": self.status_message,
            "timestamp": time.time()
        }


@dataclass
class TaskPlan:
    """Structured execution plan generated from user objective."""
    plan_id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    goal: str = ""
    status: PlanStatus = PlanStatus.CREATED
    approval_mode: ApprovalMode = ApprovalMode.REQUIRE_RISKY_STEP_APPROVAL
    autonomy_level: AutonomyLevel = AutonomyLevel.ASSISTED
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    steps: List[TaskStep] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    estimated_complexity: str = "MODERATE"
    risk_summary: str = "LOW"
    required_permissions: List[str] = field(default_factory=list)
    current_step_index: int = 0
    checkpoint_state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_step(self, step_id: str) -> Optional[TaskStep]:
        for s in self.steps:
            if s.step_id == step_id:
                return s
        return None

    def get_progress(self) -> TaskProgress:
        completed = sum(1 for s in self.steps if s.status == StepStatus.COMPLETED)
        total = len(self.steps)
        pct = (completed / total * 100.0) if total > 0 else 0.0
        current = None
        for s in self.steps:
            if s.status == StepStatus.RUNNING:
                current = s.step_id
                break
        return TaskProgress(
            plan_id=self.plan_id,
            goal=self.goal,
            current_step_id=current,
            completed_steps=completed,
            total_steps=total,
            percentage=pct,
            status_message=f"Plan status: {self.status.value} ({completed}/{total} steps)"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "goal": self.goal,
            "status": self.status.value,
            "approval_mode": self.approval_mode.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "steps": [s.to_dict() for s in self.steps],
            "dependencies": self.dependencies,
            "estimated_complexity": self.estimated_complexity,
            "risk_summary": self.risk_summary,
            "required_permissions": self.required_permissions,
            "current_step_index": self.current_step_index,
            "metadata": self.metadata
        }
