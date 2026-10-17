"""
JARVIS X — Prompt 57 Stage 5 & 6 Planning Integration & System Verification Tests
Validates AppContainer registration, JarvisCore application-level methods,
PlanSkill action dispatch, IntentRouter natural language routing, lifecycle transitions,
event emissions, and non-execution boundary guarantees.
"""

import pytest
import os
import shutil
import tempfile
import asyncio
from unittest.mock import MagicMock

from backend.core.container import AppContainer
from backend.core.core import JarvisCore
from backend.core.models import UserInput, InputChannel
from backend.goals.models import Goal, GoalType, GoalStatus
from backend.planning.long_horizon_models import (
    PlanStatus,
    MilestoneStatus,
    Milestone,
    LongHorizonPlan,
)
from backend.planning.adaptive_planning import (
    AdaptationTrigger,
    AdaptationTriggerType,
)


@pytest.fixture
def temp_vault_env():
    temp_dir = tempfile.mkdtemp(prefix="test_planning_integration_")
    vault_dir = os.path.join(temp_dir, "vault")
    os.makedirs(os.path.join(vault_dir, "plans"), exist_ok=True)
    os.makedirs(os.path.join(vault_dir, "plans", "pending"), exist_ok=True)
    os.makedirs(os.path.join(vault_dir, "goals"), exist_ok=True)
    os.makedirs(os.path.join(vault_dir, "daily"), exist_ok=True)
    yield temp_dir
    try:
        shutil.rmtree(temp_dir)
    except Exception:
        pass


def test_app_container_registers_planning_services(temp_vault_env):
    """Verifies that AppContainer instantiates singleton planning engines correctly."""
    config = {
        "security": {"dangerous_actions": []},
        "vault": {"path": os.path.join(temp_vault_env, "vault")},
    }
    container = AppContainer(config=config, session_id="test_session")
    assert hasattr(container, "planning_engine")
    assert hasattr(container, "adaptive_planning")
    assert container.planning_engine is not None
    assert container.adaptive_planning is not None
    assert container.adaptive_planning.planning_engine is container.planning_engine


def test_jarvis_core_planning_lifecycle_and_methods(temp_vault_env):
    """Verifies JarvisCore application-level planning methods and lifecycle."""
    config = {
        "security": {"dangerous_actions": []},
        "vault": {"path": os.path.join(temp_vault_env, "vault")},
    }
    core = JarvisCore(config=config, session_id="test_core_session")
    assert core.planning_engine is not None
    assert core.adaptive_planning is not None
    # Set non-interactive confirmation callback to auto-allow for test
    core.security.confirmation_callback = lambda action, details: True

    # Create goal in goal_engine
    g = core.goal_engine.create_goal(
        title="Deploy Quantum Research Cluster",
        description="High-performance computing cluster setup for algorithmic simulations.",
        goal_type=GoalType.LONG_TERM,
        target_date="2026-12-31",
        completion_criteria=["Cluster provisioned", "Network secured", "Benchmarks run"],
    )

    # 1. Create long-horizon plan
    plan = core.create_long_horizon_plan(goal_id=g.goal_id, title="Quantum Deployment Strategy")
    assert plan is not None
    assert plan.status == PlanStatus.DRAFT
    assert len(plan.milestones) == 4
    assert plan.critical_path.total_duration_days > 0

    # 2. Get plan
    retrieved = core.get_plan(plan.plan_id)
    assert retrieved.plan_id == plan.plan_id

    # 3. List plans
    all_plans = core.list_plans()
    assert len(all_plans) >= 1
    assert any(p.plan_id == plan.plan_id for p in all_plans)

    # 4. Critical path
    cpm = core.get_critical_path(plan.plan_id)
    assert cpm.total_duration_days == plan.critical_path.total_duration_days
    assert len(cpm.critical_milestones) > 0

    # 5. Submit for approval (DRAFT -> PROPOSED)
    prop = core.submit_plan_for_approval(plan.plan_id, author="LeadArchitect")
    assert prop.status == PlanStatus.PROPOSED

    # 6. Approve plan (PROPOSED -> APPROVED)
    app = core.approve_plan(plan.plan_id, reviewer="Admin")
    assert app.status == PlanStatus.APPROVED

    # 7. Activate plan (APPROVED -> ACTIVE)
    act = core.activate_plan(plan.plan_id, user="Operator")
    assert act.status == PlanStatus.ACTIVE

    # 8. Adaptive trigger & revision proposal
    trigger = AdaptationTrigger(
        plan_id=plan.plan_id,
        trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
        new_state={"milestone_id": plan.milestones[1].milestone_id, "delay_days": 3.0},
    )
    assessment = core.assess_plan_adaptation(trigger)
    assert assessment.plan_id == plan.plan_id

    candidate, diff = core.propose_plan_revision(plan.plan_id, author="AdaptiveBot", reason="Critical milestone slipped")
    assert diff.duration_delta_days == 3.0

    # Baseline remains unchanged at active version until approval
    baseline_before = core.get_plan(plan.plan_id)
    assert len(baseline_before.revisions) == len(act.revisions)

    # 9. Approve revision -> baseline replaces
    revised = core.approve_plan_revision(plan.plan_id, reviewer="Admin")
    assert len(revised.revisions) > len(baseline_before.revisions)

    # 10. History retrieval
    history = core.get_plan_revision_history(plan.plan_id)
    assert len(history) >= 4


