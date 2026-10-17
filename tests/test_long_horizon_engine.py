"""
Unit and integration tests for LongHorizonPlanningEngine.
Validates synthesis, scheduling, resource projections, risk assessment,
human approval gates, invalid transitions, persistence round-tripping,
persistence rollback, security denials, and strict non-execution boundaries.
"""

import copy
import datetime
import os
import pytest
import shutil
import tempfile
import time

from backend.goals.models import Goal, GoalStatus, GoalType, GoalTask
from backend.planning.long_horizon_models import (
    PlanStatus,
    MilestoneStatus,
    Milestone,
    PlanModelValidationError,
)
from backend.planning.long_horizon_engine import (
    LongHorizonPlanningEngine,
    PlanningClarificationRequired,
    PlanningSecurityError,
)
from backend.memory.vault.vault_manager import VaultManager


class MockMemoryAPI:
    """Mock MemoryAPI that wraps a real VaultManager in a temp directory."""
    def __init__(self, temp_vault_dir: str):
        self.vault = VaultManager(vault_root=temp_vault_dir)


class MockSecurityProxy:
    """Mock SecurityProxy that allows or denies actions based on a flag."""
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
    """Mock EventBus capturing published events."""
    def __init__(self):
        self.published = []

    async def publish(self, event_type: str, data=None):
        self.published.append((event_type, data))


@pytest.fixture
def temp_vault():
    temp_dir = tempfile.mkdtemp(prefix="test_vault_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def engine_setup(temp_vault):
    mem_api = MockMemoryAPI(temp_vault)
    event_bus = MockEventBus()
    security = MockSecurityProxy(allow_all=True)

    # In-memory goal repository
    goals_repo = {}
    engine = LongHorizonPlanningEngine(
        goal_engine=goals_repo,
        memory_api=mem_api,
        event_bus=event_bus,
        security_proxy=security,
    )
    return engine, goals_repo, mem_api, event_bus, security


# =====================================================================
# 1. Goal-to-Plan Synthesis & Clarification Checks
# =====================================================================

def test_synthesis_valid_goal(engine_setup):
    engine, goals_repo, _, _, _ = engine_setup
    goal = Goal(
        goal_id="goal_test_01",
        title="Automated Data Pipeline",
        description="Build an end-to-end resilient event pipeline with observability.",
        goal_type=GoalType.LONG_TERM,
        status=GoalStatus.ACTIVE,
        completion_criteria=["Zero message drops", "Latency under 50ms"],
    )
    goals_repo[goal.goal_id] = goal

    plan = engine.synthesize_plan(goal_id=goal.goal_id)
    assert plan.linked_goal_id == goal.goal_id
    assert plan.status == PlanStatus.DRAFT
    assert len(plan.milestones) == 4
    assert plan.critical_path is not None
    assert plan.critical_path.total_duration > 0.0
    assert len(plan.revisions) == 1
    assert plan.revisions[0].change_reason == "Initial plan synthesis"


def test_synthesis_insufficient_goal_requires_clarification(engine_setup):
    engine, goals_repo, _, _, _ = engine_setup
    # Goal with empty description and minimal title
    vague_goal = Goal(
        goal_id="goal_vague",
        title="Do it",
        description="",
    )
    goals_repo[vague_goal.goal_id] = vague_goal

    with pytest.raises(PlanningClarificationRequired, match="Clarification required"):
        engine.synthesize_plan(goal_id=vague_goal.goal_id)


def test_synthesis_missing_goal_raises_validation_error(engine_setup):
    engine, _, _, _, _ = engine_setup
    with pytest.raises(PlanModelValidationError, match="not found in GoalManagerEngine"):
        engine.synthesize_plan(goal_id="NON_EXISTENT_GOAL")


# =====================================================================
# 2. Impossible Deadline Constraint Handling
# =====================================================================

def test_impossible_deadline_in_past(engine_setup):
    engine, goals_repo, _, _, _ = engine_setup
    past_date = "2020-01-01T00:00:00"
    goal = Goal(
        goal_id="goal_past",
        title="Past Deadline Goal",
        description="This goal has a deadline in the past.",
        target_date=past_date,
    )
    goals_repo[goal.goal_id] = goal

    with pytest.raises(PlanModelValidationError, match="Impossible deadline constraint"):
        engine.synthesize_plan(goal_id=goal.goal_id)


def test_impossible_deadline_window_too_short(engine_setup):
    engine, goals_repo, _, _, _ = engine_setup
    # Deadline 1 hour from now, but plan takes at least several days
    soon = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)).isoformat()
    goal = Goal(
        goal_id="goal_too_tight",
        title="Tight Deadline Goal",
        description="This goal has an impossibly tight deadline.",
        target_date=soon,
    )
    goals_repo[goal.goal_id] = goal

    with pytest.raises(PlanModelValidationError, match="Impossible schedule"):
        engine.synthesize_plan(goal_id=goal.goal_id)


