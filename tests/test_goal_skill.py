"""
Integration tests for JARVIS X GoalSkill and Core Subsystem Integration (Prompt 57 Stage 5).
"""

import os
import shutil
import tempfile
import pytest
from unittest.mock import MagicMock

from backend.core.models import UserInput, Intent, SkillResult, InputChannel
from backend.core.container import AppContainer
from backend.core.core import JarvisCore
from backend.goals.models import Goal, GoalTask, GoalType, GoalStatus, GoalValidationError
from backend.goals.engine import GoalManagerEngine
from backend.goals.decomposition import GoalDecompositionEngine, ProposedGoalPlan
from backend.skills.goal_skill import GoalSkill
from backend.skills.registry import SkillRegistry
from backend.router.intent_router import IntentRouter
from backend.memory.vault.vault_manager import VaultManager


@pytest.fixture
def temp_environment():
    temp_dir = tempfile.mkdtemp()
    vm = VaultManager(vault_root=temp_dir)
    mock_memory = MagicMock()
    mock_memory.vault = vm
    mock_memory.retrieve_context.return_value = []

    mock_sec = MagicMock()
    mock_sec.is_dangerous.return_value = False

    engine = GoalManagerEngine(memory_api=mock_memory, security_proxy=mock_sec)
    decomp = GoalDecompositionEngine(llm_client=None)
    skill = GoalSkill(engine=engine, decomposition_engine=decomp)

    yield engine, decomp, skill, temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_goal_skill_metadata(temp_environment):
    _, _, skill, _ = temp_environment
    assert skill.name == "goal"
    assert "create_goal" in skill.supported_actions
    assert "decompose_goal" in skill.supported_actions
    assert "approve_plan" in skill.supported_actions
    assert "list_active_goals" in skill.supported_actions
    assert "check_progress" in skill.supported_actions


def test_goal_creation_and_listing(temp_environment):
    engine, _, skill, _ = temp_environment

    # 1. Create goal via skill
    intent = Intent(
        intent_type="goal",
        skill_name="goal",
        action="create_goal",
        parameters={"title": "Build Autonomous AI OS", "target_date": "2026-12-31"}
    )
    res = skill.execute(intent)
    assert res.success is True
    assert "created successfully" in res.message
    created_id = res.data["goal"]["goal_id"]
    assert created_id in engine._goals

    # 2. List all goals
    list_res = skill.execute(Intent(intent_type="goal", skill_name="goal", action="list_goals"))
    assert list_res.success is True
    assert len(list_res.data["goals"]) == 1
    assert list_res.data["goals"][0]["title"] == "Build Autonomous AI OS"

    # 3. List active goals
    active_res = skill.execute(Intent(intent_type="goal", skill_name="goal", action="list_active_goals"))
    assert active_res.success is True
    assert len(active_res.data["goals"]) == 1


def test_goal_decomposition_and_approval_workflow(temp_environment):
    engine, _, skill, _ = temp_environment

    # Create root goal
    g = engine.create_goal(title="Launch Space Platform")

    # 1. Decompose goal via skill
    decomp_intent = Intent(
        intent_type="goal",
        skill_name="goal",
        action="decompose_goal",
        parameters={"goal_id": g.goal_id}
    )
    decomp_res = skill.execute(decomp_intent)
    assert decomp_res.success is True
    plan_id = decomp_res.data["plan_id"]
    assert plan_id in skill._pending_plans

    # Verify root goal has NOT yet been modified in engine (tasks not auto-executed or approved)
    assert len(engine.get_goal(g.goal_id).subgoal_ids) == 0

    # 2. Approve proposed plan
    approve_intent = Intent(
        intent_type="goal",
        skill_name="goal",
        action="approve_plan",
        parameters={"plan_id": plan_id}
    )
    approve_res = skill.execute(approve_intent)
    assert approve_res.success is True
    assert plan_id not in skill._pending_plans
    saved_root_id = approve_res.data["root_goal"]["goal_id"]
    assert saved_root_id in engine._goals
    assert len(engine.get_goal(saved_root_id).subgoal_ids) > 0


def test_unresolved_clarifications_blocks_approval(temp_environment):
    engine, _, skill, _ = temp_environment

    plan = ProposedGoalPlan(
        root_goal=Goal(title="Ambiguous Architecture"),
        clarification_questions=["What backend architecture should be used?"]
    )
    skill._pending_plans[plan.plan_id] = plan

    # Approval should be blocked
    approve_res = skill.execute(Intent(
        intent_type="goal",
        skill_name="goal",
        action="approve_plan",
        parameters={"plan_id": plan.plan_id, "force": False}
    ))
    assert approve_res.success is False
    assert "clarification questions remain unresolved" in approve_res.message
    assert plan.root_goal.goal_id not in engine._goals


