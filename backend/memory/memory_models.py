from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List


class MemoryCategory(str, Enum):
    SHORT_TERM = "short_term"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    TASK = "task"
    PROJECT = "project"


class MemoryImportance(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PrivacyLevel(str, Enum):
    LOCAL_ONLY = "local_only"
    PREFER_LOCAL = "prefer_local"
    CLOUD_ALLOWED = "cloud_allowed"


class MemoryConfidence(str, Enum):
    USER_EXPLICIT = "user_explicit"
    REPEATED_CONTEXT = "repeated_context"
    MODEL_INFERRED = "model_inferred"
    EXTERNAL_SOURCE = "external_source"


@dataclass
class MemoryDecision:
    """Represents the orchestrator's decision on how to persist information."""
    should_save: bool
    category: MemoryCategory = MemoryCategory.SHORT_TERM
    importance: MemoryImportance = MemoryImportance.LOW
    expiry_seconds: Optional[int] = None
    project_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    privacy_level: PrivacyLevel = PrivacyLevel.PREFER_LOCAL
    confidence: MemoryConfidence = MemoryConfidence.MODEL_INFERRED

    @classmethod
    def discard(cls) -> "MemoryDecision":
        return cls(should_save=False)
