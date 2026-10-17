"""
Tests for JARVIS X Long-Horizon Planning Domain Models.
Validates validation rules, lifecycle status transitions, dependency DAGs,
critical path computations, risk matrices, resource projections, immutable revisions,
and serialization round-tripping.
"""

import copy
import datetime
import pytest
import time

from backend.planning.long_horizon_models import (
    PlanStatus,
    MilestoneStatus,
    Milestone,
    DependencyGraph,
    CriticalPath,
    MilestoneSchedule,
    ResourceEstimate,
    RiskAssessment,
    RiskSeverity,
    PlanRevision,
    LongHorizonPlan,
    PlanModelValidationError,
)


# =====================================================================
# 1. PlanStatus & Lifecycle Transitions
# =====================================================================

def test_plan_status_transitions():
    plan = LongHorizonPlan(
        plan_id="plan_test_01",
        linked_goal_id="goal_100",
        title="Infrastructure Upgrade",
        status=PlanStatus.DRAFT,
    )
    assert plan.status == PlanStatus.DRAFT

    # DRAFT -> PROPOSED (allowed)
    plan.transition_to(PlanStatus.PROPOSED)
    assert plan.status == PlanStatus.PROPOSED

    # PROPOSED -> APPROVED (allowed)
    plan.transition_to(PlanStatus.APPROVED)
    assert plan.status == PlanStatus.APPROVED

    # APPROVED -> ACTIVE (allowed)
    plan.transition_to(PlanStatus.ACTIVE)
    assert plan.status == PlanStatus.ACTIVE

    # ACTIVE -> COMPLETED (allowed)
    plan.transition_to(PlanStatus.COMPLETED)
    assert plan.status == PlanStatus.COMPLETED


def test_plan_status_illegal_transitions():
    plan = LongHorizonPlan(
        plan_id="plan_test_02",
        linked_goal_id="goal_100",
        title="Direct Activation Attempt",
        status=PlanStatus.DRAFT,
    )

    # DRAFT -> ACTIVE is prohibited (must be proposed and approved)
    with pytest.raises(PlanModelValidationError, match="DRAFT plan cannot transition directly to ACTIVE"):
        plan.transition_to(PlanStatus.ACTIVE)

    # PROPOSED -> ACTIVE is prohibited (must be approved first)
    plan.transition_to(PlanStatus.PROPOSED)
    with pytest.raises(PlanModelValidationError, match="PROPOSED plan must be APPROVED before becoming ACTIVE"):
        plan.transition_to(PlanStatus.ACTIVE)

    # PROPOSED -> COMPLETED is prohibited
    with pytest.raises(PlanModelValidationError, match="Prohibited plan status transition"):
        plan.transition_to(PlanStatus.COMPLETED)


# =====================================================================
# 2. Milestone Validation
# =====================================================================

def test_milestone_valid():
    ms = Milestone(
        milestone_id="ms_01",
        title="Database Migration",
        description="Migrate database schema to v2",
        sequence=1,
        estimated_duration=3.5,
        target_date="2026-11-01T12:00:00",
        success_criteria=["Zero data loss", "Under 10 minutes downtime"],
        depends_on=[],
        deliverables=["Migration script", "Rollback script"],
        required_capabilities=["postgres_admin", "backup_agent"],
        status=MilestoneStatus.PENDING,
    )
    assert ms.milestone_id == "ms_01"
    assert ms.estimated_duration == 3.5
    d = ms.to_dict()
    ms_restored = Milestone.from_dict(d)
    assert ms_restored.milestone_id == ms.milestone_id
    assert ms_restored.estimated_duration == 3.5


def test_milestone_invalid_fields():
    # Empty milestone_id
    with pytest.raises(PlanModelValidationError, match="milestone_id must be a non-empty string"):
        Milestone(milestone_id="", title="Valid Title")

    # Invalid characters in ID
    with pytest.raises(PlanModelValidationError, match="Invalid milestone_id format"):
        Milestone(milestone_id="ms 01 invalid!", title="Valid Title")

    # Empty title
    with pytest.raises(PlanModelValidationError, match="Milestone title must be a non-empty string"):
        Milestone(milestone_id="ms_01", title="   ")

    # Negative duration
    with pytest.raises(PlanModelValidationError, match="estimated_duration must be a positive number"):
        Milestone(milestone_id="ms_01", title="Test", estimated_duration=-1.0)

    # Zero duration
    with pytest.raises(PlanModelValidationError, match="estimated_duration must be a positive number"):
        Milestone(milestone_id="ms_01", title="Test", estimated_duration=0.0)

    # Invalid ISO date
    with pytest.raises(PlanModelValidationError, match="not a valid ISO-8601 date string"):
        Milestone(milestone_id="ms_01", title="Test", target_date="not-a-date")

    # Self-dependency
    with pytest.raises(PlanModelValidationError, match="cannot depend on itself"):
        Milestone(milestone_id="ms_01", title="Test", depends_on=["ms_01"])

    # Duplicate dependencies
    with pytest.raises(PlanModelValidationError, match="Duplicate dependencies"):
        Milestone(milestone_id="ms_01", title="Test", depends_on=["ms_02", "ms_02"])


