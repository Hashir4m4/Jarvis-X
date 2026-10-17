"""
Unit and integration tests for Prompt 58 — Autonomous Workflow Execution Subsystem.
Tests workflow domain models, conversion from approved plans, security authorization boundaries,
step dependencies, retry policies, cancellation, and execution audit logging.
"""

import pytest
import time
from backend.planning.long_horizon_models import (
    LongHorizonPlan,
    Milestone,
    PlanStatus,
    MilestoneStatus,
    RiskAssessment,
    CriticalPath,
)
from backend.planning.models import RiskLevel
from backend.workflows.models import (
    Workflow,
    WorkflowStep,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowExecution,
    ExecutionPolicy,
    ExecutionRiskLevel,
    ExecutionAuditRecord,
)
from backend.workflows.converter import PlanToWorkflowConverter
from backend.workflows.engine import WorkflowExecutionEngine
from backend.core.models import SkillResult


class MockSecurityProxy:
    def __init__(self, allow_all: bool = True):
        self.allow_all = allow_all
        self.calls = []

    def is_dangerous(self, action_name: str) -> bool:
        return True

    def request_confirmation(self, action_name: str, details: str) -> bool:
        self.calls.append((action_name, details))
        return self.allow_all


class MockSkillRegistry:
    def __init__(self, failure_actions: list = None):
        self.failure_actions = failure_actions or []
        self.invocations = []

    def execute_intent(self, intent):
        self.invocations.append(intent)
        if intent.action in self.failure_actions:
            return SkillResult(
                success=False,
                status="failed",
                message=f"Intent {intent.action} failed as requested",
            )
        return SkillResult(
            success=True,
            status="completed",
            message=f"Executed {intent.skill_name}:{intent.action}",
            data={"status": "ok", "action": intent.action},
        )


def _make_approved_plan() -> LongHorizonPlan:
    m1 = Milestone(
        milestone_id="m1_spec",
        sequence=1,
        title="Specification Document",
        description="Draft spec in vault",
        estimated_duration=3,
        depends_on=[],
        metadata={"risk_level": "LOW"},
    )
    m2 = Milestone(
        milestone_id="m2_code",
        sequence=2,
        title="Core Implementation",
        description="Develop code modules",
        estimated_duration=5,
        depends_on=["m1_spec"],
        metadata={"risk_level": "HIGH"},
    )
    cp = CriticalPath(critical_milestones=["m1_spec", "m2_code"], total_duration=8)
    return LongHorizonPlan(
        plan_id="plan_test_01",
        title="Test Strategic Plan",
        linked_goal_id="goal_100",
        milestones=[m1, m2],
        critical_path=cp,
        status=PlanStatus.APPROVED,
    )


def test_workflow_models_serialization():
    step = WorkflowStep(
        step_id="step_01",
        title="Run System Health",
        skill_name="system",
        action="get_system_info",
        policy=ExecutionPolicy(max_retries=3, risk_level=ExecutionRiskLevel.LOW),
    )
    wf = Workflow(
        workflow_id="wf_01",
        title="Health Check Flow",
        steps=[step],
        status=WorkflowStatus.DRAFT,
    )
    data = wf.to_dict()
    assert data["workflow_id"] == "wf_01"
    assert len(data["steps"]) == 1

    restored = Workflow.from_dict(data)
    assert restored.workflow_id == "wf_01"
    assert restored.steps[0].action == "get_system_info"
    assert restored.steps[0].policy.max_retries == 3


def test_converter_requires_approved_plan():
    converter = PlanToWorkflowConverter()
    draft_plan = _make_approved_plan()
    draft_plan.status = PlanStatus.DRAFT

    with pytest.raises(ValueError, match="Cannot convert plan"):
        converter.convert(draft_plan)

    # Approved plan converts cleanly
    approved_plan = _make_approved_plan()
    wf = converter.convert(approved_plan)
    assert wf.origin_plan_id == "plan_test_01"
    assert len(wf.steps) == 2
    assert wf.steps[0].step_id == "step_m1_spec"
    assert wf.steps[1].dependencies == ["step_m1_spec"]
    assert wf.steps[1].policy.risk_level == ExecutionRiskLevel.HIGH
    assert wf.steps[1].policy.requires_approval is True
    # Non-execution guarantee: Status must be PENDING_APPROVAL
    assert wf.status == WorkflowStatus.PENDING_APPROVAL


