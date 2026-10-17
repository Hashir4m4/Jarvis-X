"""
JARVIS X — Personal Project Intelligence Subsystem
Domain models, project status, architectural context, blockers, and decisions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class ProjectStatus(str, Enum):
    ACTIVE = "ACTIVE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


@dataclass
class ProjectDecisionRecord:
    """Historical decision made regarding project architecture, scope, or technology."""
    decision_id: str = field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:8]}")
    title: str = ""
    rationale: str = ""
    decided_by: str = "User"
    timestamp: float = field(default_factory=time.time)
    related_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "title": self.title,
            "rationale": self.rationale,
            "decided_by": self.decided_by,
            "timestamp": self.timestamp,
            "related_files": list(self.related_files),
        }


@dataclass
class ProjectBlocker:
    """Active blocker or dependency impediment identified for a project."""
    blocker_id: str = field(default_factory=lambda: f"blk_{uuid.uuid4().hex[:8]}")
    description: str = ""
    severity: str = "HIGH"  # LOW, MEDIUM, HIGH, CRITICAL
    identified_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolved_at: Optional[float] = None
    resolution_notes: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blocker_id": self.blocker_id,
            "description": self.description,
            "severity": self.severity,
            "identified_at": self.identified_at,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at,
            "resolution_notes": self.resolution_notes,
        }


@dataclass
class PersonalProject:
    """Comprehensive aggregate model representing a personal engineering or research project."""
    project_id: str = field(default_factory=lambda: f"proj_{uuid.uuid4().hex[:8]}")
    name: str = ""
    description: str = ""
    repository_path: Optional[str] = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    linked_goal_ids: List[str] = field(default_factory=list)
    linked_plan_ids: List[str] = field(default_factory=list)
    active_blockers: List[ProjectBlocker] = field(default_factory=list)
    decisions: List[ProjectDecisionRecord] = field(default_factory=list)
    knowledge_references: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "repository_path": self.repository_path,
            "status": self.status.value,
            "linked_goal_ids": list(self.linked_goal_ids),
            "linked_plan_ids": list(self.linked_plan_ids),
            "active_blockers": [b.to_dict() for b in self.active_blockers],
            "decisions": [d.to_dict() for d in self.decisions],
            "knowledge_references": list(self.knowledge_references),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalProject":
        status_val = data.get("status", ProjectStatus.ACTIVE.value)
        try:
            status = ProjectStatus(status_val)
        except ValueError:
            status = ProjectStatus.ACTIVE
        blockers = [ProjectBlocker(**b) for b in data.get("active_blockers", [])]
        decisions = [ProjectDecisionRecord(**d) for d in data.get("decisions", [])]
        return cls(
            project_id=data.get("project_id", f"proj_{uuid.uuid4().hex[:8]}"),
            name=data.get("name", ""),
            description=data.get("description", ""),
            repository_path=data.get("repository_path"),
            status=status,
            linked_goal_ids=list(data.get("linked_goal_ids", [])),
            linked_plan_ids=list(data.get("linked_plan_ids", [])),
            active_blockers=blockers,
            decisions=decisions,
            knowledge_references=list(data.get("knowledge_references", [])),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            metadata=dict(data.get("metadata", {})),
        )
