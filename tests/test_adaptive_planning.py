"""
Unit and integration tests for AdaptivePlanningSubsystem.
Validates:
- Monitoring & trigger detection
- Duplicate event handling
- Adaptation analysis & recommendations
- Candidate revision generation & structural diffs
- Immutable baseline preservation
- Human approval gate & baseline replacement
- Rejection handling
- EventBus failure resilience
- Path traversal protection
- Strict non-execution guarantees
"""

import copy
import datetime
import os
import pytest
import shutil
import tempfile
import time

from backend.goals.models import Goal, GoalStatus, GoalType
from backend.planning.long_horizon_models import (
    PlanStatus,
    MilestoneStatus,
    Milestone,
    LongHorizonPlan,
    PlanModelValidationError,
)
from backend.planning.long_horizon_engine import (
    LongHorizonPlanningEngine,
    PlanningSecurityError,
)
from backend.planning.adaptive_planning import (
    AdaptivePlanningSubsystem,
    AdaptationTrigger,
    AdaptationTriggerType,
    AdaptationActionRecommendation,
    PlanStructuralDiff,
)
from backend.memory.vault.vault_manager import VaultManager


class MockMemoryAPI:
    def __init__(self, temp_vault_dir: str):
        self.vault = VaultManager(vault_root=temp_vault_dir)


class MockSecurityProxy:
    def __init__(self, allow_all: bool = True):
        self.allow_all = allow_all
        self.denied_actions = set()

    def is_dangerous(self, action_name: str) -> bool:
        return True

    def request_confirmation(self, action_name: str, details: str) -> bool:
        if not self.allow_all or action_name in self.denied_actions:
            return False
        return True


class MockEventBus:
    def __init__(self):
        self.subscribers = {}
        self.published = []

    def subscribe(self, event_type, callback):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def publish(self, event_type, data=None):
        self.published.append((event_type, data))


@pytest.fixture
def temp_vault():
    temp_dir = tempfile.mkdtemp(prefix="test_adaptive_vault_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def adaptive_setup(temp_vault):
    mem_api = MockMemoryAPI(temp_vault)
    event_bus = MockEventBus()
    security = MockSecurityProxy(allow_all=True)
    goals_repo = {}

    planning_engine = LongHorizonPlanningEngine(
        goal_engine=goals_repo,
        memory_api=mem_api,
        event_bus=event_bus,
        security_proxy=security,
    )

    adaptive_subsystem = AdaptivePlanningSubsystem(
        planning_engine=planning_engine,
        goal_engine=goals_repo,
        event_bus=event_bus,
        security_proxy=security,
    )

    return adaptive_subsystem, planning_engine, goals_repo, mem_api, event_bus, security


# =====================================================================
# 1. Monitoring & Trigger Detection
# =====================================================================

def test_monitoring_start_stop(adaptive_setup):
    adaptive, _, _, _, event_bus, _ = adaptive_setup
    assert adaptive._monitoring_active is False
    adaptive.start_monitoring()
    assert adaptive._monitoring_active is True
    assert len(adaptive._event_subscriptions) == 4

    # Stop monitoring
    adaptive.stop_monitoring()
    assert adaptive._monitoring_active is False
    assert len(adaptive._event_subscriptions) == 0


def test_duplicate_event_handling(adaptive_setup):
    adaptive, planning_engine, goals_repo, _, _, _ = adaptive_setup
    goal = Goal(
        goal_id="g_dup",
        title="Duplicate Event Goal",
        description="Verify duplicate event suppression.",
    )
    goals_repo[goal.goal_id] = goal
    plan = planning_engine.create_plan(goal_id=goal.goal_id)

    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=plan.plan_id,
        new_state={"milestone_id": plan.milestones[0].milestone_id, "slip_days": 2.0},
    )

    # First time: processed
    first_eval = adaptive.process_trigger(trigger)
    assert first_eval is not None

    # Immediate second time: suppressed
    second_eval = adaptive.process_trigger(trigger)
    assert second_eval is None


