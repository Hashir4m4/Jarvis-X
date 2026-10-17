"""
JARVIS X — Long-Horizon Autonomous Planning Models
Data models, validation rules, dependency graphs, critical path calculation,
resource estimation, risk assessment, and revision tracking for long-horizon plans.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Union
import copy
import datetime
import re
import time
import uuid


class PlanModelValidationError(ValueError):
    """Raised when long-horizon planning model constraints or invariants are violated."""
    pass


# =====================================================================
# A. PlanStatus & Lifecycle Transitions
# =====================================================================

class PlanStatus(str, Enum):
    """Lifecycle states of a long-horizon strategic plan."""
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


ALLOWED_PLAN_STATUS_TRANSITIONS: Dict[PlanStatus, Set[PlanStatus]] = {
    PlanStatus.DRAFT: {PlanStatus.PROPOSED, PlanStatus.CANCELLED},
    PlanStatus.PROPOSED: {PlanStatus.APPROVED, PlanStatus.REJECTED, PlanStatus.DRAFT, PlanStatus.CANCELLED},
    PlanStatus.APPROVED: {PlanStatus.ACTIVE, PlanStatus.CANCELLED, PlanStatus.PROPOSED},
    PlanStatus.ACTIVE: {PlanStatus.COMPLETED, PlanStatus.CANCELLED, PlanStatus.PROPOSED},
    PlanStatus.COMPLETED: {PlanStatus.ACTIVE},  # Re-opening completed plan if goals reopened
    PlanStatus.REJECTED: {PlanStatus.DRAFT, PlanStatus.PROPOSED, PlanStatus.CANCELLED},
    PlanStatus.CANCELLED: {PlanStatus.DRAFT, PlanStatus.PROPOSED},
}


class MilestoneStatus(str, Enum):
    """Lifecycle states for individual milestones in a plan."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    SKIPPED = "SKIPPED"


# =====================================================================
# B. Milestone
# =====================================================================

