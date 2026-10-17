"""
Unit tests for JARVIS X Goal Manager Engine (Prompt 56 Stage 4).
"""

import pytest
import os
import shutil
import tempfile
from unittest.mock import MagicMock

from backend.goals.models import (
    Goal,
    GoalTask,
    GoalType,
    GoalStatus,
    GoalValidationError,
)
from backend.goals.decomposition import ProposedGoalPlan
from backend.goals.engine import GoalManagerEngine
from backend.memory.vault.vault_manager import VaultManager


@pytest.fixture
def temp_vault():
    temp_dir = tempfile.mkdtemp()
    vm = VaultManager(vault_root=temp_dir)
    mock_memory = MagicMock()
    mock_memory.vault = vm
    yield mock_memory, temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_crud_and_persistence(temp_vault):
    mock_memory, temp_dir = temp_vault
    engine = GoalManagerEngine(memory_api=mock_memory)

    # 1. Create Goal
    g = engine.create_goal(
        title="Develop Core Kernel",
        description="Build asynchronous kernel loop",
        goal_type=GoalType.MEDIUM_TERM,
        target_date="2026-12-31",
        completion_criteria=["All loop events processed"],
        tasks=[{"description": "Implement task queue", "completed": False}],
    )

    assert g.goal_id in engine._goals
    assert g.title == "Develop Core Kernel"
    assert g.progress == 0.0

    # Verify file was written to vault/goals/
    goal_file = os.path.join(temp_dir, "goals", f"{g.goal_id}.md")
    assert os.path.isfile(goal_file)

    # 2. Retrieve Goal
    retrieved = engine.get_goal(g.goal_id)
    assert retrieved is not None
    assert retrieved.title == "Develop Core Kernel"

    # 3. Update Goal
    engine.update_goal(g.goal_id, {"description": "Updated description", "target_date": "2027-01-15"})
    assert engine.get_goal(g.goal_id).description == "Updated description"
    assert engine.get_goal(g.goal_id).target_date == "2027-01-15"

    # 4. Engine Reinitialization / Storage Reload Test
    engine_new = GoalManagerEngine(memory_api=mock_memory)
    assert g.goal_id in engine_new._goals
    loaded = engine_new.get_goal(g.goal_id)
    assert loaded.title == "Develop Core Kernel"
    assert loaded.description == "Updated description"
    assert loaded.target_date == "2027-01-15"


def test_lifecycle_and_status_transitions():
    engine = GoalManagerEngine(memory_api=None)
    g = engine.create_goal(title="Test Lifecycle", status=GoalStatus.ACTIVE)

    # Pause
    engine.pause_goal(g.goal_id)
    assert g.status == GoalStatus.PAUSED

    # Resume
    engine.resume_goal(g.goal_id)
    assert g.status == GoalStatus.ACTIVE

    # Complete with incomplete tasks should fail without force
    g.tasks.append(GoalTask(description="Pending task", completed=False))
    with pytest.raises(GoalValidationError, match="task.*remain incomplete"):
        engine.complete_goal(g.goal_id, force=False)

    # Force complete
    engine.complete_goal(g.goal_id, force=True)
    assert g.status == GoalStatus.COMPLETED
    assert g.progress == 1.0

    # Reopening resets progress according to actual state
    engine.update_goal(g.goal_id, {"status": GoalStatus.ACTIVE})
    assert g.status == GoalStatus.ACTIVE
    assert g.progress == 0.0  # 0 of 1 tasks completed


def test_subgoal_parent_relationships():
    engine = GoalManagerEngine(memory_api=None)

    parent = engine.create_goal(title="Autonomous OS Platform")
    child1 = engine.create_goal(title="Subsystem 1", parent_goal_id=parent.goal_id)
    child2 = engine.create_goal(title="Subsystem 2")

    # Link child2 manually
    engine.add_subgoal(parent.goal_id, child2.goal_id)

    assert child1.goal_id in parent.subgoal_ids
    assert child2.goal_id in parent.subgoal_ids
    assert child2.parent_goal_id == parent.goal_id

    # Circular relationship prevention
    with pytest.raises(GoalValidationError, match="Circular goal dependency"):
        engine.add_subgoal(child1.goal_id, parent.goal_id)

    # Remove subgoal
    engine.remove_subgoal(parent.goal_id, child2.goal_id)
    assert child2.goal_id not in parent.subgoal_ids
    assert child2.parent_goal_id is None


def test_cancel_goal_preserves_children():
    engine = GoalManagerEngine(memory_api=None)
    parent = engine.create_goal(title="Parent Project")
    child = engine.create_goal(title="Child Task", parent_goal_id=parent.goal_id)

    # Cancel parent with preserve_children=True
    engine.cancel_goal(parent.goal_id, preserve_children=True)
    assert parent.status == GoalStatus.CANCELLED
    assert child.status == GoalStatus.ACTIVE
    assert child.parent_goal_id is None