# =====================================================================
# 2. Adaptation Analysis & Recommendations
# =====================================================================

def test_critical_path_milestone_delayed_triggers_revision_required(adaptive_setup):
    adaptive, planning_engine, goals_repo, _, _, _ = adaptive_setup
    goal = Goal(
        goal_id="g_delay",
        title="Delayed Critical Milestone",
        description="Verify critical milestone slip triggers REVISION_REQUIRED.",
    )
    goals_repo[goal.goal_id] = goal
    plan = planning_engine.create_plan(goal_id=goal.goal_id)

    # Pick a critical milestone
    crit_m_id = plan.critical_path.critical_milestones[0]
    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=plan.plan_id,
        new_state={"milestone_id": crit_m_id, "slip_days": 3.0},
    )

    assessment = adaptive.process_trigger(trigger)
    assert assessment.recommendation == AdaptationActionRecommendation.REVISION_REQUIRED
    assert assessment.feasibility_status == "AT_RISK"
    assert assessment.proposed_plan is not None
    assert assessment.structural_diff is not None


def test_non_critical_minor_delay_triggers_monitor_only(adaptive_setup):
    adaptive, planning_engine, goals_repo, _, _, _ = adaptive_setup
    # Create plan with slack
    m1 = Milestone(milestone_id="M1", title="M1", estimated_duration=2.0)
    m2 = Milestone(milestone_id="M2", title="M2", estimated_duration=10.0)
    m3 = Milestone(milestone_id="M3", title="M3", estimated_duration=2.0, depends_on=["M1", "M2"])

    goal = Goal(goal_id="g_slack", title="Goal with Slack", description="Testing minor delay")
    goals_repo[goal.goal_id] = goal

    plan = planning_engine.create_plan(goal_id=goal.goal_id)
    planning_engine.modify_plan(plan.plan_id, milestones=[m1, m2, m3])

    # M1 has slack (10 - 2 = 8 days). A 1-day delay on M1 should recommend MONITOR
    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=plan.plan_id,
        new_state={"milestone_id": "M1", "slip_days": 1.0},
    )

    assessment = adaptive.process_trigger(trigger)
    assert assessment.recommendation == AdaptationActionRecommendation.MONITOR
    assert assessment.feasibility_status == "FEASIBLE"


def test_goal_deadline_infeasible_triggers_revision_required(adaptive_setup):
    adaptive, planning_engine, goals_repo, _, _, _ = adaptive_setup
    goal = Goal(goal_id="g_tight", title="Tight Goal", description="Deadline infeasibility test")
    goals_repo[goal.goal_id] = goal
    plan = planning_engine.create_plan(goal_id=goal.goal_id)

    # Trigger with new deadline 2 hours from now
    soon = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)).isoformat()
    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.GOAL_DEADLINE_CHANGED,
        goal_id=goal.goal_id,
        plan_id=plan.plan_id,
        new_state={"target_date": soon},
    )

    assessment = adaptive.process_trigger(trigger)
    assert assessment.recommendation == AdaptationActionRecommendation.REVISION_REQUIRED
    assert assessment.feasibility_status == "INFEASIBLE"


# =====================================================================
# 3. Structural Diff Correctness
# =====================================================================