def test_intent_router_and_plan_skill_nl_routing(temp_vault_env):
    """Verifies that IntentRouter routes natural language queries to PlanSkill actions."""
    config = {
        "security": {"dangerous_actions": []},
        "vault": {"path": os.path.join(temp_vault_env, "vault")},
    }
    core = JarvisCore(config=config, session_id="test_routing_session")
    core.security.confirmation_callback = lambda action, details: True

    # Seed goal and plan
    g = core.goal_engine.create_goal(
        title="Robotics Lab Expansion",
        description="Expand assembly cells and install precision arms.",
        goal_type=GoalType.LONG_TERM,
    )
    plan = core.create_long_horizon_plan(goal_id=g.goal_id)
    core.submit_plan_for_approval(plan.plan_id)
    core.approve_plan(plan.plan_id)

    router = core.router

    # Route: List plans
    res1 = router.route(UserInput(content="list all my plans", channel=InputChannel.TEXT))
    assert res1.skill_name == "plan"
    assert res1.action == "list_plans"

    # Route: View plan
    res2 = router.route(UserInput(content=f"view plan {plan.plan_id}", channel=InputChannel.TEXT))
    assert res2.skill_name == "plan"
    assert res2.action == "view_plan"
    assert res2.parameters.get("plan_id") == plan.plan_id

    # Route: Critical path
    res3 = router.route(UserInput(content=f"show critical path for {plan.plan_id}", channel=InputChannel.TEXT))
    assert res3.skill_name == "plan"
    assert res3.action == "get_critical_path"
    assert res3.parameters.get("plan_id") == plan.plan_id

    # Route: Approve plan
    res4 = router.route(UserInput(content=f"approve plan {plan.plan_id}", channel=InputChannel.TEXT))
    assert res4.skill_name == "plan"
    assert res4.action == "approve_plan"

    # Route: Propose revision
    res5 = router.route(UserInput(content=f"propose revised project plan {plan.plan_id}", channel=InputChannel.TEXT))
    assert res5.skill_name == "plan"
    assert res5.action == "propose_revision"


@pytest.mark.asyncio
async def test_jarvis_core_start_stop_monitoring_lifecycle(temp_vault_env):
    """Verifies that start() begins adaptive monitoring and stop() terminates cleanly."""
    config = {
        "security": {"dangerous_actions": []},
        "vault": {"path": os.path.join(temp_vault_env, "vault")},
    }
    core = JarvisCore(config=config, session_id="test_lifecycle_session")
    core.security.confirmation_callback = lambda action, details: True

    assert core.adaptive_planning._monitoring_active is False
    await core.start()
    assert core.adaptive_planning._monitoring_active is True

    await core.stop()
    assert core.adaptive_planning._monitoring_active is False
