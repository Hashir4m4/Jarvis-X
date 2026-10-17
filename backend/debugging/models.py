"""
JARVIS X — Intelligent Debugging Subsystem
Domain models for error collection, diagnostic hypotheses, stack trace correlation, and proposed fixes.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class DiagnosticConfidence(str, Enum):
    CONFIRMED = "CONFIRMED"
    PROBABLE = "PROBABLE"
    POSSIBLE = "POSSIBLE"
    UNKNOWN = "UNKNOWN"


class ErrorCategory(str, Enum):
    SYNTAX = "SYNTAX"
    RUNTIME_EXCEPTION = "RUNTIME_EXCEPTION"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    TIMEOUT = "TIMEOUT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    CONFIGURATION = "CONFIGURATION"


@dataclass
class DiagnosticHypothesis:
    """Hypothesis explaining the root cause of an error with evidence and suggested fix."""
    hypothesis_id: str = field(default_factory=lambda: f"hyp_{uuid.uuid4().hex[:8]}")
    confidence: DiagnosticConfidence = DiagnosticConfidence.PROBABLE
    summary: str = ""
    evidence: List[str] = field(default_factory=list)
    suggested_fix: Optional[str] = None
    target_file: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "confidence": self.confidence.value,
            "summary": self.summary,
            "evidence": list(self.evidence),
            "suggested_fix": self.suggested_fix,
            "target_file": self.target_file,
        }


@dataclass
class DiagnosticReport:
    """Complete diagnostic investigation result for an error or exception."""
    report_id: str = field(default_factory=lambda: f"diag_{uuid.uuid4().hex[:8]}")
    error_type: str = ""
    error_message: str = ""
    category: ErrorCategory = ErrorCategory.RUNTIME_EXCEPTION
    sanitized_stack_trace: str = ""
    affected_component: Optional[str] = None
    hypotheses: List[DiagnosticHypothesis] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "category": self.category.value,
            "sanitized_stack_trace": self.sanitized_stack_trace,
            "affected_component": self.affected_component,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "created_at": self.created_at,
        }