def test_cancel_goal_cascades_children():
    engine = GoalManagerEngine(memory_api=None)
    parent = engine.create_goal(title="Parent Project")
    child = engine.create_goal(title="Child Task", parent_goal_id=parent.goal_id)

    engine.cancel_goal(parent.goal_id, preserve_children=False)
    assert parent.status == GoalStatus.CANCELLED
    assert child.status == GoalStatus.CANCELLED


def test_security_authorization_denied():
    mock_sec = MagicMock()
    mock_sec.is_dangerous.return_value = True
    mock_sec.request_confirmation.return_value = False  # Denied

    engine = GoalManagerEngine(memory_api=None, security_proxy=mock_sec)

    with pytest.raises(PermissionError, match="not authorized"):
        engine.create_goal(title="Dangerous Goal")


def test_save_approved_plan():
    engine = GoalManagerEngine(memory_api=None)

    root = Goal(title="Build NextGen Router")
    sub1 = Goal(title="Design Router Spec", tasks=[GoalTask(description="Draft spec")])
    sub2 = Goal(title="Implement Router", tasks=[GoalTask(description="Write code")])

    plan = ProposedGoalPlan(
        root_goal=root,
        subgoals=[sub1, sub2],
        completion_criteria=["Specs approved", "Code written"],
    )

    # Save approved plan
    saved_root = engine.save_approved_plan(plan)
    assert saved_root.status == GoalStatus.ACTIVE
    assert saved_root.goal_id in engine._goals
    assert len(saved_root.subgoal_ids) == 2
    assert sub1.goal_id in engine._goals
    assert sub2.goal_id in engine._goals
    assert sub1.status == GoalStatus.ACTIVE
    assert sub2.status == GoalStatus.ACTIVE


def test_save_plan_rejected_blocks_persistence():
    engine = GoalManagerEngine(memory_api=None)
    plan = ProposedGoalPlan(root_goal=Goal(title="Rejected Goal"))
    plan.reject(reason="No budget")

    with pytest.raises(GoalValidationError, match="Cannot persist a rejected"):
        engine.save_approved_plan(plan)


def test_save_plan_unresolved_clarifications_blocked():
    engine = GoalManagerEngine(memory_api=None)
    plan = ProposedGoalPlan(
        root_goal=Goal(title="Ambiguous Goal"),
        clarification_questions=["What is the target platform?"],
    )

    # Should raise error because clarification questions are pending
    with pytest.raises(GoalValidationError, match="clarification questions remain unresolved"):
        engine.save_approved_plan(plan, force_unresolved_clarifications=False)

    # With force=True it can proceed
    engine.save_approved_plan(plan, force_unresolved_clarifications=True)
    assert plan.root_goal.goal_id in engine._goals


def test_event_publication():
    mock_event_bus = MagicMock()
    engine = GoalManagerEngine(memory_api=None, event_bus=mock_event_bus)

    g = engine.create_goal(title="Event Test")
    engine.update_goal(g.goal_id, {"description": "Updated"})
    engine.complete_goal(g.goal_id, force=True)

    # Verify event bus was invoked
    assert mock_event_bus.publish.called


def test_hierarchy_and_summary():
    engine = GoalManagerEngine(memory_api=None)
    root = engine.create_goal(title="Root System", goal_type=GoalType.LONG_TERM)
    child1 = engine.create_goal(title="Sub 1", parent_goal_id=root.goal_id)
    child2 = engine.create_goal(title="Sub 2", parent_goal_id=root.goal_id)

    hierarchy = engine.get_goal_hierarchy(root.goal_id)
    assert len(hierarchy) == 1
    assert hierarchy[0]["goal_id"] == root.goal_id
    assert len(hierarchy[0]["subgoals"]) == 2

    summary = engine.get_active_goals_summary()
    assert summary["total_goals"] == 3
    assert summary["active_count"] == 3


def test_authorization_denied_for_all_mutation_categories():
    """Verify SecurityProxy denial prevents memory mutations and raises PermissionError for all operations."""
    mock_sec = MagicMock()
    mock_sec.is_dangerous.return_value = True
    mock_sec.request_confirmation.return_value = False  # Always deny

    engine = GoalManagerEngine(memory_api=None, security_proxy=mock_sec)

    # Allow one creation by temporarily bypassing security
    engine.security = None
    g1 = engine.create_goal(title="Goal 1")
    g2 = engine.create_goal(title="Goal 2")
    engine.security = mock_sec

    # 1. create_goal denied
    with pytest.raises(PermissionError, match="Action 'create_goal' was not authorized"):
        engine.create_goal(title="Blocked Creation")
    assert "Blocked Creation" not in [g.title for g in engine.list_goals()]

    # 2. update_goal denied
    with pytest.raises(PermissionError, match="Action 'update_goal' was not authorized"):
        engine.update_goal(g1.goal_id, {"title": "Updated Title"})
    assert engine.get_goal(g1.goal_id).title == "Goal 1"

    # 3. complete_goal denied
    with pytest.raises(PermissionError, match="Action 'complete_goal' was not authorized"):
        engine.complete_goal(g1.goal_id, force=True)
    assert engine.get_goal(g1.goal_id).status == GoalStatus.ACTIVE

    # 4. cancel_goal denied
    with pytest.raises(PermissionError, match="Action 'cancel_goal' was not authorized"):
        engine.cancel_goal(g1.goal_id)
    assert engine.get_goal(g1.goal_id).status == GoalStatus.ACTIVE

    # 5. add_subgoal denied
    with pytest.raises(PermissionError, match="Action 'add_subgoal' was not authorized"):
        engine.add_subgoal(g1.goal_id, g2.goal_id)
    assert g2.goal_id not in engine.get_goal(g1.goal_id).subgoal_ids
    assert engine.get_goal(g2.goal_id).parent_goal_id is None

    # Link them without security to test remove_subgoal
    engine.security = None
    engine.add_subgoal(g1.goal_id, g2.goal_id)
    engine.security = mock_sec

    # 6. remove_subgoal denied
    with pytest.raises(PermissionError, match="Action 'remove_subgoal' was not authorized"):
        engine.remove_subgoal(g1.goal_id, g2.goal_id)
    assert g2.goal_id in engine.get_goal(g1.goal_id).subgoal_ids

    # 7. save_approved_plan denied
    plan = ProposedGoalPlan(root_goal=Goal(title="Plan Root"))
    with pytest.raises(PermissionError, match="Action 'save_approved_plan' was not authorized"):
        engine.save_approved_plan(plan)
    assert plan.root_goal.goal_id not in engine._goals