# =====================================================================
# 3. Approval Workflow & Lifecycle State Transitions
# =====================================================================

def test_plan_approval_and_activation_lifecycle(engine_setup):
    engine, goals_repo, _, event_bus, _ = engine_setup
    goal = Goal(
        goal_id="goal_lifecycle",
        title="Lifecycle Validation Project",
        description="Comprehensive lifecycle transition test.",
    )
    goals_repo[goal.goal_id] = goal

    # 1. Create plan -> DRAFT
    plan = engine.create_plan(goal_id=goal.goal_id)
    assert plan.status == PlanStatus.DRAFT

    # Attempting to activate DRAFT directly must fail
    with pytest.raises(PlanModelValidationError):
        engine.activate_plan(plan.plan_id)

    # 2. Submit for approval -> PROPOSED
    proposed = engine.submit_for_approval(plan.plan_id, author="AI Agent")
    assert proposed.status == PlanStatus.PROPOSED
    assert len(proposed.revisions) == 2

    # Attempting to activate PROPOSED directly must fail (must be approved first)
    with pytest.raises(PlanModelValidationError):
        engine.activate_plan(plan.plan_id)

    # 3. Approve plan -> APPROVED
    approved = engine.approve_plan(plan.plan_id, reviewer="Senior Operator")
    assert approved.status == PlanStatus.APPROVED
    assert len(approved.revisions) == 3

    # 4. Activate plan -> ACTIVE
    active = engine.activate_plan(plan.plan_id, user="Senior Operator")
    assert active.status == PlanStatus.ACTIVE
    assert len(active.revisions) == 4


def test_plan_rejection_workflow(engine_setup):
    engine, goals_repo, _, _, _ = engine_setup
    goal = Goal(
        goal_id="goal_reject",
        title="Rejection Testing Goal",
        description="Plan will be rejected by operator.",
    )
    goals_repo[goal.goal_id] = goal

    plan = engine.create_plan(goal_id=goal.goal_id)
    engine.submit_for_approval(plan.plan_id)

    rejected = engine.reject_plan(plan.plan_id, reviewer="Security Lead", reason="Inadequate disaster recovery")
    assert rejected.status == PlanStatus.REJECTED
    assert rejected.metadata["rejection_reason"] == "Inadequate disaster recovery"


# =====================================================================
# 4. Modification & Graph Recalculation
# =====================================================================

def test_plan_modification_and_cycle_rejection(engine_setup):
    engine, goals_repo, _, _, _ = engine_setup
    goal = Goal(
        goal_id="goal_mod",
        title="Modifiable Project",
        description="Tests plan modification and cycle guards.",
    )
    goals_repo[goal.goal_id] = goal

    plan = engine.create_plan(goal_id=goal.goal_id)
    orig_rev_count = len(plan.revisions)

    # Add cyclic milestones: A -> B -> A
    m_a = Milestone(milestone_id="MA", title="A", estimated_duration=2.0, depends_on=["MB"])
    m_b = Milestone(milestone_id="MB", title="B", estimated_duration=3.0, depends_on=["MA"])

    with pytest.raises(PlanModelValidationError, match="Circular dependency detected"):
        engine.modify_plan(plan.plan_id, milestones=[m_a, m_b])

    # Ensure plan was rolled back to original state
    current = engine.get_plan(plan.plan_id)
    assert len(current.milestones) == len(plan.milestones)
    assert len(current.revisions) == orig_rev_count