# =====================================================================
# 3. DependencyGraph: Cycles, DAG, Topological Ordering
# =====================================================================

def test_dependency_graph_acyclic_and_topological():
    graph = DependencyGraph()
    graph.add_node("A")
    graph.add_node("B")
    graph.add_node("C")
    graph.add_node("D")

    # D depends on C, C depends on B, B depends on A
    graph.add_dependency("B", "A")
    graph.add_dependency("C", "B")
    graph.add_dependency("D", "C")

    order = graph.get_topological_order()
    assert order == ["A", "B", "C", "D"]


def test_dependency_graph_cycle_detection():
    graph = DependencyGraph()
    graph.add_dependency("A", "B")
    graph.add_dependency("B", "C")

    # C depends on A creates a cycle: A -> B -> C -> A
    with pytest.raises(PlanModelValidationError, match="Circular dependency detected"):
        graph.add_dependency("C", "A")


def test_dependency_graph_missing_dependency():
    graph = DependencyGraph()
    graph.nodes.add("A")
    graph.edges["A"] = {"MISSING_NODE"}

    with pytest.raises(PlanModelValidationError, match="Missing dependency"):
        graph.detect_cycles()


def test_dependency_graph_disconnected_nodes():
    graph = DependencyGraph()
    graph.add_node("A")
    graph.add_node("B")
    graph.add_node("ISOLATED")
    graph.add_dependency("B", "A")

    disc = graph.get_disconnected_nodes()
    assert disc == {"ISOLATED"}


# =====================================================================
# 4. Critical Path Method (CPM)
# =====================================================================

def test_critical_path_computation():
    """
    Graph structure:
    Start -> A (3 days) -> B (4 days) -> D (2 days) -> End (total: 3+4+2=9)
          -> C (2 days) --------------> D
    Critical path should be: A -> B -> D with total duration 9.
    C has duration 2, so it has slack.
    """
    m_a = Milestone(milestone_id="A", title="A", estimated_duration=3.0)
    m_b = Milestone(milestone_id="B", title="B", estimated_duration=4.0, depends_on=["A"])
    m_c = Milestone(milestone_id="C", title="C", estimated_duration=2.0)
    m_d = Milestone(milestone_id="D", title="D", estimated_duration=2.0, depends_on=["B", "C"])

    milestones = [m_a, m_b, m_c, m_d]
    graph = DependencyGraph.from_milestones(milestones)
    cpm = CriticalPath.compute(milestones, graph)

    assert cpm.total_duration == 9.0
    assert "A" in cpm.critical_milestones
    assert "B" in cpm.critical_milestones
    assert "D" in cpm.critical_milestones
    assert "C" not in cpm.critical_milestones

    # Check timing for C
    sched_c = cpm.schedules["C"]
    assert sched_c.is_critical is False
    assert sched_c.slack > 0.0
    assert sched_c.duration == 2.0


def test_critical_path_serialization_roundtrip():
    m_a = Milestone(milestone_id="M1", title="Setup", estimated_duration=5.0)
    graph = DependencyGraph.from_milestones([m_a])
    cpm = CriticalPath.compute([m_a], graph)

    d = cpm.to_dict()
    cpm_restored = CriticalPath.from_dict(d)
    assert cpm_restored.total_duration == 5.0
    assert cpm_restored.critical_milestones == ["M1"]
    assert cpm_restored.schedules["M1"].is_critical is True


# =====================================================================
# 5. ResourceEstimate & RiskAssessment Validation
# =====================================================================

def test_resource_estimate_validation():
    res = ResourceEstimate(
        required_capabilities=["python", "docker"],
        estimated_human_effort_hours=20.0,
        estimated_compute_requirements="high-memory",
        estimated_token_budget=150000,
        required_human_oversight="mandatory-per-milestone",
        assumptions=["Local GPU available"],
        confidence=0.85,
    )
    assert res.confidence == 0.85
    d = res.to_dict()
    res_restored = ResourceEstimate.from_dict(d)
    assert res_restored.estimated_token_budget == 150000

    # Negative human effort
    with pytest.raises(PlanModelValidationError, match="estimated_human_effort_hours must be a non-negative"):
        ResourceEstimate(estimated_human_effort_hours=-5)

    # Invalid confidence bounds (> 1.0)
    with pytest.raises(PlanModelValidationError, match="confidence must be between 0.0 and 1.0"):
        ResourceEstimate(confidence=1.5)