def test_progress_and_hierarchy_views(temp_environment):
    engine, _, skill, _ = temp_environment

    parent = engine.create_goal(title="System Kernel")
    child = engine.create_goal(
        title="Async EventBus",
        parent_goal_id=parent.goal_id,
        tasks=[{"description": "Implement pubsub", "completed": True}]
    )

    # 1. View hierarchy
    hier_res = skill.execute(Intent(
        intent_type="goal",
        skill_name="goal",
        action="view_goal_hierarchy",
        parameters={"root_goal_id": parent.goal_id}
    ))
    assert hier_res.success is True
    assert len(hier_res.data["hierarchy"]) == 1
    assert len(hier_res.data["hierarchy"][0]["subgoals"]) == 1

    # 2. Check progress
    prog_res = skill.execute(Intent(
        intent_type="goal",
        skill_name="goal",
        action="check_progress",
        parameters={"goal_id": parent.goal_id}
    ))
    assert prog_res.success is True
    assert prog_res.data["percentage"] == 100.0

    # Ensure 100% progress does NOT automatically mark the goal as COMPLETED
    parent_ref = engine.get_goal(parent.goal_id)
    assert parent_ref.status == GoalStatus.ACTIVE


def test_pause_resume_complete_cancel_lifecycle(temp_environment):
    engine, _, skill, _ = temp_environment

    g = engine.create_goal(title="Lifecycle Target")

    # 1. Pause
    pause_res = skill.execute(Intent(intent_type="goal", skill_name="goal", action="pause_goal", parameters={"id": g.goal_id}))
    assert pause_res.success is True
    assert engine.get_goal(g.goal_id).status == GoalStatus.PAUSED

    # 2. Resume
    resume_res = skill.execute(Intent(intent_type="goal", skill_name="goal", action="resume_goal", parameters={"id": g.goal_id}))
    assert resume_res.success is True
    assert engine.get_goal(g.goal_id).status == GoalStatus.ACTIVE

    # 3. Complete (with force=True since no tasks)
    comp_res = skill.execute(Intent(intent_type="goal", skill_name="goal", action="complete_goal", parameters={"id": g.goal_id, "force": True}))
    assert comp_res.success is True
    assert engine.get_goal(g.goal_id).status == GoalStatus.COMPLETED

    # 4. Cancel a second active goal (since COMPLETED is terminal to CANCELLED)
    g2 = engine.create_goal(title="Cancel Target")
    cancel_res = skill.execute(Intent(intent_type="goal", skill_name="goal", action="cancel_goal", parameters={"id": g2.goal_id}))
    assert cancel_res.success is True
    assert engine.get_goal(g2.goal_id).status == GoalStatus.CANCELLED


def test_missing_identifiers_and_ambiguity(temp_environment):
    _, _, skill, _ = temp_environment

    # Missing title on creation
    res1 = skill.execute(Intent(intent_type="goal", skill_name="goal", action="create_goal", parameters={}))
    assert res1.success is False
    assert "Missing required input: title" in res1.message

    # Non-existent goal ID on pause
    res2 = skill.execute(Intent(intent_type="goal", skill_name="goal", action="pause_goal", parameters={"id": "goal_nonexistent"}))
    assert res2.success is False
    assert "Could not find" in res2.output_text


def test_security_authorization_denial(temp_environment):
    engine, _, skill, _ = temp_environment

    mock_sec = MagicMock()
    mock_sec.is_dangerous.return_value = True
    mock_sec.request_confirmation.return_value = False  # Denied
    engine.security = mock_sec

    # Try creating goal
    res = skill.execute(Intent(
        intent_type="goal",
        skill_name="goal",
        action="create_goal",
        parameters={"title": "Exploit Kernel"}
    ))
    assert res.success is False
    assert "Permission Denied" in res.output_text
    assert len(engine.list_goals()) == 0


