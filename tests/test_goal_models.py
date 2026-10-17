"""
Unit tests for JARVIS X Goal Domain Models & Validation (Prompt 56 Stage 2).
"""

import pytest
import time
import datetime
from backend.goals.models import (
    GoalType,
    GoalStatus,
    GoalTask,
    Goal,
    GoalValidationError,
    validate_hierarchy_acyclic,
    compute_hierarchical_progress
)


def test_goal_task_valid():
    task = GoalTask(task_id="t1", description="Configure server", completed=False)
    assert task.task_id == "t1"
    assert task.description == "Configure server"
    assert not task.completed
    assert task.completed_at is None

    # Complete task
    task.completed = True
    task.validate()
    assert task.completed_at is not None

    d = task.to_dict()
    assert d["task_id"] == "t1"
    assert d["completed"] is True

    # Reconstruct from dict
    task2 = GoalTask.from_dict(d)
    assert task2.task_id == "t1"
    assert task2.completed is True


def test_goal_task_invalid():
    with pytest.raises(GoalValidationError, match="non-empty string"):
        GoalTask(task_id="", description="Valid description")

    with pytest.raises(GoalValidationError, match="non-empty string"):
        GoalTask(task_id="t1", description="   ")

    with pytest.raises(GoalValidationError, match="boolean"):
        GoalTask(task_id="t1", description="Valid", completed="not_a_bool")


def test_goal_creation_valid():
    goal = Goal(
        goal_id="g1",
        title="Master Robotics",
        description="Learn robotics engineering",
        goal_type=GoalType.LONG_TERM,
        status=GoalStatus.ACTIVE,
        target_date="2027-12-31",
        completion_criteria=["Build autonomous robot", "Pass robotics cert"],
        progress=0.1
    )
    assert goal.goal_id == "g1"
    assert goal.title == "Master Robotics"
    assert goal.goal_type == GoalType.LONG_TERM
    assert goal.status == GoalStatus.ACTIVE
    assert goal.progress == 0.1
    assert len(goal.completion_criteria) == 2


def test_goal_string_enum_coercion():
    goal = Goal(
        goal_id="g_str",
        title="Test String Enums",
        goal_type="SHORT_TERM",
        status="PROPOSED"
    )
    assert goal.goal_type == GoalType.SHORT_TERM
    assert goal.status == GoalStatus.PROPOSED


def test_goal_invalid_enums():
    with pytest.raises(GoalValidationError, match="Invalid goal_type"):
        Goal(title="Test", goal_type="ULTRA_LONG_TERM")

    with pytest.raises(GoalValidationError, match="Invalid status"):
        Goal(title="Test", status="SUPER_ACTIVE")


def test_goal_invalid_titles():
    with pytest.raises(GoalValidationError, match="title must be a non-empty string"):
        Goal(goal_id="g1", title="")

    with pytest.raises(GoalValidationError, match="title must be a non-empty string"):
        Goal(goal_id="g1", title="   ")


def test_goal_invalid_progress():
    with pytest.raises(GoalValidationError, match="progress must be between 0.0 and 1.0"):
        Goal(title="Test", progress=-0.1)

    with pytest.raises(GoalValidationError, match="progress must be between 0.0 and 1.0"):
        Goal(title="Test", progress=1.1)

    with pytest.raises(GoalValidationError, match="progress must be a numeric value"):
        Goal(title="Test", progress="halfway")


def test_goal_invalid_target_date():
    with pytest.raises(GoalValidationError, match="not a valid ISO-8601"):
        Goal(title="Test", target_date="tomorrow")

    with pytest.raises(GoalValidationError, match="not a valid ISO-8601"):
        Goal(title="Test", target_date="31-12-2026")


def test_goal_self_parent_and_duplicate_subgoals():
    # Self parent
    with pytest.raises(GoalValidationError, match="cannot be its own parent"):
        Goal(goal_id="g1", title="Self Parent", parent_goal_id="g1")

    # Duplicate subgoals
    with pytest.raises(GoalValidationError, match="Duplicate subgoal_ids"):
        Goal(goal_id="g1", title="Dup Subgoals", subgoal_ids=["sub1", "sub1"])

    # Contains self in subgoals
    with pytest.raises(GoalValidationError, match="cannot contain itself in subgoal_ids"):
        Goal(goal_id="g1", title="Self in Subgoals", subgoal_ids=["g1"])


def test_goal_status_transitions():
    goal = Goal(goal_id="g1", title="Workflow Lifecycle", status=GoalStatus.PROPOSED)

    # PROPOSED -> ACTIVE (Allowed)
    goal.transition_to(GoalStatus.ACTIVE)
    assert goal.status == GoalStatus.ACTIVE

    # ACTIVE -> PAUSED (Allowed)
    goal.transition_to(GoalStatus.PAUSED)
    assert goal.status == GoalStatus.PAUSED

    # PAUSED -> ACTIVE (Allowed)
    goal.transition_to(GoalStatus.ACTIVE)
    assert goal.status == GoalStatus.ACTIVE

    # ACTIVE -> CANCELLED (Allowed)
    goal.transition_to(GoalStatus.CANCELLED)
    assert goal.status == GoalStatus.CANCELLED

    # CANCELLED -> COMPLETED (PROHIBITED)
    with pytest.raises(GoalValidationError, match="cannot transition directly from CANCELLED to COMPLETED"):
        goal.transition_to(GoalStatus.COMPLETED)

    # CANCELLED -> PROPOSED (Allowed)
    goal.transition_to(GoalStatus.PROPOSED)
    assert goal.status == GoalStatus.PROPOSED