def test_persistence_failure_rollback_and_no_events(temp_vault):
    """Verify that disk persistence failures roll back memory state and emit no success events."""
    mock_memory, temp_dir = temp_vault
    mock_event_bus = MagicMock()
    engine = GoalManagerEngine(memory_api=mock_memory, event_bus=mock_event_bus)

    # 1. Failure on create_goal
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(engine, "_persist_goal", lambda g: False)
        with pytest.raises(IOError, match="Failed to persist newly created goal"):
            engine.create_goal(title="Unpersistable Goal")
        assert len(engine._goals) == 0
        assert not mock_event_bus.publish.called

    # Create a valid goal
    g = engine.create_goal(title="Persistent Goal")
    mock_event_bus.reset_mock()

    # 2. Failure on update_goal
    orig_title = g.title
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(engine, "_persist_goal", lambda target: False)
        with pytest.raises(IOError, match="Failed to persist updated goal"):
            engine.update_goal(g.goal_id, {"title": "Failed Title Update"})
        # In-memory title must remain unchanged
        assert engine.get_goal(g.goal_id).title == orig_title
        assert not mock_event_bus.publish.called

    # 3. Failure on complete_goal
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(engine, "_persist_goal", lambda target: False)
        with pytest.raises(IOError, match="Failed to persist completed goal"):
            engine.complete_goal(g.goal_id, force=True)
        assert engine.get_goal(g.goal_id).status == GoalStatus.ACTIVE
        assert not mock_event_bus.publish.called

    # 4. Failure on cancel_goal
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(engine, "_persist_goal", lambda target: False)
        with pytest.raises(IOError, match="Failed to persist cancelled goal"):
            engine.cancel_goal(g.goal_id)
        assert engine.get_goal(g.goal_id).status == GoalStatus.ACTIVE
        assert not mock_event_bus.publish.called


def test_malformed_records_and_restart_consistency(temp_vault):
    """Verify restart loading handles malformed files gracefully and fixes parent-child reciprocal links."""
    mock_memory, temp_dir = temp_vault
    goals_dir = os.path.join(temp_dir, "goals")
    os.makedirs(goals_dir, exist_ok=True)

    # 1. Write a completely malformed corrupted markdown file
    bad_file = os.path.join(goals_dir, "corrupt_record.md")
    with open(bad_file, "w", encoding="utf-8") as f:
        f.write("# Corrupted File\n\n```json\n{ not valid json ... \n```\n")

    # 2. Write valid parent and child goals
    engine1 = GoalManagerEngine(memory_api=mock_memory)
    p = engine1.create_goal(title="Platform System")
    c = engine1.create_goal(title="Subcomponent", parent_goal_id=p.goal_id)

    # Corrupt the parent's file by stripping child from its subgoal_ids
    # (Simulate asymmetric or out-of-sync storage)
    parent_file = os.path.join(goals_dir, f"{p.goal_id}.md")
    p_dict = p.to_dict()
    p_dict["subgoal_ids"] = []  # Asymmetric: child still points to parent, but parent list is empty
    import json
    p_json = json.dumps(p_dict, indent=2)
    with open(parent_file, "w", encoding="utf-8") as f:
        f.write(f"# Goal: {p.title}\n\n```json\n{p_json}\n```\n")

    # 3. Restart engine and reload
    engine2 = GoalManagerEngine(memory_api=mock_memory)
    assert p.goal_id in engine2._goals
    assert c.goal_id in engine2._goals
    # Engine must have restored reciprocal parent-child relationship
    reloaded_parent = engine2.get_goal(p.goal_id)
    reloaded_child = engine2.get_goal(c.goal_id)
    assert c.goal_id in reloaded_parent.subgoal_ids
    assert reloaded_child.parent_goal_id == p.goal_id