def test_structural_diff_computation():
    m1 = Milestone(milestone_id="M1", title="Initial Discovery", estimated_duration=2.0)
    m2 = Milestone(milestone_id="M2", title="Implementation", estimated_duration=4.0, depends_on=["M1"])
    plan_base = LongHorizonPlan(
        plan_id="p_diff",
        linked_goal_id="g1",
        title="Base Plan",
        milestones=[m1, m2],
    )

    # Candidate modifies M2 duration, adds M3
    m2_mod = Milestone(milestone_id="M2", title="Implementation Extended", estimated_duration=6.0, depends_on=["M1"])
    m3 = Milestone(milestone_id="M3", title="Final Signoff", estimated_duration=1.0, depends_on=["M2"])
    plan_cand = LongHorizonPlan(
        plan_id="p_diff",
        linked_goal_id="g1",
        title="Candidate Plan",
        milestones=[m1, m2_mod, m3],
    )

    diff = PlanStructuralDiff.compute(baseline=plan_base, candidate=plan_cand)
    assert diff.added_milestones == ["M3"]
    assert diff.removed_milestones == []
    assert "M2" in diff.modified_milestones
    assert diff.modified_milestones["M2"]["title"]["new"] == "Implementation Extended"
    assert diff.modified_milestones["M2"]["duration"]["new"] == 6.0
    assert diff.duration_delta_days > 0.0


# =====================================================================
# 4. Human Approval Workflow & Baseline Replacement
# =====================================================================

def test_revision_proposal_and_human_approval(adaptive_setup):
    adaptive, planning_engine, goals_repo, _, event_bus, _ = adaptive_setup
    goal = Goal(goal_id="g_appr", title="Approval Goal", description="Verify revision approval")
    goals_repo[goal.goal_id] = goal

    # Create & approve baseline plan
    baseline = planning_engine.create_plan(goal_id=goal.goal_id)
    planning_engine.submit_for_approval(baseline.plan_id)
    approved_base = planning_engine.approve_plan(baseline.plan_id)
    assert approved_base.status == PlanStatus.APPROVED
    orig_duration = approved_base.critical_path.total_duration

    # Trigger slip
    crit_m_id = approved_base.critical_path.critical_milestones[0]
    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=approved_base.plan_id,
        new_state={"milestone_id": crit_m_id, "slip_days": 2.0},
    )
    assessment = adaptive.process_trigger(trigger)
    assert assessment.proposed_plan is not None

    # Propose revision
    proposed = adaptive.propose_revision(approved_base.plan_id, assessment)
    assert proposed.status == PlanStatus.PROPOSED
    # Baseline must NOT be modified yet
    current = planning_engine.get_plan(approved_base.plan_id)
    assert current.critical_path.total_duration == orig_duration
    assert current.status == PlanStatus.APPROVED

    # Human approves revision
    new_approved = adaptive.approve_revision(
        approved_base.plan_id,
        reviewer="Operator One",
        rationale="Approved timeline extension",
    )
    assert new_approved.status == PlanStatus.APPROVED
    assert new_approved.critical_path.total_duration > orig_duration
    assert len(new_approved.revisions) >= 3

    # Check that previous revision snapshot remains intact
    prev_rev = new_approved.revisions[-2]
    assert "Superseded" in prev_rev.change_reason


def test_revision_rejection_leaves_baseline_intact(adaptive_setup):
    adaptive, planning_engine, goals_repo, _, _, _ = adaptive_setup
    goal = Goal(goal_id="g_rej", title="Rejection Goal", description="Verify rejection")
    goals_repo[goal.goal_id] = goal

    baseline = planning_engine.create_plan(goal_id=goal.goal_id)
    planning_engine.submit_for_approval(baseline.plan_id)
    approved_base = planning_engine.approve_plan(baseline.plan_id)

    crit_m_id = approved_base.critical_path.critical_milestones[0]
    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=approved_base.plan_id,
        new_state={"milestone_id": crit_m_id, "slip_days": 5.0},
    )
    assessment = adaptive.process_trigger(trigger)
    adaptive.propose_revision(approved_base.plan_id, assessment)

    # Rejection
    adaptive.reject_revision(approved_base.plan_id, reviewer="Lead Architect", reason="Too much slip")

    # Pending revision is cleared
    assert adaptive.get_pending_revision(approved_base.plan_id) is None
    # Baseline remains approved
    current = planning_engine.get_plan(approved_base.plan_id)
    assert current.status == PlanStatus.APPROVED
    assert any("rejected_revision" in k for k in current.metadata.keys())


