"""
JARVIS X — Autonomous Code Modification Subsystem
Domain models for patch proposals, unified diffs, approval boundaries, and atomic rollbacks.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class PatchStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


@dataclass
class CodePatchProposal:
    """Atomic patch proposal targeting a source file."""
    proposal_id: str = field(default_factory=lambda: f"patch_{uuid.uuid4().hex[:8]}")
    file_path: str = ""
    rationale: str = ""
    original_content: str = ""
    proposed_content: str = ""
    diff_unified: str = ""
    status: PatchStatus = PatchStatus.PROPOSED
    syntax_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    proposed_by: str = "JARVIS"
    approved_by: Optional[str] = None
    applied_at: Optional[float] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "file_path": self.file_path,
            "rationale": self.rationale,
            "diff_unified": self.diff_unified,
            "status": self.status.value,
            "syntax_valid": self.syntax_valid,
            "validation_errors": list(self.validation_errors),
            "proposed_by": self.proposed_by,
            "approved_by": self.approved_by,
            "applied_at": self.applied_at,
            "created_at": self.created_at,
        }
