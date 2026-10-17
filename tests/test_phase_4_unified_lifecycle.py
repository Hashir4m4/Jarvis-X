"""
Phase 4 Unified End-to-End Integration Tests.
Validates the complete autonomous intelligence lifecycle:
Understand -> Plan -> Prioritize -> Propose -> Obtain Approval -> Execute -> Monitor -> Debug -> Learn -> Improve.
"""

import pytest
from backend.core.container import AppContainer
from backend.core.core import JarvisCore
from backend.goals.models import Goal, GoalType, GoalStatus
from backend.control.models import RiskTier, ApprovalStatus
from backend.planning.long_horizon_models import Milestone, CriticalPath, LongHorizonPlan, PlanStatus
from backend.workflows.models import WorkflowStatus


class HeadlessSecurityProxy:
    def __init__(self):
        self.confirmed = True

    def is_dangerous(self, action_name: str) -> bool:
        return True

    def request_confirmation(self, action_name: str, details: str) -> bool:
        return self.confirmed


@pytest.mark.asyncio
async def test_complete_phase_4_unified_lifecycle():
    # 1. Initialize JarvisCore with config
    core = JarvisCore(config={"learning": {"enabled": True}})
    core.security.confirmation_callback = lambda action, details: True
    if hasattr(core.container, "security") and core.container.security:
        core.container.security.confirmation_callback = lambda action, details: True

    # 2. Plan Formulation & Approval
    goal = core.goal_engine.create_goal(
        title="Autonomous Deployment Pipeline",
        description="End-to-end automated system deployment",
        goal_type=GoalType.LONG_TERM,
        status=GoalStatus.ACTIVE,
        target_date="2026-11-15",
    )

    plan = core.create_long_horizon_plan(
        goal_id=goal.goal_id,
        title="Deployment Strategic Plan",
        author="UserLead",
        deadline="2026-11-15",
    )
    assert plan is not None
    assert plan.status == PlanStatus.DRAFT

    # Submit for approval, then approve and activate
    submitted_plan = core.submit_plan_for_approval(plan.plan_id)
    assert submitted_plan.status == PlanStatus.PROPOSED
    approved_plan = core.approve_plan(plan.plan_id, reviewer="HumanLead")
    assert approved_plan.status == PlanStatus.APPROVED
    active_plan = core.activate_plan(plan.plan_id, user="HumanLead")
    assert active_plan.status == PlanStatus.ACTIVE

    # 3. Priority Intelligence & Recommendations
    p_recs = core.get_priority_recommendations()
    assert len(p_recs) >= 1
    assert any(r.item_id == goal.goal_id for r in p_recs)

    # 4. Project Intelligence Integration
    proj = core.register_personal_project(
        name="Apollo Launch System",
        description="E2E Pipeline Project",
        linked_goal_ids=[goal.goal_id],
    )
    status_report = core.get_project_status(proj.project_id)
    assert status_report["name"] == "Apollo Launch System"
    assert len(status_report["linked_goals"]) == 1

    # 5. Workflow Conversion (Non-execution guarantee: Status is PENDING_APPROVAL)
    wf = core.convert_plan_to_workflow(plan.plan_id)
    assert wf is not None
    assert wf.status == WorkflowStatus.PENDING_APPROVAL
    assert len(wf.steps) >= 1

    # 6. Human-in-the-Loop Unified Approval Gate (Prompt 65)
    approval_req = core.request_autonomous_action_approval(
        action_type="execute_workflow",
        subsystem="workflows",
        risk_tier=RiskTier.TIER_2_CONTROLLED,
        description=f"Execute workflow for plan {plan.plan_id}",
        parameters={"workflow_id": wf.workflow_id},
    )
    assert approval_req.status == ApprovalStatus.PENDING

    # Human grants explicit approval
    approved = core.approve_autonomous_action(approval_req.request_id, approver="HumanLead")
    assert approved is True

    # 7. Authorized Workflow Execution
    exec_record = core.workflow_engine._active_executions.get(wf.workflow_id)
    from backend.workflows.models import WorkflowExecution
    if not exec_record:
        exec_record = WorkflowExecution(execution_id=f"exec_{wf.workflow_id}", workflow_id=wf.workflow_id)

    auth_ok = core.authorize_workflow_execution(exec_record, authorizer="HumanLead")
    assert auth_ok is True

    # Mock registry for simulated execution in test environment
    core.workflow_engine.skill_registry = None
    exec_result = core.execute_workflow(wf, exec_record)
    assert exec_result.status == WorkflowStatus.COMPLETED
    assert len(exec_result.audit_trail) >= 1

    # 8. Code Analysis & Modification Under Control
    code_report = core.analyze_codebase("backend/control", max_files=5)
    assert code_report.total_files_analyzed >= 1

    # 9. Intelligent Debugging
    try:
        raise KeyError("missing_metric_key")
    except KeyError as exc:
        diag = core.diagnose_error(exc, affected_component="telemetry")
        assert diag.error_type == "KeyError"
        assert len(diag.hypotheses) >= 1

    # 10. Continuous Improvement Recommendations
    imp_recs = core.get_improvement_recommendations()
    assert isinstance(imp_recs, list)