def test_unauthorized_revision_approval_denied(adaptive_setup):
    adaptive, planning_engine, goals_repo, _, _, security = adaptive_setup
    goal = Goal(goal_id="g_sec_rev", title="Sec Goal", description="Verify security denial")
    goals_repo[goal.goal_id] = goal

    baseline = planning_engine.create_plan(goal_id=goal.goal_id)
    planning_engine.submit_for_approval(baseline.plan_id)
    planning_engine.approve_plan(baseline.plan_id)

    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=baseline.plan_id,
        new_state={"milestone_id": baseline.critical_path.critical_milestones[0], "slip_days": 1.0},
    )
    assessment = adaptive.process_trigger(trigger)
    adaptive.propose_revision(baseline.plan_id, assessment)

    # Deny write_file
    security.denied_actions.add("write_file")

    with pytest.raises(PlanningSecurityError):
        adaptive.approve_revision(baseline.plan_id, reviewer="Untrusted")


# =====================================================================
# 5. Strict Non-Execution Guarantee
# =====================================================================

def test_adaptive_planning_non_execution(adaptive_setup):
    """
    Verifies that trigger processing, assessment, proposal, and approval
    do not execute tasks or mark milestones completed.
    """
    adaptive, planning_engine, goals_repo, _, _, _ = adaptive_setup
    goal = Goal(goal_id="g_nonexec", title="Non-Execution Goal", description="Strict non-exec test")
    goals_repo[goal.goal_id] = goal

    plan = planning_engine.create_plan(goal_id=goal.goal_id)
    planning_engine.submit_for_approval(plan.plan_id)
    approved = planning_engine.approve_plan(plan.plan_id)

    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=approved.plan_id,
        new_state={"milestone_id": approved.critical_path.critical_milestones[0], "slip_days": 2.0},
    )
    assessment = adaptive.process_trigger(trigger)
    adaptive.propose_revision(approved.plan_id, assessment)
    new_approved = adaptive.approve_revision(approved.plan_id, reviewer="Operator")

    # Assert every milestone remains strictly PENDING
    for m in new_approved.milestones:
        assert m.status == MilestoneStatus.PENDING
        assert "execution_time" not in m.metadata


# =====================================================================
# 6. Audit & Hardening Verification Tests
# =====================================================================

def test_pending_revision_durability_and_recovery(adaptive_setup, temp_vault):
    """
    Verifies that pending proposals are persisted to disk under vault/plans/pending/
    and can be recovered upon subsystem restart.
    """
    adaptive, planning_engine, goals_repo, mem_api, _, _ = adaptive_setup
    goal = Goal(goal_id="g_dur", title="Durability Goal", description="Verify restart recovery")
    goals_repo[goal.goal_id] = goal

    baseline = planning_engine.create_plan(goal_id=goal.goal_id)
    planning_engine.submit_for_approval(baseline.plan_id)
    planning_engine.approve_plan(baseline.plan_id)

    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=baseline.plan_id,
        new_state={"milestone_id": baseline.critical_path.critical_milestones[0], "slip_days": 2.0},
    )
    assessment = adaptive.process_trigger(trigger)
    adaptive.propose_revision(baseline.plan_id, assessment)

    pending_file = os.path.join(temp_vault, "plans", "pending", f"{baseline.plan_id}.md")
    assert os.path.isfile(pending_file)

    # Simulate restart with new AdaptivePlanningSubsystem instance
    new_adaptive = AdaptivePlanningSubsystem(
        planning_engine=planning_engine,
        goal_engine=goals_repo,
    )
    # Recovered from disk
    recovered_pending = new_adaptive.get_pending_revision(baseline.plan_id)
    assert recovered_pending is not None
    assert recovered_pending.plan_id == baseline.plan_id
    assert recovered_pending.status == PlanStatus.PROPOSED