@dataclass
class Milestone:
    """
    A major strategic milestone within a long-horizon plan.
    """
    milestone_id: str = field(default_factory=lambda: f"ms_{uuid.uuid4().hex[:8]}")
    title: str = ""
    description: str = ""
    sequence: int = 1
    estimated_duration: float = 1.0  # In days or hours, must be > 0.0
    target_date: Optional[str] = None  # ISO-8601 date string
    success_criteria: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    status: MilestoneStatus = MilestoneStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = MilestoneStatus(self.status)
            except ValueError:
                raise PlanModelValidationError(
                    f"Invalid milestone status: {self.status}. Must be one of {[e.value for e in MilestoneStatus]}."
                )
        self.validate()

    def validate(self):
        """Validates internal constraints of the milestone."""
        if not self.milestone_id or not isinstance(self.milestone_id, str) or not self.milestone_id.strip():
            raise PlanModelValidationError("Milestone milestone_id must be a non-empty string.")
        if not re.match(r"^[a-zA-Z0-9_\-]+$", self.milestone_id):
            raise PlanModelValidationError(
                f"Invalid milestone_id format: '{self.milestone_id}'. Alphanumeric, underscores, hyphens only."
            )
        if not self.title or not isinstance(self.title, str) or not self.title.strip():
            raise PlanModelValidationError("Milestone title must be a non-empty string.")
        if not isinstance(self.description, str):
            raise PlanModelValidationError("Milestone description must be a string.")
        if not isinstance(self.sequence, int) or self.sequence < 0:
            raise PlanModelValidationError(f"Milestone sequence must be a non-negative integer, got {self.sequence}")

        if not isinstance(self.estimated_duration, (int, float)) or self.estimated_duration <= 0.0:
            raise PlanModelValidationError(
                f"Milestone estimated_duration must be a positive number (> 0), got {self.estimated_duration}"
            )

        if self.target_date is not None:
            if not isinstance(self.target_date, str) or not self.target_date.strip():
                raise PlanModelValidationError("Milestone target_date if specified must be a non-empty string.")
            try:
                datetime.datetime.fromisoformat(self.target_date.replace("Z", "+00:00"))
            except ValueError:
                raise PlanModelValidationError(
                    f"Milestone target_date '{self.target_date}' is not a valid ISO-8601 date string."
                )

        if not isinstance(self.success_criteria, list):
            raise PlanModelValidationError("success_criteria must be a list of strings.")
        for crit in self.success_criteria:
            if not isinstance(crit, str) or not crit.strip():
                raise PlanModelValidationError("Each success criterion must be a non-empty string.")

        if not isinstance(self.depends_on, list):
            raise PlanModelValidationError("depends_on must be a list of milestone ID strings.")
        if len(self.depends_on) != len(set(self.depends_on)):
            raise PlanModelValidationError(f"Duplicate dependencies in milestone {self.milestone_id}: {self.depends_on}")
        if self.milestone_id in self.depends_on:
            raise PlanModelValidationError(f"Milestone '{self.milestone_id}' cannot depend on itself.")
        for dep in self.depends_on:
            if not isinstance(dep, str) or not dep.strip():
                raise PlanModelValidationError("Dependency references in depends_on must be non-empty strings.")

        if not isinstance(self.deliverables, list):
            raise PlanModelValidationError("deliverables must be a list of strings.")
        for d in self.deliverables:
            if not isinstance(d, str) or not d.strip():
                raise PlanModelValidationError("Each deliverable must be a non-empty string.")

        if not isinstance(self.required_capabilities, list):
            raise PlanModelValidationError("required_capabilities must be a list of strings.")
        for cap in self.required_capabilities:
            if not isinstance(cap, str) or not cap.strip():
                raise PlanModelValidationError("Each required capability must be a non-empty string.")

        if not isinstance(self.metadata, dict):
            raise PlanModelValidationError("metadata must be a dictionary.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "title": self.title,
            "description": self.description,
            "sequence": self.sequence,
            "estimated_duration": float(self.estimated_duration),
            "target_date": self.target_date,
            "success_criteria": list(self.success_criteria),
            "depends_on": list(self.depends_on),
            "deliverables": list(self.deliverables),
            "required_capabilities": list(self.required_capabilities),
            "status": self.status.value,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Milestone":
        if not isinstance(data, dict):
            raise PlanModelValidationError("Milestone.from_dict requires a dictionary.")
        return cls(
            milestone_id=data.get("milestone_id") or f"ms_{uuid.uuid4().hex[:8]}",
            title=data.get("title", ""),
            description=data.get("description", ""),
            sequence=int(data.get("sequence", 1)),
            estimated_duration=float(data.get("estimated_duration", 1.0)),
            target_date=data.get("target_date"),
            success_criteria=list(data.get("success_criteria", [])),
            depends_on=list(data.get("depends_on", [])),
            deliverables=list(data.get("deliverables", [])),
            required_capabilities=list(data.get("required_capabilities", [])),
            status=data.get("status", MilestoneStatus.PENDING),
            metadata=dict(data.get("metadata", {})),
        )

    @property
    def dependencies(self) -> List[str]:
        return self.depends_on


# =====================================================================
# C. DependencyGraph
# =====================================================================

@dataclass
class DependencyGraph:
    """
    Directed Acyclic Graph (DAG) for milestone dependencies.
    Provides node registration, edge validation, cycle detection,
    topological ordering, and disconnected component detection.
    """
    nodes: Set[str] = field(default_factory=set)
    edges: Dict[str, Set[str]] = field(default_factory=dict)  # node -> set of predecessor dependencies

    def add_node(self, node_id: str) -> None:
        """Registers a node identifier in the graph."""
        if not node_id or not isinstance(node_id, str) or not node_id.strip():
            raise PlanModelValidationError("Node ID must be a non-empty string.")
        self.nodes.add(node_id)
        if node_id not in self.edges:
            self.edges[node_id] = set()

    def add_dependency(self, node_id: str, depends_on_id: str) -> None:
        """
        Adds a directed dependency edge: `node_id` depends on `depends_on_id`.
        """
        if node_id == depends_on_id:
            raise PlanModelValidationError(f"Self-dependency detected: node '{node_id}' cannot depend on itself.")
        self.add_node(node_id)
        self.add_node(depends_on_id)
        self.edges[node_id].add(depends_on_id)
        # Check for cycles immediately
        self.detect_cycles()

    def validate_nodes_exist(self) -> None:
        """Verifies that all dependency targets exist in the graph's registered nodes."""
        for node, deps in self.edges.items():
            for dep in deps:
                if dep not in self.nodes:
                    raise PlanModelValidationError(
                        f"Missing dependency: node '{node}' depends on unregistered node '{dep}'."
                    )

    def detect_cycles(self) -> None:
        """
        Detects if there is any directed cycle in the graph.
        Raises PlanModelValidationError if a cycle is found.
        """
        self.validate_nodes_exist()
        visited: Set[str] = set()
        visiting: Set[str] = set()

        def dfs(curr: str, path: List[str]):
            if curr in visiting:
                cycle_path = " -> ".join(path + [curr])
                raise PlanModelValidationError(f"Circular dependency detected in graph: {cycle_path}")
            if curr in visited:
                return

            visiting.add(curr)
            for dep in self.edges.get(curr, set()):
                dfs(dep, path + [curr])
            visiting.remove(curr)
            visited.add(curr)

        for n in self.nodes:
            if n not in visited:
                dfs(n, [])

    def get_topological_order(self) -> List[str]:
        """
        Returns a topological sort of nodes (dependencies come before dependents).
        Deterministic order using tie-breaking by node ID.
        """
        self.detect_cycles()
        in_degree: Dict[str, int] = {n: 0 for n in self.nodes}
        dependents_map: Dict[str, List[str]] = {n: [] for n in self.nodes}

        for n, deps in self.edges.items():
            in_degree[n] = len(deps)
            for d in deps:
                dependents_map[d].append(n)

        # Start with nodes that have no dependencies (in_degree == 0)
        ready_queue = sorted([n for n, deg in in_degree.items() if deg == 0])
        order: List[str] = []

        while ready_queue:
            curr = ready_queue.pop(0)
            order.append(curr)

            for dependent in sorted(dependents_map[curr]):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    ready_queue.append(dependent)
                    ready_queue.sort()

        if len(order) != len(self.nodes):
            raise PlanModelValidationError("Unable to compute topological ordering: graph contains unresolved cycles.")

        return order

    def get_disconnected_nodes(self) -> Set[str]:
        """
        Finds nodes that have no incoming or outgoing dependencies.
        """
        has_edges: Set[str] = set()
        for node, deps in self.edges.items():
            if deps:
                has_edges.add(node)
                has_edges.update(deps)
        return self.nodes - has_edges

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": sorted(list(self.nodes)),
            "edges": {k: sorted(list(v)) for k, v in sorted(self.edges.items())},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DependencyGraph":
        if not isinstance(data, dict):
            raise PlanModelValidationError("DependencyGraph.from_dict requires a dictionary.")
        graph = cls()
        nodes = data.get("nodes", [])
        for n in nodes:
            graph.add_node(n)
        raw_edges = data.get("edges", {})
        for node, deps in raw_edges.items():
            graph.add_node(node)
            for dep in deps:
                graph.add_dependency(node, dep)
        return graph

    @classmethod
    def from_milestones(cls, milestones: List[Milestone]) -> "DependencyGraph":
        """Builds and validates a DependencyGraph from a list of milestones."""
        graph = cls()
        milestone_ids = {m.milestone_id for m in milestones}
        if len(milestone_ids) != len(milestones):
            raise PlanModelValidationError("Duplicate milestone IDs detected in milestone list.")

        for m in milestones:
            graph.add_node(m.milestone_id)

        for m in milestones:
            for dep in m.depends_on:
                if dep not in milestone_ids:
                    raise PlanModelValidationError(
                        f"Milestone '{m.milestone_id}' depends on missing milestone '{dep}'."
                    )
                graph.add_dependency(m.milestone_id, dep)

        graph.detect_cycles()
        return graph


# =====================================================================
# D. CriticalPath
# =====================================================================

@dataclass
class MilestoneSchedule:
    """Schedule timing for an individual milestone in Critical Path analysis."""
    milestone_id: str
    duration: float
    earliest_start: float
    earliest_finish: float
    latest_start: float
    latest_finish: float
    slack: float
    is_critical: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "milestone_id": self.milestone_id,
            "duration": round(float(self.duration), 4),
            "earliest_start": round(float(self.earliest_start), 4),
            "earliest_finish": round(float(self.earliest_finish), 4),
            "latest_start": round(float(self.latest_start), 4),
            "latest_finish": round(float(self.latest_finish), 4),
            "slack": round(float(self.slack), 4),
            "is_critical": bool(self.is_critical),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MilestoneSchedule":
        return cls(
            milestone_id=data["milestone_id"],
            duration=float(data["duration"]),
            earliest_start=float(data["earliest_start"]),
            earliest_finish=float(data["earliest_finish"]),
            latest_start=float(data["latest_start"]),
            latest_finish=float(data["latest_finish"]),
            slack=float(data["slack"]),
            is_critical=bool(data["is_critical"]),
        )


@dataclass
class CriticalPath:
    """
    Critical Path Method (CPM) calculation result for a plan.
    Provides deterministic earliest/latest timing, slack, and the sequence of critical bottlenecks.
    """
    total_duration: float = 0.0
    critical_milestones: List[str] = field(default_factory=list)
    schedules: Dict[str, MilestoneSchedule] = field(default_factory=dict)

    @classmethod
    def compute(cls, milestones: List[Milestone], graph: DependencyGraph) -> "CriticalPath":
        """
        Computes the Critical Path using standard forward and backward passes.
        """
        if not milestones:
            return cls(total_duration=0.0, critical_milestones=[], schedules={})

        graph.detect_cycles()
        topo_order = graph.get_topological_order()
        milestone_map: Dict[str, Milestone] = {m.milestone_id: m for m in milestones}

        # Successors map
        successors: Dict[str, List[str]] = {m_id: [] for m_id in topo_order}
        for m_id in topo_order:
            for dep in graph.edges.get(m_id, set()):
                if dep in successors:
                    successors[dep].append(m_id)

        # Forward pass (Earliest Start / Earliest Finish)
        es: Dict[str, float] = {}
        ef: Dict[str, float] = {}

        for m_id in topo_order:
            m = milestone_map[m_id]
            dur = m.estimated_duration
            deps = graph.edges.get(m_id, set())
            if not deps:
                es[m_id] = 0.0
            else:
                es[m_id] = max(ef[dep] for dep in deps)
            ef[m_id] = es[m_id] + dur

        total_duration = max(ef.values()) if ef else 0.0

        # Backward pass (Latest Start / Latest Finish)
        ls: Dict[str, float] = {}
        lf: Dict[str, float] = {}

        for m_id in reversed(topo_order):
            m = milestone_map[m_id]
            dur = m.estimated_duration
            succs = successors.get(m_id, [])
            if not succs:
                lf[m_id] = total_duration
            else:
                lf[m_id] = min(ls[succ] for succ in succs)
            ls[m_id] = lf[m_id] - dur

        # Calculate Slack and identify Critical Milestones
        schedules: Dict[str, MilestoneSchedule] = {}
        critical_milestones: List[str] = []

        for m_id in topo_order:
            slack = round(ls[m_id] - es[m_id], 6)
            is_crit = abs(slack) < 1e-6
            sched = MilestoneSchedule(
                milestone_id=m_id,
                duration=milestone_map[m_id].estimated_duration,
                earliest_start=es[m_id],
                earliest_finish=ef[m_id],
                latest_start=ls[m_id],
                latest_finish=lf[m_id],
                slack=max(0.0, slack),
                is_critical=is_crit,
            )
            schedules[m_id] = sched
            if is_crit:
                critical_milestones.append(m_id)

        return cls(
            total_duration=round(total_duration, 4),
            critical_milestones=critical_milestones,
            schedules=schedules,
        )

    @property
    def total_duration_days(self) -> float:
        """Convenience property for total CPM duration in days."""
        return self.total_duration

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_duration": round(float(self.total_duration), 4),
            "critical_milestones": list(self.critical_milestones),
            "schedules": {k: v.to_dict() for k, v in self.schedules.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CriticalPath":
        if not isinstance(data, dict):
            raise PlanModelValidationError("CriticalPath.from_dict requires a dictionary.")
        schedules_raw = data.get("schedules", {})
        schedules = {k: MilestoneSchedule.from_dict(v) for k, v in schedules_raw.items()}
        return cls(
            total_duration=float(data.get("total_duration", 0.0)),
            critical_milestones=list(data.get("critical_milestones", [])),
            schedules=schedules,
        )


# =====================================================================
# E. ResourceEstimate
# =====================================================================

@dataclass
class ResourceEstimate:
    """
    Projected resource envelope and capability requirements.
    All fields are explicitly estimates/projections, not claims of hardware guarantee.
    """
    required_capabilities: List[str] = field(default_factory=list)
    estimated_human_effort_hours: float = 0.0
    estimated_compute_requirements: str = "standard"  # e.g. "low", "standard", "high-memory", "gpu"
    estimated_token_budget: int = 0
    required_human_oversight: str = "periodic"  # "none", "periodic", "mandatory-per-milestone"
    assumptions: List[str] = field(default_factory=list)
    confidence: float = 0.8  # Confidence score 0.0 to 1.0

    def __post_init__(self):
        self.validate()

    def validate(self):
        if not isinstance(self.required_capabilities, list):
            raise PlanModelValidationError("required_capabilities must be a list of strings.")
        if not isinstance(self.estimated_human_effort_hours, (int, float)) or self.estimated_human_effort_hours < 0:
            raise PlanModelValidationError("estimated_human_effort_hours must be a non-negative number.")
        if not isinstance(self.estimated_compute_requirements, str) or not self.estimated_compute_requirements.strip():
            raise PlanModelValidationError("estimated_compute_requirements must be a non-empty string.")
        if not isinstance(self.estimated_token_budget, int) or self.estimated_token_budget < 0:
            raise PlanModelValidationError("estimated_token_budget must be a non-negative integer.")
        if not isinstance(self.required_human_oversight, str) or not self.required_human_oversight.strip():
            raise PlanModelValidationError("required_human_oversight must be a non-empty string.")
        if not isinstance(self.assumptions, list):
            raise PlanModelValidationError("assumptions must be a list of strings.")
        if not isinstance(self.confidence, (int, float)) or not (0.0 <= self.confidence <= 1.0):
            raise PlanModelValidationError(f"confidence must be between 0.0 and 1.0, got {self.confidence}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "required_capabilities": list(self.required_capabilities),
            "estimated_human_effort_hours": round(float(self.estimated_human_effort_hours), 2),
            "estimated_compute_requirements": self.estimated_compute_requirements,
            "estimated_token_budget": self.estimated_token_budget,
            "required_human_oversight": self.required_human_oversight,
            "assumptions": list(self.assumptions),
            "confidence": round(float(self.confidence), 4),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceEstimate":
        if not isinstance(data, dict):
            raise PlanModelValidationError("ResourceEstimate.from_dict requires a dictionary.")
        return cls(
            required_capabilities=list(data.get("required_capabilities", [])),
            estimated_human_effort_hours=float(data.get("estimated_human_effort_hours", 0.0)),
            estimated_compute_requirements=str(data.get("estimated_compute_requirements", "standard")),
            estimated_token_budget=int(data.get("estimated_token_budget", 0)),
            required_human_oversight=str(data.get("required_human_oversight", "periodic")),
            assumptions=list(data.get("assumptions", [])),
            confidence=float(data.get("confidence", 0.8)),
        )


# =====================================================================
# F. RiskAssessment
# =====================================================================

class RiskSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskAssessment:
    """
    Structured risk identification and mitigation entry.
    Probability and impact must be normalized float values between 0.0 and 1.0.
    """
    risk_id: str = field(default_factory=lambda: f"risk_{uuid.uuid4().hex[:8]}")
    description: str = ""
    probability: float = 0.5  # 0.0 to 1.0
    impact: float = 0.5       # 0.0 to 1.0
    severity: RiskSeverity = RiskSeverity.MEDIUM
    mitigation_strategy: str = ""
    trigger_conditions: List[str] = field(default_factory=list)
    residual_risk: str = "LOW"

    def __post_init__(self):
        if isinstance(self.severity, str):
            try:
                self.severity = RiskSeverity(self.severity)
            except ValueError:
                raise PlanModelValidationError(
                    f"Invalid severity: {self.severity}. Must be one of {[e.value for e in RiskSeverity]}."
                )
        self.validate()

    def validate(self):
        if not self.risk_id or not isinstance(self.risk_id, str) or not self.risk_id.strip():
            raise PlanModelValidationError("risk_id must be a non-empty string.")
        if not self.description or not isinstance(self.description, str) or not self.description.strip():
            raise PlanModelValidationError("Risk description must be a non-empty string.")
        if not isinstance(self.probability, (int, float)) or not (0.0 <= self.probability <= 1.0):
            raise PlanModelValidationError(f"Risk probability must be between 0.0 and 1.0, got {self.probability}")
        if not isinstance(self.impact, (int, float)) or not (0.0 <= self.impact <= 1.0):
            raise PlanModelValidationError(f"Risk impact must be between 0.0 and 1.0, got {self.impact}")
        if not isinstance(self.severity, RiskSeverity):
            raise PlanModelValidationError(f"severity must be a RiskSeverity enum, got {type(self.severity)}")
        if not self.mitigation_strategy or not isinstance(self.mitigation_strategy, str) or not self.mitigation_strategy.strip():
            raise PlanModelValidationError("mitigation_strategy must be a non-empty string.")
        if not isinstance(self.trigger_conditions, list):
            raise PlanModelValidationError("trigger_conditions must be a list of strings.")
        if not isinstance(self.residual_risk, str) or not self.residual_risk.strip():
            raise PlanModelValidationError("residual_risk must be a non-empty string.")

    @staticmethod
    def calculate_severity(probability: float, impact: float) -> RiskSeverity:
        """Helper to derive severity from probability and impact score."""
        score = probability * impact
        if score >= 0.7:
            return RiskSeverity.CRITICAL
        elif score >= 0.4:
            return RiskSeverity.HIGH
        elif score >= 0.15:
            return RiskSeverity.MEDIUM
        return RiskSeverity.LOW

    def to_dict(self) -> Dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "description": self.description,
            "probability": round(float(self.probability), 4),
            "impact": round(float(self.impact), 4),
            "severity": self.severity.value,
            "mitigation_strategy": self.mitigation_strategy,
            "trigger_conditions": list(self.trigger_conditions),
            "residual_risk": self.residual_risk,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RiskAssessment":
        if not isinstance(data, dict):
            raise PlanModelValidationError("RiskAssessment.from_dict requires a dictionary.")
        return cls(
            risk_id=data.get("risk_id") or f"risk_{uuid.uuid4().hex[:8]}",
            description=data.get("description", ""),
            probability=float(data.get("probability", 0.5)),
            impact=float(data.get("impact", 0.5)),
            severity=data.get("severity", RiskSeverity.MEDIUM),
            mitigation_strategy=data.get("mitigation_strategy", ""),
            trigger_conditions=list(data.get("trigger_conditions", [])),
            residual_risk=str(data.get("residual_risk", "LOW")),
        )


# =====================================================================
# G. PlanRevision
# =====================================================================

@dataclass
class PlanRevision:
    """
    Immutable historical snapshot of a plan at a specific point in time.
    """
    revision_number: int = 1
    author: str = "JARVIS"
    timestamp: float = field(default_factory=time.time)
    change_reason: str = ""
    previous_revision: Optional[int] = None
    structural_change_summary: str = ""
    snapshot_data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.validate()

    def validate(self):
        if not isinstance(self.revision_number, int) or self.revision_number < 1:
            raise PlanModelValidationError(f"revision_number must be a positive integer >= 1, got {self.revision_number}")
        if not self.author or not isinstance(self.author, str) or not self.author.strip():
            raise PlanModelValidationError("author must be a non-empty string.")
        if not isinstance(self.timestamp, (int, float)) or self.timestamp <= 0:
            raise PlanModelValidationError("timestamp must be a positive number.")
        if not self.change_reason or not isinstance(self.change_reason, str) or not self.change_reason.strip():
            raise PlanModelValidationError("change_reason must be a non-empty string.")
        if self.previous_revision is not None:
            if not isinstance(self.previous_revision, int) or self.previous_revision < 0:
                raise PlanModelValidationError("previous_revision must be a non-negative integer.")
            if self.previous_revision >= self.revision_number:
                raise PlanModelValidationError(
                    f"previous_revision ({self.previous_revision}) must be strictly less than revision_number ({self.revision_number})."
                )
        if not isinstance(self.structural_change_summary, str):
            raise PlanModelValidationError("structural_change_summary must be a string.")
        if not isinstance(self.snapshot_data, dict):
            raise PlanModelValidationError("snapshot_data must be a dictionary.")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "revision_number": self.revision_number,
            "author": self.author,
            "timestamp": self.timestamp,
            "change_reason": self.change_reason,
            "previous_revision": self.previous_revision,
            "structural_change_summary": self.structural_change_summary,
            "snapshot_data": copy.deepcopy(self.snapshot_data),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlanRevision":
        if not isinstance(data, dict):
            raise PlanModelValidationError("PlanRevision.from_dict requires a dictionary.")
        return cls(
            revision_number=int(data.get("revision_number", 1)),
            author=str(data.get("author", "JARVIS")),
            timestamp=float(data.get("timestamp", time.time())),
            change_reason=str(data.get("change_reason", "")),
            previous_revision=data.get("previous_revision"),
            structural_change_summary=str(data.get("structural_change_summary", "")),
            snapshot_data=dict(data.get("snapshot_data", {})),
        )


# =====================================================================
# H. LongHorizonPlan
# =====================================================================

@dataclass
class LongHorizonPlan:
    """
    Comprehensive aggregate model for long-horizon autonomous planning.
    Integrates milestones, dependency DAG, critical path analysis, resource estimates,
    risk profiles, and versioned revision history.
    """
    plan_id: str = field(default_factory=lambda: f"lhplan_{uuid.uuid4().hex[:8]}")
    linked_goal_id: str = ""
    title: str = ""
    description: str = ""
    status: PlanStatus = PlanStatus.DRAFT
    milestones: List[Milestone] = field(default_factory=list)
    dependency_graph: DependencyGraph = field(default_factory=DependencyGraph)
    critical_path: Optional[CriticalPath] = None
    resource_estimates: ResourceEstimate = field(default_factory=ResourceEstimate)
    risk_assessments: List[RiskAssessment] = field(default_factory=list)
    revisions: List[PlanRevision] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.status, str):
            try:
                self.status = PlanStatus(self.status)
            except ValueError:
                raise PlanModelValidationError(
                    f"Invalid plan status: {self.status}. Must be one of {[e.value for e in PlanStatus]}."
                )

        # Normalize milestones
        norm_ms: List[Milestone] = []
        for m in self.milestones:
            if isinstance(m, dict):
                norm_ms.append(Milestone.from_dict(m))
            elif isinstance(m, Milestone):
                norm_ms.append(m)
            else:
                raise PlanModelValidationError(f"Invalid milestone object: {m}")
        self.milestones = norm_ms

        # Normalize resource estimate
        if isinstance(self.resource_estimates, dict):
            self.resource_estimates = ResourceEstimate.from_dict(self.resource_estimates)
        elif not isinstance(self.resource_estimates, ResourceEstimate):
            raise PlanModelValidationError(f"Invalid resource estimate object: {self.resource_estimates}")

        # Normalize risks
        norm_risks: List[RiskAssessment] = []
        for r in self.risk_assessments:
            if isinstance(r, dict):
                norm_risks.append(RiskAssessment.from_dict(r))
            elif isinstance(r, RiskAssessment):
                norm_risks.append(r)
            else:
                raise PlanModelValidationError(f"Invalid risk object: {r}")
        self.risk_assessments = norm_risks

        # Normalize revisions
        norm_revs: List[PlanRevision] = []
        for rev in self.revisions:
            if isinstance(rev, dict):
                norm_revs.append(PlanRevision.from_dict(rev))
            elif isinstance(rev, PlanRevision):
                norm_revs.append(rev)
            else:
                raise PlanModelValidationError(f"Invalid revision object: {rev}")
        self.revisions = norm_revs

        # Sync and recalculate graph & critical path if not provided
        self.sync_graph_and_critical_path()
        self.validate()

    def sync_graph_and_critical_path(self) -> None:
        """
        Synchronizes dependency graph and recalculates the critical path
        based on current milestones.
        """
        if self.milestones:
            self.dependency_graph = DependencyGraph.from_milestones(self.milestones)
            self.critical_path = CriticalPath.compute(self.milestones, self.dependency_graph)
        else:
            self.dependency_graph = DependencyGraph()
            self.critical_path = CriticalPath()

    def validate(self):
        """Validates internal invariants of the entire LongHorizonPlan aggregate."""
        if not self.plan_id or not isinstance(self.plan_id, str) or not self.plan_id.strip():
            raise PlanModelValidationError("plan_id must be a non-empty string.")
        if not re.match(r"^[a-zA-Z0-9_\-]+$", self.plan_id):
            raise PlanModelValidationError(
                f"Invalid plan_id format: '{self.plan_id}'. Alphanumeric, underscores, hyphens only."
            )
        if not self.linked_goal_id or not isinstance(self.linked_goal_id, str) or not self.linked_goal_id.strip():
            raise PlanModelValidationError("linked_goal_id must be a non-empty string referencing a Goal.")
        if not self.title or not isinstance(self.title, str) or not self.title.strip():
            raise PlanModelValidationError("Plan title must be a non-empty string.")
        if not isinstance(self.description, str):
            raise PlanModelValidationError("Plan description must be a string.")
        if not isinstance(self.status, PlanStatus):
            raise PlanModelValidationError(f"status must be a PlanStatus enum, got: {type(self.status)}")

        # Timestamps
        if self.created_at <= 0 or self.updated_at <= 0:
            raise PlanModelValidationError("Timestamps created_at and updated_at must be positive numbers.")
        if self.updated_at < self.created_at:
            raise PlanModelValidationError("updated_at cannot be prior to created_at.")

        # Milestones uniqueness
        m_ids = [m.milestone_id for m in self.milestones]
        if len(m_ids) != len(set(m_ids)):
            raise PlanModelValidationError(f"Duplicate milestone IDs in plan {self.plan_id}: {m_ids}")

        for m in self.milestones:
            m.validate()

        # Graph validation
        self.dependency_graph.detect_cycles()

        # Risk validation
        for r in self.risk_assessments:
            r.validate()

        # Resource estimate validation
        self.resource_estimates.validate()

        # Revision history validation
        seen_rev_nums: Set[int] = set()
        prev_num = 0
        for rev in self.revisions:
            rev.validate()
            if rev.revision_number in seen_rev_nums:
                raise PlanModelValidationError(f"Duplicate revision number detected: {rev.revision_number}")
            if rev.revision_number <= prev_num:
                raise PlanModelValidationError(
                    f"Revisions must be ordered monotonically: got {rev.revision_number} after {prev_num}"
                )
            seen_rev_nums.add(rev.revision_number)
            prev_num = rev.revision_number

    def can_transition_to(self, target_status: PlanStatus) -> bool:
        """Determines if the plan can transition to target_status."""
        if self.status == target_status:
            return True
        allowed = ALLOWED_PLAN_STATUS_TRANSITIONS.get(self.status, set())
        return target_status in allowed

    def transition_to(self, new_status: Union[PlanStatus, str], force: bool = False) -> None:
        """
        Transitions the plan to a new status.
        Raises PlanModelValidationError if the transition is prohibited.
        """
        if isinstance(new_status, str):
            try:
                new_status = PlanStatus(new_status)
            except ValueError:
                raise PlanModelValidationError(f"Unknown plan status: {new_status}")

        if self.status == new_status:
            return

        # Direct transition from DRAFT to ACTIVE is strictly forbidden (must be approved first)
        if self.status == PlanStatus.DRAFT and new_status == PlanStatus.ACTIVE:
            raise PlanModelValidationError("Illegal transition: DRAFT plan cannot transition directly to ACTIVE without approval.")

        # Direct transition from PROPOSED to ACTIVE is strictly forbidden (must be approved first)
        if self.status == PlanStatus.PROPOSED and new_status == PlanStatus.ACTIVE:
            raise PlanModelValidationError("Illegal transition: PROPOSED plan must be APPROVED before becoming ACTIVE.")

        if not force and not self.can_transition_to(new_status):
            raise PlanModelValidationError(
                f"Prohibited plan status transition: cannot transition from {self.status.value} to {new_status.value}."
            )

        self.status = new_status
        self.updated_at = time.time()

    def create_revision_snapshot(self, author: str, change_reason: str, structural_change_summary: str = "") -> PlanRevision:
        """
        Creates and appends an immutable PlanRevision capturing the current state before modifications.
        """
        next_rev = (self.revisions[-1].revision_number + 1) if self.revisions else 1
        prev_rev = self.revisions[-1].revision_number if self.revisions else None

        snapshot = self.to_dict()
        # Do not recursively nest revisions in the snapshot to keep snapshots bounded
        snapshot.pop("revisions", None)

        revision = PlanRevision(
            revision_number=next_rev,
            author=author,
            timestamp=time.time(),
            change_reason=change_reason,
            previous_revision=prev_rev,
            structural_change_summary=structural_change_summary,
            snapshot_data=snapshot,
        )
        self.revisions.append(revision)
        self.updated_at = time.time()
        return revision

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the entire plan aggregate to a JSON-compatible dictionary."""
        return {
            "plan_id": self.plan_id,
            "linked_goal_id": self.linked_goal_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "milestones": [m.to_dict() for m in self.milestones],
            "dependency_graph": self.dependency_graph.to_dict(),
            "critical_path": self.critical_path.to_dict() if self.critical_path else None,
            "resource_estimates": self.resource_estimates.to_dict(),
            "risk_assessments": [r.to_dict() for r in self.risk_assessments],
            "revisions": [rev.to_dict() for rev in self.revisions],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LongHorizonPlan":
        """Deserializes a LongHorizonPlan from a dictionary."""
        if not isinstance(data, dict):
            raise PlanModelValidationError("LongHorizonPlan.from_dict requires a dictionary.")

        raw_milestones = data.get("milestones", [])
        milestones = [Milestone.from_dict(m) if isinstance(m, dict) else m for m in raw_milestones]

        raw_graph = data.get("dependency_graph")
        graph = DependencyGraph.from_dict(raw_graph) if isinstance(raw_graph, dict) else None

        raw_cpm = data.get("critical_path")
        cpm = CriticalPath.from_dict(raw_cpm) if isinstance(raw_cpm, dict) else None

        raw_res = data.get("resource_estimates", {})
        res = ResourceEstimate.from_dict(raw_res) if isinstance(raw_res, dict) else ResourceEstimate()

        raw_risks = data.get("risk_assessments", [])
        risks = [RiskAssessment.from_dict(r) if isinstance(r, dict) else r for r in raw_risks]

        raw_revs = data.get("revisions", [])
        revs = [PlanRevision.from_dict(rev) if isinstance(rev, dict) else rev for rev in raw_revs]

        plan = cls(
            plan_id=data.get("plan_id") or f"lhplan_{uuid.uuid4().hex[:8]}",
            linked_goal_id=data.get("linked_goal_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", PlanStatus.DRAFT),
            milestones=milestones,
            dependency_graph=graph or DependencyGraph(),
            critical_path=cpm,
            resource_estimates=res,
            risk_assessments=risks,
            revisions=revs,
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            metadata=dict(data.get("metadata", {})),
        )
        return plan