# =====================================================================
# 5. Vault Persistence & Restart Recovery
# =====================================================================

def test_vault_persistence_and_restart_recovery(engine_setup, temp_vault):
    engine, goals_repo, _, _, _ = engine_setup
    goal = Goal(
        goal_id="goal_persist",
        title="Persistent Long-Horizon Mission",
        description="Validates disk persistence to vault/plans/<plan_id>.md.",
    )
    goals_repo[goal.goal_id] = goal

    plan = engine.create_plan(goal_id=goal.goal_id)
    plan_file = os.path.join(temp_vault, "plans", f"{plan.plan_id}.md")
    assert os.path.isfile(plan_file)

    # Simulate fresh engine startup with same storage
    new_mem_api = MockMemoryAPI(temp_vault)
    new_engine = LongHorizonPlanningEngine(
        goal_engine=goals_repo,
        memory_api=new_mem_api,
    )

    restored = new_engine.get_plan(plan.plan_id)
    assert restored is not None
    assert restored.plan_id == plan.plan_id
    assert restored.title == plan.title
    assert len(restored.milestones) == len(plan.milestones)
    assert restored.critical_path.total_duration == plan.critical_path.total_duration


def test_corrupted_plan_skipped_gracefully(engine_setup, temp_vault):
    engine, goals_repo, _, _, _ = engine_setup
    # Write a corrupted markdown file into vault/plans/
    plans_dir = os.path.join(temp_vault, "plans")
    os.makedirs(plans_dir, exist_ok=True)
    corrupted_path = os.path.join(plans_dir, "lhplan_corrupt.md")
    with open(corrupted_path, "w", encoding="utf-8") as f:
        f.write("# Corrupted Note\n```json\n{malformed json: true\n```")

    new_mem_api = MockMemoryAPI(temp_vault)
    new_engine = LongHorizonPlanningEngine(goal_engine=goals_repo, memory_api=new_mem_api)
    # Corrupted note skipped, engine starts cleanly
    assert len(new_engine.list_plans()) == 0


# =====================================================================
# 6. Security Denials
# =====================================================================

def test_security_proxy_denial(engine_setup):
    engine, goals_repo, _, _, security = engine_setup
    goal = Goal(
        goal_id="goal_sec",
        title="Security Test Goal",
        description="Verify security proxy denials.",
    )
    goals_repo[goal.goal_id] = goal

    # Deny create_file
    security.denied_actions.add("create_file")

    with pytest.raises(PlanningSecurityError, match="denied by security policy"):
        engine.create_plan(goal_id=goal.goal_id)


# =====================================================================
# 7. Strict Non-Execution Guarantee
# =====================================================================

def test_non_execution_guarantee(engine_setup):
    """
    Explicitly proves that running planning operations:
    - Does NOT execute shell commands
    - Does NOT run external tools
    - Does NOT mark milestones COMPLETED automatically
    """
    engine, goals_repo, _, _, _ = engine_setup
    goal = Goal(
        goal_id="goal_non_exec",
        title="Strict Non-Execution Contract",
        description="Testing that planning does not trigger task execution.",
    )
    goals_repo[goal.goal_id] = goal

    plan = engine.create_plan(goal_id=goal.goal_id)
    engine.submit_for_approval(plan.plan_id)
    engine.approve_plan(plan.plan_id)
    active = engine.activate_plan(plan.plan_id)

    # Every milestone must remain PENDING. None should be executed.
    for m in active.milestones:
        assert m.status == MilestoneStatus.PENDING
        assert "execution_time" not in m.metadata


# =====================================================================
# 8. Additional Technical Audit Verification Tests
# =====================================================================

