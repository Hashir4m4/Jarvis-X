"""
Unit and integration tests for Prompt 65 — Human-in-the-Loop Autonomous Control Framework.
Tests risk tier classification, human approval flow, expiration protection,
payload tampering prevention, and emergency stop enforcement.
"""

import time
import pytest
from backend.control.models import (
    RiskTier,
    ApprovalStatus,
    UnifiedApprovalRequest,
)
from backend.control.framework import AutonomousControlFramework


class MockSecurityProxy:
    def __init__(self, allow_all: bool = True):
        self.allow_all = allow_all
        self.calls = []

    def request_confirmation(self, action_name: str, details: str) -> bool:
        self.calls.append((action_name, details))
        return self.allow_all


def test_risk_tier_auto_vs_manual_approval():
    framework = AutonomousControlFramework(security_proxy=MockSecurityProxy(allow_all=True))

    # Tier 0 (Read-only) auto-approves
    req_t0 = framework.request_approval(
        action_type="code_analysis",
        subsystem="code_intelligence",
        risk_tier=RiskTier.TIER_0_READ_ONLY,
        description="Run static scan",
        parameters={"path": "backend/"},
    )
    assert req_t0.status == ApprovalStatus.APPROVED
    assert req_t0.decided_by == "auto_policy"

    # Tier 3 (Code modification) requires explicit human approval
    req_t3 = framework.request_approval(
        action_type="apply_patch",
        subsystem="code_modification",
        risk_tier=RiskTier.TIER_3_ELEVATED,
        description="Apply hotfix patch",
        parameters={"file": "server.py", "lines": 10},
    )
    assert req_t3.status == ApprovalStatus.PENDING

    # Human approves
    approved = framework.approve_request(req_t3.request_id, approver="HumanOperator")
    assert approved is True
    assert req_t3.status == ApprovalStatus.APPROVED
    assert req_t3.decided_by == "HumanOperator"


def test_tampered_payload_hash_rejection():
    framework = AutonomousControlFramework(security_proxy=MockSecurityProxy(allow_all=True))
    params = {"target_file": "config.json", "action": "update", "value": 42}

    req = framework.request_approval(
        action_type="modify_config",
        subsystem="config",
        risk_tier=RiskTier.TIER_3_ELEVATED,
        description="Update config param",
        parameters=params,
    )
    framework.approve_request(req.request_id, approver="Admin")

    # Verification with identical parameters succeeds
    assert framework.verify_action_authorized(req.request_id, params) is True

    # Tampered parameters (e.g. value changed to 999) must be rejected
    tampered_params = dict(params)
    tampered_params["value"] = 999
    assert framework.verify_action_authorized(req.request_id, tampered_params) is False


def test_approval_expiration():
    framework = AutonomousControlFramework(security_proxy=MockSecurityProxy(allow_all=True))

    # Request with 0.05s timeout
    req = framework.request_approval(
        action_type="sensitive_action",
        subsystem="system",
        risk_tier=RiskTier.TIER_3_ELEVATED,
        description="Ephemeral action",
        parameters={"id": 1},
        timeout_seconds=0.05,
    )
    time.sleep(0.08)

    # Attempting to approve an expired request fails
    approved = framework.approve_request(req.request_id, approver="Admin")
    assert approved is False
    assert req.status == ApprovalStatus.EXPIRED


def test_emergency_stop_blocks_all_actions():
    framework = AutonomousControlFramework(security_proxy=MockSecurityProxy(allow_all=True))
    framework.trigger_emergency_stop(reason="Unexpected autonomous behavior detected")
    assert framework.is_emergency_stop_active() is True

    # Cannot request new approvals during emergency stop
    with pytest.raises(RuntimeError, match="EMERGENCY STOP"):
        framework.request_approval(
            action_type="test",
            subsystem="test",
            risk_tier=RiskTier.TIER_0_READ_ONLY,
            description="Test action",
            parameters={},
        )

    # Clear emergency stop
    framework.clear_emergency_stop(authorizer="SafetyOfficer")
    assert framework.is_emergency_stop_active() is False