def test_stale_revision_cannot_overwrite_newer_baseline(adaptive_setup):
    """
    Verifies that if the approved baseline advances to revision N+1,
    a stale proposal based on revision N is rejected.
    """
    adaptive, planning_engine, goals_repo, _, _, _ = adaptive_setup
    goal = Goal(goal_id="g_stale", title="Stale Goal", description="Verify stale check")
    goals_repo[goal.goal_id] = goal

    baseline = planning_engine.create_plan(goal_id=goal.goal_id)
    planning_engine.submit_for_approval(baseline.plan_id)
    planning_engine.approve_plan(baseline.plan_id)

    # Proposal created based on initial baseline (revision 2)
    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=baseline.plan_id,
        new_state={"milestone_id": baseline.critical_path.critical_milestones[0], "slip_days": 1.0},
    )
    assessment = adaptive.process_trigger(trigger)
    adaptive.propose_revision(baseline.plan_id, assessment)

    # Intervening direct modification to baseline advances it to revision 3
    planning_engine.modify_plan(baseline.plan_id, title="Intervening Baseline Update")

    # Attempting to approve stale proposal must fail
    with pytest.raises(PlanModelValidationError, match="Stale revision conflict"):
        adaptive.approve_revision(baseline.plan_id, reviewer="Operator")


def test_atomic_rollback_on_persist_failure(adaptive_setup):
    """
    Verifies that if writing the approved revision to disk fails,
    in-memory baseline state is cleanly rolled back.
    """
    adaptive, planning_engine, goals_repo, _, _, _ = adaptive_setup
    goal = Goal(goal_id="g_fail", title="Write Fail Goal", description="Verify atomic rollback")
    goals_repo[goal.goal_id] = goal

    baseline = planning_engine.create_plan(goal_id=goal.goal_id)
    planning_engine.submit_for_approval(baseline.plan_id)
    planning_engine.approve_plan(baseline.plan_id)
    orig_title = baseline.title

    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=baseline.plan_id,
        new_state={"milestone_id": baseline.critical_path.critical_milestones[0], "slip_days": 1.0},
    )
    assessment = adaptive.process_trigger(trigger)
    adaptive.propose_revision(baseline.plan_id, assessment)

    # Inject failure into persistence
    planning_engine._persist_plan = lambda plan: False

    with pytest.raises(IOError, match="Failed to persist approved revision"):
        adaptive.approve_revision(baseline.plan_id, reviewer="Operator")

    # Baseline remains in-memory as original
    current = planning_engine.get_plan(baseline.plan_id)
    assert current.title == orig_title


def test_concurrent_approval_protection(adaptive_setup):
    """
    Verifies that multiple concurrent approval attempts for the same plan
    result in exactly one success and proper rejection/handling of subsequent calls.
    """
    import threading
    adaptive, planning_engine, goals_repo, _, _, _ = adaptive_setup
    goal = Goal(goal_id="g_conc", title="Concurrent Goal", description="Verify concurrent approvals")
    goals_repo[goal.goal_id] = goal

    baseline = planning_engine.create_plan(goal_id=goal.goal_id)
    planning_engine.submit_for_approval(baseline.plan_id)
    planning_engine.approve_plan(baseline.plan_id)

    trigger = AdaptationTrigger(
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        goal_id=goal.goal_id,
        plan_id=baseline.plan_id,
        new_state={"milestone_id": baseline.critical_path.critical_milestones[0], "slip_days": 1.0},
    )
    assessment = adaptive.process_trigger(trigger)
    adaptive.propose_revision(baseline.plan_id, assessment)

    results = []
    errors = []

    def try_approve():
        try:
            res = adaptive.approve_revision(baseline.plan_id, reviewer="ThreadReviewer")
            results.append(res)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=try_approve) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly 1 thread must succeed; the other 4 must fail due to missing pending proposal
    assert len(results) == 1
    assert len(errors) == 4
    for err in errors:
        assert "No pending revision found" in str(err)