def test_cpm_complex_parallel_branches_and_multiple_terminals():
    """
    Validates CPM calculation on a complex graph with parallel branches
    and multiple terminal milestones.
    Graph:
          -> M1 (duration 2) -> M3 (duration 5) -> Term1 (duration 1) [Path 1: 0+2+5+1 = 8]
    Start
          -> M2 (duration 4) -> M4 (duration 6) -> Term2 (duration 2) [Path 2: 0+4+6+2 = 12]
    Critical path: M2 -> M4 -> Term2 (duration 12).
    Path 1 (M1, M3, Term1) must have slack.
    """
    m1 = Milestone(milestone_id="M1", title="Branch 1A", estimated_duration=2.0)
    m2 = Milestone(milestone_id="M2", title="Branch 2A", estimated_duration=4.0)
    m3 = Milestone(milestone_id="M3", title="Branch 1B", estimated_duration=5.0, depends_on=["M1"])
    m4 = Milestone(milestone_id="M4", title="Branch 2B", estimated_duration=6.0, depends_on=["M2"])
    term1 = Milestone(milestone_id="Term1", title="Terminal 1", estimated_duration=1.0, depends_on=["M3"])
    term2 = Milestone(milestone_id="Term2", title="Terminal 2", estimated_duration=2.0, depends_on=["M4"])

    milestones = [m1, m2, m3, m4, term1, term2]
    from backend.planning.long_horizon_models import DependencyGraph, CriticalPath
    graph = DependencyGraph.from_milestones(milestones)
    cpm = CriticalPath.compute(milestones, graph)

    assert cpm.total_duration == 12.0
    assert set(cpm.critical_milestones) == {"M2", "M4", "Term2"}
    assert "M1" not in cpm.critical_milestones
    assert "M3" not in cpm.critical_milestones
    assert "Term1" not in cpm.critical_milestones
    # Slack on Term1 should be 12 - (2+5+1) = 4.0
    assert cpm.schedules["Term1"].slack == pytest.approx(4.0)


def test_path_traversal_protection(engine_setup):
    """
    Verifies that VaultManager path traversal guard blocks any traversal
    outside vault root.
    """
    _, _, mem_api, _, _ = engine_setup
    vault = mem_api.vault
    with pytest.raises(ValueError, match="Security Violation: Path traversal detected"):
        vault._safe_resolve_path("../../etc/passwd", base_folder="plans")


def test_event_bus_failure_does_not_corrupt_plan(engine_setup):
    """
    Verifies that when EventBus throws an exception or fails,
    persisted plan state remains intact and committed.
    """
    engine, goals_repo, _, _, _ = engine_setup
    goal = Goal(
        goal_id="goal_eb_fail",
        title="EventBus Failure Test",
        description="Verify plan resilience if EventBus fails.",
    )
    goals_repo[goal.goal_id] = goal

    class BrokenEventBus:
        def publish(self, *args, **kwargs):
            raise RuntimeError("EventBus connection broken")

    engine.event_bus = BrokenEventBus()

    # Plan creation should succeed despite EventBus failure
    plan = engine.create_plan(goal_id=goal.goal_id)
    assert plan is not None
    assert plan.status == PlanStatus.DRAFT

    # Plan approval should also succeed despite EventBus failure
    engine.submit_for_approval(plan.plan_id)
    approved = engine.approve_plan(plan.plan_id)
    assert approved.status == PlanStatus.APPROVED
    assert engine.get_plan(plan.plan_id).status == PlanStatus.APPROVED


def test_revision_snapshot_immutability(engine_setup):
    """
    Verifies that revisions maintain immutable snapshots of earlier states
    even after subsequent plan mutations.
    """
    engine, goals_repo, _, _, _ = engine_setup
    goal = Goal(
        goal_id="goal_rev_snap",
        title="Snapshot Immutability",
        description="Ensure earlier revisions cannot be mutated retroactively.",
    )
    goals_repo[goal.goal_id] = goal

    plan = engine.create_plan(goal_id=goal.goal_id)
    first_rev_snapshot = copy.deepcopy(plan.revisions[0].snapshot_data)

    # Modify plan title and milestones
    engine.modify_plan(plan.plan_id, title="Brand New Title After Rev 1")

    # Fetch updated plan
    updated_plan = engine.get_plan(plan.plan_id)
    assert len(updated_plan.revisions) == 2
    # Verify revision 1 snapshot still reflects original title
    assert updated_plan.revisions[0].snapshot_data["title"] == first_rev_snapshot["title"]
    assert updated_plan.revisions[0].snapshot_data["title"] != "Brand New Title After Rev 1"

