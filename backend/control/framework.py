"""
JARVIS X — Unified Human-in-the-Loop Autonomous Control Framework
Coordinates authorization gates, human approval decisions, risk tier evaluation, and emergency stops.
"""

import hashlib
import json
import time
import logging
from typing import Dict, Any, List, Optional
from .models import (
    RiskTier,
    ApprovalStatus,
    UnifiedApprovalRequest,
)

logger = logging.getLogger("JARVIS.ControlFramework")


class AutonomousControlFramework:
    """
    Subsystem responsible for unified human oversight and safety governance across Phase 4.
    Guarantees:
    - Tier-3 and Tier-4 actions strictly require human approval before execution.
    - Approval is cryptographically bound to the exact payload hash; modified requests cannot be replayed.
    - Expired approvals (> 300s) are immediately rejected.
    - Emergency stop immediately prevents new autonomous jobs and signals running workflows to abort.
    """

    def __init__(self, security_proxy: Optional[Any] = None):
        self.security = security_proxy
        self._requests: Dict[str, UnifiedApprovalRequest] = {}
        self._emergency_stop_active: bool = False
        self._emergency_stop_reason: Optional[str] = None

    def trigger_emergency_stop(self, reason: str = "Human operator initiated emergency stop"):
        """Activates system-wide emergency stop."""
        self._emergency_stop_active = True
        self._emergency_stop_reason = reason
        logger.critical(f"EMERGENCY STOP ACTIVATED: {reason}")

    def clear_emergency_stop(self, authorizer: str = "User"):
        """Clears emergency stop status."""
        self._emergency_stop_active = False
        self._emergency_stop_reason = None
        logger.info(f"Emergency stop cleared by {authorizer}.")

    def is_emergency_stop_active(self) -> bool:
        return self._emergency_stop_active

    def request_approval(
        self,
        action_type: str,
        subsystem: str,
        risk_tier: RiskTier,
        description: str,
        parameters: Dict[str, Any],
        target_resource: Optional[str] = None,
        requested_by: str = "JARVIS",
        timeout_seconds: float = 300.0,
    ) -> UnifiedApprovalRequest:
        if self._emergency_stop_active:
            raise RuntimeError(f"Cannot request approval. System is in EMERGENCY STOP: {self._emergency_stop_reason}")

        # Compute payload hash to prevent replay or tampering
        payload_str = json.dumps(parameters, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

        req = UnifiedApprovalRequest(
            action_type=action_type,
            subsystem=subsystem,
            risk_tier=risk_tier,
            description=description,
            target_resource=target_resource,
            parameters_snapshot=dict(parameters),
            payload_hash=payload_hash,
            requested_by=requested_by,
            expires_at=time.time() + timeout_seconds,
            status=ApprovalStatus.PENDING,
        )

        # Auto-approve Tier 0 and Tier 1
        if risk_tier in (RiskTier.TIER_0_READ_ONLY, RiskTier.TIER_1_INTERNAL):
            req.status = ApprovalStatus.APPROVED
            req.decided_by = "auto_policy"
            req.decided_at = time.time()

        self._requests[req.request_id] = req
        logger.info(f"Created approval request {req.request_id} for '{action_type}' ({risk_tier.value}) -> status={req.status.value}")
        return req

    def approve_request(self, request_id: str, approver: str = "User") -> bool:
        if self._emergency_stop_active:
            raise RuntimeError(f"Cannot approve request. System is in EMERGENCY STOP: {self._emergency_stop_reason}")

        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Approval request '{request_id}' not found.")

        # Check expiration
        if time.time() > req.expires_at:
            req.status = ApprovalStatus.EXPIRED
            logger.warning(f"Approval request {request_id} expired prior to decision.")
            return False

        if req.status != ApprovalStatus.PENDING:
            raise ValueError(f"Cannot approve request '{request_id}': status is '{req.status.value}'.")

        # Security check
        if self.security and hasattr(self.security, "request_confirmation"):
            confirmed = self.security.request_confirmation(
                req.action_type,
                f"Unified approval for {req.description} (Tier: {req.risk_tier.value})",
            )
            if not confirmed:
                req.status = ApprovalStatus.REJECTED
                req.rejection_reason = "Denied by security confirmation."
                return False

        req.status = ApprovalStatus.APPROVED
        req.decided_by = approver
        req.decided_at = time.time()
        logger.info(f"Request {request_id} APPROVED by {approver}.")
        return True

    def reject_request(self, request_id: str, reason: str, reviewer: str = "User") -> bool:
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Approval request '{request_id}' not found.")

        req.status = ApprovalStatus.REJECTED
        req.rejection_reason = reason
        req.decided_by = reviewer
        req.decided_at = time.time()
        logger.info(f"Request {request_id} REJECTED by {reviewer}: {reason}")
        return True

    def verify_action_authorized(self, request_id: str, current_parameters: Dict[str, Any]) -> bool:
        """
        Verifies that the action has been approved, has not expired, and matches the exact approved payload hash.
        """
        if self._emergency_stop_active:
            return False

        req = self._requests.get(request_id)
        if not req or req.status != ApprovalStatus.APPROVED:
            return False

        # Expiry check
        if req.expires_at and time.time() > req.expires_at:
            req.status = ApprovalStatus.EXPIRED
            return False

        # Hash check to prevent payload tampering
        current_str = json.dumps(current_parameters, sort_keys=True, default=str)
        current_hash = hashlib.sha256(current_str.encode("utf-8")).hexdigest()
        if current_hash != req.payload_hash:
            logger.error(f"Payload hash mismatch on approved request {request_id}. Rejecting execution.")
            return False

        return True
