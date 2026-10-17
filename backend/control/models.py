"""
JARVIS X — Human-in-the-Loop Autonomous Control Framework
Domain models for unified approvals, risk categorization, intervention policies, and emergency stops.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class RiskTier(str, Enum):
    TIER_0_READ_ONLY = "TIER_0_READ_ONLY"      # Analysis, status, search (Auto-allowed)
    TIER_1_INTERNAL = "TIER_1_INTERNAL"        # Internal planning, metrics (Auto-allowed)
    TIER_2_CONTROLLED = "TIER_2_CONTROLLED"    # Standard non-destructive workflow steps (Assisted)
    TIER_3_ELEVATED = "TIER_3_ELEVATED"        # Code modification, vault note edit (Requires human approval)
    TIER_4_CRITICAL = "TIER_4_CRITICAL"        # Destructive, deletion, system shutdown (Always prompt human)


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


@dataclass
class UnifiedApprovalRequest:
    """Unified request model governing any sensitive or autonomous action across Phase 4."""
    request_id: str = field(default_factory=lambda: f"apr_{uuid.uuid4().hex[:8]}")
    action_type: str = ""
    subsystem: str = ""
    risk_tier: RiskTier = RiskTier.TIER_2_CONTROLLED
    description: str = ""
    target_resource: Optional[str] = None
    parameters_snapshot: Dict[str, Any] = field(default_factory=dict)
    payload_hash: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_by: str = "JARVIS"
    decided_by: Optional[str] = None
    decided_at: Optional[float] = None
    expires_at: float = field(default_factory=lambda: time.time() + 300.0)  # 5 min expiration
    rejection_reason: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "action_type": self.action_type,
            "subsystem": self.subsystem,
            "risk_tier": self.risk_tier.value,
            "description": self.description,
            "target_resource": self.target_resource,
            "payload_hash": self.payload_hash,
            "status": self.status.value,
            "requested_by": self.requested_by,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "expires_at": self.expires_at,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at,
        }
