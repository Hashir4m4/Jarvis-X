from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid

class LearningStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"

@dataclass
class LearningOutcome:
    """A raw observed outcome of a task or explicit feedback."""
    outcome_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: Optional[str] = None
    category: str = "unknown"
    status: str = "unknown" # e.g. "COMPLETED", "FAILED", "FEEDBACK"
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_category: Optional[str] = None
    user_feedback: Optional[str] = None
    source: str = "system" # e.g. "system", "user_explicit"
    timestamp: float = field(default_factory=time.time)

@dataclass
class LearningRecord:
    """A learning record, which starts as a candidate and can be promoted to validated."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    pattern: str = "" # e.g. "tool_always_fails", "user_prefers_concise"
    context: Dict[str, Any] = field(default_factory=dict)
    status: LearningStatus = LearningStatus.CANDIDATE
    confidence: float = 0.0 # 0.0 to 1.0
    evidence_count: int = 0
    provenance: List[str] = field(default_factory=list) # List of outcome_ids
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    inferred: bool = True


class ImprovementCategory(str, Enum):
    WORKFLOW_RELIABILITY = "WORKFLOW_RELIABILITY"
    PLANNING_ACCURACY = "PLANNING_ACCURACY"
    CODE_QUALITY = "CODE_QUALITY"
    RESOURCE_EFFICIENCY = "RESOURCE_EFFICIENCY"
    USER_EXPERIENCE = "USER_EXPERIENCE"


@dataclass
class ImprovementRecommendation:
    """Actionable improvement recommendation generated from observed telemetry and outcomes."""
    recommendation_id: str = field(default_factory=lambda: f"imp_{uuid.uuid4().hex[:8]}")
    category: ImprovementCategory = ImprovementCategory.WORKFLOW_RELIABILITY
    title: str = ""
    description: str = ""
    expected_benefit: str = ""
    risk_level: str = "LOW"
    confidence: float = 0.8
    evidence: List[str] = field(default_factory=list)
    requires_approval: bool = True
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "category": self.category.value,
            "title": self.title,
            "description": self.description,
            "expected_benefit": self.expected_benefit,
            "risk_level": self.risk_level,
            "confidence": round(self.confidence, 2),
            "evidence": list(self.evidence),
            "requires_approval": self.requires_approval,
            "created_at": self.created_at,
        }
