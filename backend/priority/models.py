"""
JARVIS X — Advanced Intelligent Priority Management Subsystem
Domain models, explainable scoring criteria, recommendations, and user override records.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class PriorityLevel(str, Enum):
    P0_CRITICAL = "P0_CRITICAL"
    P1_HIGH = "P1_HIGH"
    P2_MEDIUM = "P2_MEDIUM"
    P3_LOW = "P3_LOW"
    P4_DEFERRED = "P4_DEFERRED"


class ItemType(str, Enum):
    GOAL = "GOAL"
    MILESTONE = "MILESTONE"
    TASK = "TASK"
    WORKFLOW = "WORKFLOW"


@dataclass
class PriorityScoreExplanation:
    """
    Transparent, explainable breakdown of the composite priority calculation.
    """
    item_id: str
    item_type: ItemType
    composite_score: float  # 0.0 to 100.0
    urgency_component: float  # Deadline proximity & pressure
    impact_component: float   # Goal alignment & business importance
    dependency_component: float  # Critical path / blocking factor
    risk_component: float     # Downside impact if delayed
    effort_component: float   # Execution complexity / duration
    user_override_delta: float = 0.0
    reasoning: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type.value,
            "composite_score": round(self.composite_score, 2),
            "urgency_component": round(self.urgency_component, 2),
            "impact_component": round(self.impact_component, 2),
            "dependency_component": round(self.dependency_component, 2),
            "risk_component": round(self.risk_component, 2),
            "effort_component": round(self.effort_component, 2),
            "user_override_delta": round(self.user_override_delta, 2),
            "reasoning": list(self.reasoning),
        }


@dataclass
class PriorityOverride:
    """Explicit human override fixing priority level and reason."""
    item_id: str
    item_type: ItemType
    assigned_level: PriorityLevel
    override_reason: str
    author: str = "User"
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_type": self.item_type.value,
            "assigned_level": self.assigned_level.value,
            "override_reason": self.override_reason,
            "author": self.author,
            "created_at": self.created_at,
        }


@dataclass
class PriorityRecommendation:
    """Actionable recommendation produced by the Priority Intelligence Subsystem."""
    recommendation_id: str = field(default_factory=lambda: f"rec_{uuid.uuid4().hex[:8]}")
    item_id: str = ""
    item_type: ItemType = ItemType.TASK
    title: str = ""
    recommended_level: PriorityLevel = PriorityLevel.P2_MEDIUM
    score_explanation: Optional[PriorityScoreExplanation] = None
    suggested_action: str = ""
    is_blocked: bool = False
    is_overdue: bool = False
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "item_id": self.item_id,
            "item_type": self.item_type.value,
            "title": self.title,
            "recommended_level": self.recommended_level.value,
            "score_explanation": self.score_explanation.to_dict() if self.score_explanation else None,
            "suggested_action": self.suggested_action,
            "is_blocked": self.is_blocked,
            "is_overdue": self.is_overdue,
            "generated_at": self.generated_at,
        }