def test_goal_serialization_roundtrip():
    t1 = GoalTask(task_id="t1", description="Step 1", completed=True)
    t2 = GoalTask(task_id="t2", description="Step 2", completed=False)
    goal = Goal(
        goal_id="g_main",
        title="Complete Project",
        description="Ship version 1.0",
        goal_type=GoalType.MEDIUM_TERM,
        status=GoalStatus.ACTIVE,
        subgoal_ids=["sub1", "sub2"],
        tasks=[t1, t2],
        target_date="2026-11-15T18:00:00",
        completion_criteria=["Criterion 1", "Criterion 2"],
        metadata={"priority": "high", "department": "engineering"},
        progress=0.5
    )

    d = goal.to_dict()
    assert d["goal_id"] == "g_main"
    assert d["goal_type"] == "MEDIUM_TERM"
    assert d["status"] == "ACTIVE"
    assert len(d["tasks"]) == 2
    assert d["tasks"][0]["completed"] is True

    # Reconstruct from dictionary
    reconstructed = Goal.from_dict(d)
    assert reconstructed.goal_id == goal.goal_id
    assert reconstructed.title == goal.title
    assert reconstructed.goal_type == GoalType.MEDIUM_TERM
    assert reconstructed.status == GoalStatus.ACTIVE
    assert len(reconstructed.tasks) == 2
    assert reconstructed.tasks[0].task_id == "t1"
    assert reconstructed.tasks[0].completed is True
    assert reconstructed.subgoal_ids == ["sub1", "sub2"]
    assert reconstructed.metadata["department"] == "engineering"


def test_hierarchy_acyclic_valid():
    g_root = Goal(goal_id="root", title="Root Goal", subgoal_ids=["child1", "child2"])
    g_c1 = Goal(goal_id="child1", title="Child 1", parent_goal_id="root", subgoal_ids=["grandchild1"])
    g_c2 = Goal(goal_id="child2", title="Child 2", parent_goal_id="root")
    g_gc1 = Goal(goal_id="grandchild1", title="Grandchild 1", parent_goal_id="child1")

    goals = {
        "root": g_root,
        "child1": g_c1,
        "child2": g_c2,
        "grandchild1": g_gc1
    }

    # Should pass without error
    validate_hierarchy_acyclic(goals)


def test_hierarchy_cycle_detection():
    # Direct cycle: A -> B -> A
    ga = Goal(goal_id="A", title="A", subgoal_ids=["B"])
    gb = Goal(goal_id="B", title="B", subgoal_ids=["A"])

    with pytest.raises(GoalValidationError, match="Circular goal dependency"):
        validate_hierarchy_acyclic({"A": ga, "B": gb})

    # Indirect cycle: A -> B -> C -> A
    ga = Goal(goal_id="A", title="A", subgoal_ids=["B"])
    gb = Goal(goal_id="B", title="B", subgoal_ids=["C"])
    gc = Goal(goal_id="C", title="C", subgoal_ids=["A"])

    with pytest.raises(GoalValidationError, match="Circular goal dependency"):
        validate_hierarchy_acyclic({"A": ga, "B": gb, "C": gc})


def test_hierarchy_inconsistent_parent_pointer():
    ga = Goal(goal_id="A", title="A", subgoal_ids=["B"])
    gb = Goal(goal_id="B", title="B", parent_goal_id="OTHER")

    with pytest.raises(GoalValidationError, match="Inconsistent hierarchy"):
        validate_hierarchy_acyclic({"A": ga, "B": gb, "OTHER": Goal(goal_id="OTHER", title="Other")})


def test_progress_calculation():
    # 1. Empty goal (no tasks, no subgoals) -> 0.0
    g_empty = Goal(goal_id="empty", title="Empty Goal")
    goals = {"empty": g_empty}
    assert compute_hierarchical_progress("empty", goals) == 0.0

    # 2. Tasks only
    t1 = GoalTask(task_id="t1", description="Task 1", completed=True)
    t2 = GoalTask(task_id="t2", description="Task 2", completed=False)
    g_tasks = Goal(goal_id="gt", title="Tasks Goal", tasks=[t1, t2])
    goals["gt"] = g_tasks
    assert compute_hierarchical_progress("gt", goals) == 0.5

    # 3. Subgoals only
    # child 1: 100% (2 of 2 tasks)
    c1 = Goal(
        goal_id="c1",
        title="Child 1",
        parent_goal_id="parent_sub",
        tasks=[GoalTask(task_id="c1_t1", description="c1", completed=True), GoalTask(task_id="c1_t2", description="c2", completed=True)]
    )
    # child 2: 50% (1 of 2 tasks)
    c2 = Goal(
        goal_id="c2",
        title="Child 2",
        parent_goal_id="parent_sub",
        tasks=[GoalTask(task_id="c2_t1", description="c1", completed=True), GoalTask(task_id="c2_t2", description="c2", completed=False)]
    )
    g_parent = Goal(goal_id="parent_sub", title="Parent", subgoal_ids=["c1", "c2"])
    goals.update({"c1": c1, "c2": c2, "parent_sub": g_parent})

    # Average of c1 (1.0) and c2 (0.5) is 0.75
    assert compute_hierarchical_progress("parent_sub", goals) == 0.75

    # 4. Mixed tasks & subgoals (50% tasks weight, 50% subgoals weight)
    # Add 1 completed of 1 task directly to parent (task_progress = 1.0)
    g_parent.tasks = [GoalTask(task_id="pt1", description="Parent task", completed=True)]
    # final = 0.5 * 1.0 + 0.5 * 0.75 = 0.5 + 0.375 = 0.875
    assert compute_hierarchical_progress("parent_sub", goals) == 0.875