def test_risk_assessment_validation():
    risk = RiskAssessment(
        risk_id="risk_01",
        description="External API rate limiting",
        probability=0.7,
        impact=0.8,
        severity=RiskSeverity.CRITICAL,
        mitigation_strategy="Implement backoff and local cache",
        trigger_conditions=["HTTP 429 response rate > 5%"],
        residual_risk="LOW",
    )
    assert risk.severity == RiskSeverity.CRITICAL

    # Invalid probability (< 0.0)
    with pytest.raises(PlanModelValidationError, match="probability must be between 0.0 and 1.0"):
        RiskAssessment(description="Risk", probability=-0.1, mitigation_strategy="mit")

    # Invalid impact (> 1.0)
    with pytest.raises(PlanModelValidationError, match="impact must be between 0.0 and 1.0"):
        RiskAssessment(description="Risk", impact=1.2, mitigation_strategy="mit")


# =====================================================================
# 6. PlanRevision & History Snapshots
# =====================================================================

def test_plan_revision_immutability_and_monotonicity():
    rev1 = PlanRevision(
        revision_number=1,
        author="JARVIS",
        timestamp=time.time(),
        change_reason="Initial plan draft",
        previous_revision=None,
        structural_change_summary="Created 3 initial milestones",
        snapshot_data={"milestones_count": 3},
    )
    assert rev1.revision_number == 1

    # Revision number < 1 is rejected
    with pytest.raises(PlanModelValidationError, match="revision_number must be a positive integer"):
        PlanRevision(revision_number=0, change_reason="Invalid")

    # previous_revision >= revision_number is rejected
    with pytest.raises(PlanModelValidationError, match="must be strictly less than revision_number"):
        PlanRevision(revision_number=2, previous_revision=2, change_reason="Invalid")


# =====================================================================
# 7. LongHorizonPlan Aggregate Model & Deep Copy
# =====================================================================

def test_long_horizon_plan_aggregate_lifecycle_and_revisions():
    m1 = Milestone(milestone_id="M1", title="Setup Environment", estimated_duration=2.0)
    m2 = Milestone(milestone_id="M2", title="Implement Core Logic", estimated_duration=5.0, depends_on=["M1"])

    plan = LongHorizonPlan(
        plan_id="plan_strategic_01",
        linked_goal_id="goal_master_42",
        title="Complete Architecture Overhaul",
        description="Transition system to event-driven modular architecture",
        status=PlanStatus.DRAFT,
        milestones=[m1, m2],
        resource_estimates=ResourceEstimate(estimated_human_effort_hours=10.0),
        risk_assessments=[
            RiskAssessment(
                risk_id="r1",
                description="Database locking",
                probability=0.3,
                impact=0.6,
                severity=RiskSeverity.MEDIUM,
                mitigation_strategy="Read-only replicas",
            )
        ],
    )

    # Automatic dependency graph & CPM derivation
    assert plan.critical_path is not None
    assert plan.critical_path.total_duration == 7.0
    assert plan.critical_path.critical_milestones == ["M1", "M2"]

    # Create revision snapshot
    rev = plan.create_revision_snapshot(author="Architect", change_reason="Baseline approval snapshot")
    assert rev.revision_number == 1
    assert len(plan.revisions) == 1

    # Serialization roundtrip
    serialized = plan.to_dict()
    restored = LongHorizonPlan.from_dict(serialized)

    assert restored.plan_id == plan.plan_id
    assert restored.linked_goal_id == "goal_master_42"
    assert len(restored.milestones) == 2
    assert restored.critical_path.total_duration == 7.0
    assert len(restored.revisions) == 1
    assert restored.revisions[0].change_reason == "Baseline approval snapshot"


def test_long_horizon_plan_invalid_identifiers_and_duplicates():
    # Empty linked_goal_id
    with pytest.raises(PlanModelValidationError, match="linked_goal_id must be a non-empty string"):
        LongHorizonPlan(plan_id="p1", linked_goal_id="", title="Title")

    # Duplicate milestone IDs
    m1 = Milestone(milestone_id="SAME_ID", title="M1", estimated_duration=1.0)
    m2 = Milestone(milestone_id="SAME_ID", title="M2", estimated_duration=2.0)
    with pytest.raises(PlanModelValidationError, match="Duplicate milestone IDs"):
        LongHorizonPlan(
            plan_id="p1",
            linked_goal_id="g1",
            title="Title",
            milestones=[m1, m2],
        )


def test_long_horizon_plan_missing_milestone_dependency():
    m1 = Milestone(milestone_id="M1", title="M1", estimated_duration=1.0, depends_on=["DOES_NOT_EXIST"])
    with pytest.raises(PlanModelValidationError, match="depends on missing milestone"):
        LongHorizonPlan(
            plan_id="p1",
            linked_goal_id="g1",
            title="Title",
            milestones=[m1],
        )