def test_intent_routing_patterns():
    router = IntentRouter()

    # 1. Create goal
    i1 = router.route(UserInput(content="Create a goal to build my autonomous AI operating system."))
    assert i1.skill_name == "goal"
    assert i1.action == "create_goal"
    assert "autonomous AI operating system" in i1.parameters.get("title", "")

    # 2. Decompose goal
    i2 = router.route(UserInput(content="Break this goal into smaller tasks."))
    assert i2.skill_name == "goal"
    assert i2.action == "decompose_goal"

    # 3. Active goals
    i3 = router.route(UserInput(content="Show my active goals."))
    assert i3.skill_name == "goal"
    assert i3.action == "list_active_goals"

    # 4. Progress check
    i4 = router.route(UserInput(content="What is my progress on the JARVIS project?"))
    assert i4.skill_name == "goal"
    assert i4.action == "check_progress"
    assert "JARVIS project" in i4.parameters.get("title", "")

    # 5. Pause goal
    i5 = router.route(UserInput(content="Pause goal goal_abc123"))
    assert i5.skill_name == "goal"
    assert i5.action == "pause_goal"
    assert i5.parameters.get("goal_id") == "goal_abc123"

    # 6. Resume goal
    i6 = router.route(UserInput(content="Resume goal goal_abc123"))
    assert i6.skill_name == "goal"
    assert i6.action == "resume_goal"
    assert i6.parameters.get("goal_id") == "goal_abc123"

    # 7. Complete goal
    i7 = router.route(UserInput(content="Mark goal goal_abc123 as completed."))
    assert i7.skill_name == "goal"
    assert i7.action == "complete_goal"
    assert i7.parameters.get("goal_id") == "goal_abc123"

    # 8. Cancel goal
    i8 = router.route(UserInput(content="Cancel goal goal_abc123"))
    assert i8.skill_name == "goal"
    assert i8.action == "cancel_goal"
    assert i8.parameters.get("goal_id") == "goal_abc123"


def test_app_container_and_jarvis_core_di():
    config = {
        "memory": {"storage_type": "in_memory"},
        "llm": {"provider": "mock"},
        "security": {"enforce_permissions": False}
    }

    # 1. Container DI test
    container = AppContainer(config=config)
    assert hasattr(container, "goal_engine")
    assert hasattr(container, "goal_decomposition_engine")
    assert isinstance(container.goal_engine, GoalManagerEngine)
    assert isinstance(container.goal_decomposition_engine, GoalDecompositionEngine)

    # 2. JarvisCore integration test
    core = JarvisCore(config=config)
    assert hasattr(core, "goal_engine")
    assert hasattr(core, "goal_decomposition_engine")
    assert core.goal_engine is container.goal_engine or isinstance(core.goal_engine, GoalManagerEngine)

    # Verify GoalSkill is registered exactly once
    goal_skill = core.skill_registry.get_skill("goal")
    assert goal_skill is not None
    assert isinstance(goal_skill, GoalSkill)
    assert goal_skill.engine is core.goal_engine
    # Ensure no duplicate registration in registry
    registered_count = sum(1 for s in core.skill_registry._skills.values() if s.name.lower() == "goal")
    assert registered_count == 1


def test_proposal_rejection_does_not_persist(temp_environment):
    engine, _, skill, _ = temp_environment

    plan = ProposedGoalPlan(
        root_goal=Goal(title="Proposal Rejection Test"),
        subgoals=[Goal(title="Draft Subgoal", tasks=[GoalTask(description="Draft task")])]
    )
    skill._pending_plans[plan.plan_id] = plan

    reject_res = skill.execute(Intent(
        intent_type="goal",
        skill_name="goal",
        action="reject_plan",
        parameters={"plan_id": plan.plan_id, "reason": "Not feasible right now"}
    ))
    assert reject_res.success is True
    assert plan.plan_id not in skill._pending_plans
    assert plan.root_goal.goal_id not in engine._goals
    assert len(engine.list_goals()) == 0


def test_ambiguous_and_missing_input_does_not_mutate_state(temp_environment):
    engine, _, skill, _ = temp_environment

    g = engine.create_goal(title="Existing Untouched Goal")
    initial_goal = engine.get_goal(g.goal_id)

    # 1. Update with invalid/missing identifier
    res1 = skill.execute(Intent(
        intent_type="goal",
        skill_name="goal",
        action="update_goal",
        parameters={"title": "New Title Without Valid ID"}
    ))
    assert res1.success is False

    # 2. Complete with missing identifier
    res2 = skill.execute(Intent(
        intent_type="goal",
        skill_name="goal",
        action="complete_goal",
        parameters={}
    ))
    assert res2.success is False

    # 3. Pause with nonexistent identifier
    res3 = skill.execute(Intent(
        intent_type="goal",
        skill_name="goal",
        action="pause_goal",
        parameters={"goal_id": "non_existent_id"}
    ))
    assert res3.success is False

    # Assert existing goal was completely unchanged
    post_goal = engine.get_goal(g.goal_id)
    assert post_goal.title == initial_goal.title
    assert post_goal.status == initial_goal.status
    assert post_goal.updated_at == initial_goal.updated_at