def test_execution_requires_explicit_authorization():
    registry = MockSkillRegistry()
    security = MockSecurityProxy(allow_all=True)
    engine = WorkflowExecutionEngine(skill_registry=registry, security_proxy=security)

    wf = Workflow(
        workflow_id="wf_unauth",
        title="Unauth Flow",
        steps=[WorkflowStep("s1", "Step 1", "system", "get_system_info")],
    )
    exec_record = WorkflowExecution(execution_id="exec_unauth", workflow_id="wf_unauth")

    # Attempting to execute without authorization must fail
    with pytest.raises(PermissionError, match="requires 'APPROVED'"):
        engine.execute_workflow(wf, exec_record)

    # Authorizing via engine validates confirmation and transitions state
    authorized = engine.authorize_execution(exec_record, authorizer="UserAdmin")
    assert authorized is True
    assert exec_record.status == WorkflowStatus.APPROVED
    assert len(security.calls) > 0


def test_successful_dag_execution_and_audit():
    registry = MockSkillRegistry()
    security = MockSecurityProxy(allow_all=True)
    engine = WorkflowExecutionEngine(skill_registry=registry, security_proxy=security)

    s1 = WorkflowStep("s1", "Step 1", "system", "get_system_info", dependencies=[])
    s2 = WorkflowStep("s2", "Step 2", "vault", "create_note", dependencies=["s1"])
    wf = Workflow(workflow_id="wf_run", steps=[s1, s2])
    exec_record = WorkflowExecution(execution_id="exec_run", workflow_id="wf_run")

    engine.authorize_execution(exec_record, authorizer="Tester")
    res = engine.execute_workflow(wf, exec_record)

    assert res.status == WorkflowStatus.COMPLETED
    assert wf.status == WorkflowStatus.COMPLETED
    assert len(registry.invocations) == 2
    assert s1.status == WorkflowStepStatus.COMPLETED
    assert s2.status == WorkflowStepStatus.COMPLETED
    # Audit trail verification
    assert len(res.audit_trail) == 2
    assert all(a.status == "COMPLETED" for a in res.audit_trail)


def test_dependency_failure_blocks_downstream_steps():
    # s1 fails, so s2 should be marked BLOCKED and not executed
    registry = MockSkillRegistry(failure_actions=["failing_action"])
    security = MockSecurityProxy(allow_all=True)
    engine = WorkflowExecutionEngine(skill_registry=registry, security_proxy=security)

    s1 = WorkflowStep("s1", "Fail Step", "system", "failing_action", dependencies=[])
    s2 = WorkflowStep("s2", "Dependent Step", "vault", "create_note", dependencies=["s1"])
    wf = Workflow(workflow_id="wf_fail", steps=[s1, s2])
    exec_record = WorkflowExecution(execution_id="exec_fail", workflow_id="wf_fail")

    engine.authorize_execution(exec_record, authorizer="Tester")
    res = engine.execute_workflow(wf, exec_record)

    assert res.status == WorkflowStatus.FAILED
    assert s1.status == WorkflowStepStatus.FAILED
    assert s2.status == WorkflowStepStatus.BLOCKED
    assert len(registry.invocations) == 3  # 1 initial + 2 retries
    # Dependent step was never invoked
    assert not any(inv.action == "create_note" for inv in registry.invocations)


def test_execution_cancellation():
    registry = MockSkillRegistry()
    security = MockSecurityProxy(allow_all=True)
    engine = WorkflowExecutionEngine(skill_registry=registry, security_proxy=security)

    s1 = WorkflowStep("s1", "Step 1", "system", "get_system_info")
    wf = Workflow(workflow_id="wf_cancel", steps=[s1])
    exec_record = WorkflowExecution(execution_id="exec_cancel", workflow_id="wf_cancel")

    engine.authorize_execution(exec_record, authorizer="Tester")
    # Cancel execution
    engine.cancel_execution("exec_cancel", reason="Aborted by user")
    assert exec_record.status == WorkflowStatus.CANCELLED

    res = engine.execute_workflow(wf, exec_record)
    assert res.status == WorkflowStatus.CANCELLED
    assert s1.status == WorkflowStepStatus.CANCELLED
