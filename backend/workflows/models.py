"""
JARVIS X — Autonomous Workflow Execution Subsystem
Domain models, execution states, policies, and audit records.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class WorkflowStatus(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class WorkflowStepStatus(str, Enum):
    PENDING = "PENDING"
    BLOCKED = "BLOCKED"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    CANCELLED = "CANCELLED"


class ExecutionRiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class WorkflowDependency:
    """Represents a prerequisite step dependency with condition evaluation."""
    prerequisite_step_id: str
    condition: str = "COMPLETED"  # COMPLETED, SUCCEEDED, ANY


@dataclass
class ExecutionPolicy:
    """Configures retry limits, backoff, timeouts, and manual confirmation for a step."""
    max_retries: int = 2
    timeout_seconds: float = 30.0
    backoff_multiplier: float = 1.5
    requires_approval: bool = False
    idempotency_key: Optional[str] = None
    risk_level: ExecutionRiskLevel = ExecutionRiskLevel.LOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_retries": self.max_retries,
            "timeout_seconds": self.timeout_seconds,
            "backoff_multiplier": self.backoff_multiplier,
            "requires_approval": self.requires_approval,
            "idempotency_key": self.idempotency_key,
            "risk_level": self.risk_level.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionPolicy":
        if not data:
            return cls()
        risk_str = data.get("risk_level", ExecutionRiskLevel.LOW.value)
        try:
            risk = ExecutionRiskLevel(risk_str)
        except ValueError:
            risk = ExecutionRiskLevel.LOW
        return cls(
            max_retries=int(data.get("max_retries", 2)),
            timeout_seconds=float(data.get("timeout_seconds", 30.0)),
            backoff_multiplier=float(data.get("backoff_multiplier", 1.5)),
            requires_approval=bool(data.get("requires_approval", False)),
            idempotency_key=data.get("idempotency_key"),
            risk_level=risk,
        )


@dataclass
class ExecutionAuditRecord:
    """Immutable audit record captured for each execution attempt of a step."""
    record_id: str = field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:8]}")
    workflow_id: str = ""
    step_id: str = ""
    attempt: int = 1
    actor: str = "system"
    action: str = ""
    skill_name: str = ""
    status: str = ""
    input_snapshot: Dict[str, Any] = field(default_factory=dict)
    output_snapshot: Optional[Any] = None
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "workflow_id": self.workflow_id,
            "step_id": self.step_id,
            "attempt": self.attempt,
            "actor": self.actor,
            "action": self.action,
            "skill_name": self.skill_name,
            "status": self.status,
            "input_snapshot": self.input_snapshot,
            "output_snapshot": self.output_snapshot,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionAuditRecord":
        return cls(
            record_id=data.get("record_id", f"audit_{uuid.uuid4().hex[:8]}"),
            workflow_id=data.get("workflow_id", ""),
            step_id=data.get("step_id", ""),
            attempt=int(data.get("attempt", 1)),
            actor=data.get("actor", "system"),
            action=data.get("action", ""),
            skill_name=data.get("skill_name", ""),
            status=data.get("status", ""),
            input_snapshot=data.get("input_snapshot", {}),
            output_snapshot=data.get("output_snapshot"),
            error=data.get("error"),
            started_at=float(data.get("started_at", time.time())),
            finished_at=data.get("finished_at"),
            duration_ms=float(data.get("duration_ms", 0.0)),
        )


@dataclass
class WorkflowStep:
    """Atomic step within an executable workflow bound to an authorized skill action."""
    step_id: str
    title: str
    skill_name: str
    action: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    attempt_count: int = 0
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    execution_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "skill_name": self.skill_name,
            "action": self.action,
            "parameters": self.parameters,
            "dependencies": self.dependencies,
            "policy": self.policy.to_dict(),
            "status": self.status.value,
            "attempt_count": self.attempt_count,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "execution_time_ms": self.execution_time_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStep":
        status_val = data.get("status", WorkflowStepStatus.PENDING.value)
        try:
            status = WorkflowStepStatus(status_val)
        except ValueError:
            status = WorkflowStepStatus.PENDING
        return cls(
            step_id=data["step_id"],
            title=data.get("title", ""),
            skill_name=data.get("skill_name", ""),
            action=data.get("action", ""),
            parameters=data.get("parameters", {}),
            dependencies=data.get("dependencies", []),
            policy=ExecutionPolicy.from_dict(data.get("policy", {})),
            status=status,
            attempt_count=int(data.get("attempt_count", 0)),
            result=data.get("result"),
            error=data.get("error"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            execution_time_ms=float(data.get("execution_time_ms", 0.0)),
        )


@dataclass
class Workflow:
    """Definition of an orchestrated workflow derived from an approved plan or explicit definition."""
    workflow_id: str = field(default_factory=lambda: f"wf_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    origin_plan_id: Optional[str] = None
    origin_goal_id: Optional[str] = None
    steps: List[WorkflowStep] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.DRAFT
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    approved_by: Optional[str] = None
    approved_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "title": self.title,
            "description": self.description,
            "origin_plan_id": self.origin_plan_id,
            "origin_goal_id": self.origin_goal_id,
            "steps": [s.to_dict() for s in self.steps],
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Workflow":
        status_val = data.get("status", WorkflowStatus.DRAFT.value)
        try:
            status = WorkflowStatus(status_val)
        except ValueError:
            status = WorkflowStatus.DRAFT
        steps = [WorkflowStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            workflow_id=data.get("workflow_id", f"wf_{uuid.uuid4().hex[:8]}"),
            title=data.get("title", ""),
            description=data.get("description", ""),
            origin_plan_id=data.get("origin_plan_id"),
            origin_goal_id=data.get("origin_goal_id"),
            steps=steps,
            status=status,
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            approved_by=data.get("approved_by"),
            approved_at=data.get("approved_at"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class WorkflowExecution:
    """Execution state tracking an authorized workflow run."""
    execution_id: str = field(default_factory=lambda: f"exec_{uuid.uuid4().hex[:8]}")
    workflow_id: str = ""
    status: WorkflowStatus = WorkflowStatus.PENDING_APPROVAL
    authorized_by: Optional[str] = None
    authorized_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    cancelled_at: Optional[float] = None
    step_results: Dict[str, Any] = field(default_factory=dict)
    audit_trail: List[ExecutionAuditRecord] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "authorized_by": self.authorized_by,
            "authorized_at": self.authorized_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "cancelled_at": self.cancelled_at,
            "step_results": self.step_results,
            "audit_trail": [a.to_dict() for a in self.audit_trail],
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowExecution":
        status_val = data.get("status", WorkflowStatus.PENDING_APPROVAL.value)
        try:
            status = WorkflowStatus(status_val)
        except ValueError:
            status = WorkflowStatus.PENDING_APPROVAL
        audit_records = [ExecutionAuditRecord.from_dict(a) for a in data.get("audit_trail", [])]
        return cls(
            execution_id=data.get("execution_id", f"exec_{uuid.uuid4().hex[:8]}"),
            workflow_id=data.get("workflow_id", ""),
            status=status,
            authorized_by=data.get("authorized_by"),
            authorized_at=data.get("authorized_at"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            cancelled_at=data.get("cancelled_at"),
            step_results=data.get("step_results", {}),
            audit_trail=audit_records,
            error=data.get("error"),
        )
