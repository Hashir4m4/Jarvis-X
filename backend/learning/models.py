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
