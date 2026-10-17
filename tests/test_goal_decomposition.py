"""
Unit tests for JARVIS X Goal Decomposition Engine (Prompt 56 Stage 3).
"""

import pytest
import json
from unittest.mock import MagicMock
from backend.goals.models import GoalType, GoalStatus, GoalValidationError
from backend.goals.decomposition import GoalDecompositionEngine, ProposedGoalPlan


@pytest.mark.asyncio
async def test_fallback_decomposition_build():
    engine = GoalDecompositionEngine(llm_client=None)
    plan = await engine.decompose_goal(
        title="Build an autonomous personal AI assistant",
        description="A full-featured operating layer on Windows with voice and vision.",
    )
    assert isinstance(plan, ProposedGoalPlan)
    assert plan.source == "fallback"
    assert plan.approved is None
    assert plan.root_goal.status == GoalStatus.PROPOSED
    assert len(plan.subgoals) >= 2
    assert plan.root_goal.goal_type == GoalType.LONG_TERM

    # Check subgoals wiring
    for sg in plan.subgoals:
        assert sg.parent_goal_id == plan.root_goal.goal_id
        assert sg.status == GoalStatus.PROPOSED
        assert len(sg.tasks) > 0
        for task in sg.tasks:
            assert task.description
            assert not task.completed

    assert plan.root_goal.subgoal_ids == [sg.goal_id for sg in plan.subgoals]


@pytest.mark.asyncio
async def test_fallback_decomposition_learn():
    engine = GoalDecompositionEngine(llm_client=None)
    plan = await engine.decompose_goal(
        title="Learn Quantum Computing",
        description="Study qubits, gates, and algorithms.",
    )
    assert plan.source == "fallback"
    assert plan.root_goal.status == GoalStatus.PROPOSED
    assert any("Research" in sg.title or "study" in sg.title.lower() for sg in plan.subgoals)


@pytest.mark.asyncio
async def test_mocked_llm_decomposition_success():
    mock_llm = MagicMock()
    llm_payload = {
        "goal_type": "LONG_TERM",
        "completion_criteria": [
            "Complete core microservices architecture",
            "Deploy to cluster with monitoring",
        ],
        "assumptions": ["Python 3.13 environment available"],
        "ambiguities": [],
        "clarification_questions": [],
        "subgoals": [
            {
                "title": "Phase 1: Architecture Design",
                "description": "Formulate interface schemas and protocols.",
                "goal_type": "MEDIUM_TERM",
                "completion_criteria": ["Architecture document published"],
                "tasks": [
                    {"description": "Design communication protocol", "assigned_skill": "plan"},
                    {"description": "Draft data schema specifications", "assigned_skill": "coding"},
                ],
            },
            {
                "title": "Phase 2: Service Implementation",
                "description": "Build individual components.",
                "goal_type": "MEDIUM_TERM",
                "completion_criteria": ["All service unit tests pass"],
                "tasks": [
                    {"description": "Implement authentication service", "assigned_skill": "coding"},
                    {"description": "Implement routing gateway", "assigned_skill": "coding"},
                ],
            },
        ],
    }
    mock_llm.chat_sync.return_value = json.dumps(llm_payload)

    engine = GoalDecompositionEngine(llm_client=mock_llm)
    plan = await engine.decompose_goal(
        title="Enterprise Microservices Platform",
        description="High throughput event processing platform.",
    )

    assert plan.source == "llm"
    assert plan.root_goal.goal_type == GoalType.LONG_TERM
    assert len(plan.subgoals) == 2
    assert plan.subgoals[0].title == "Phase 1: Architecture Design"
    assert len(plan.subgoals[0].tasks) == 2
    assert plan.subgoals[0].tasks[0].assigned_skill == "plan"


@pytest.mark.asyncio
async def test_llm_markdown_fence_handling():
    mock_llm = MagicMock()
    llm_payload = {
        "goal_type": "SHORT_TERM",
        "completion_criteria": ["Clean workspace"],
        "subgoals": [
            {
                "title": "Clean temp files",
                "description": "Delete logs and cache",
                "tasks": [{"description": "Remove logs folder", "assigned_skill": "system"}],
            }
        ],
    }
    # Wrap in markdown fences
    mock_llm.chat_sync.return_value = f"```json\n{json.dumps(llm_payload)}\n```"

    engine = GoalDecompositionEngine(llm_client=mock_llm)
    plan = await engine.decompose_goal(title="Clean Workspace")
    assert plan.source == "llm"
    assert len(plan.subgoals) == 1
    assert plan.subgoals[0].title == "Clean temp files"


@pytest.mark.asyncio
async def test_llm_malformed_json_triggers_fallback():
    mock_llm = MagicMock()
    mock_llm.chat_sync.return_value = "This is not JSON at all: { broken json ..."

    engine = GoalDecompositionEngine(llm_client=mock_llm)
    plan = await engine.decompose_goal(title="Build NextGen Router")

    # Should gracefully revert to fallback without crashing
    assert plan.source == "fallback"
    assert plan.root_goal.status == GoalStatus.PROPOSED
    assert len(plan.subgoals) >= 2


@pytest.mark.asyncio
async def test_llm_exception_triggers_fallback():
    mock_llm = MagicMock()
    mock_llm.chat_sync.side_effect = TimeoutError("Provider request timed out.")

    engine = GoalDecompositionEngine(llm_client=mock_llm)
    plan = await engine.decompose_goal(title="Deploy AI Model")

    assert plan.source == "fallback"
    assert plan.root_goal.title == "Deploy AI Model"


@pytest.mark.asyncio
async def test_empty_title_validation_error():
    engine = GoalDecompositionEngine(llm_client=None)
    with pytest.raises(GoalValidationError, match="title is empty"):
        await engine.decompose_goal(title="")


@pytest.mark.asyncio
async def test_ambiguity_and_clarification_detection():
    engine = GoalDecompositionEngine(llm_client=None)
    # Extremely brief title with no description
    plan = await engine.decompose_goal(title="Learn AI")
    assert len(plan.ambiguities) > 0
    assert len(plan.clarification_questions) > 0


@pytest.mark.asyncio
async def test_approval_and_rejection_workflows():
    engine = GoalDecompositionEngine(llm_client=None)
    plan = await engine.decompose_goal(title="Build Portfolio Website")

    assert plan.approved is None
    assert plan.root_goal.status == GoalStatus.PROPOSED
    assert all(sg.status == GoalStatus.PROPOSED for sg in plan.subgoals)

    # Approve
    plan.approve()
    assert plan.approved is True
    assert plan.reviewed_at is not None
    assert plan.root_goal.status == GoalStatus.ACTIVE
    assert all(sg.status == GoalStatus.ACTIVE for sg in plan.subgoals)

    # Reject
    plan.reject(reason="Out of scope for this quarter")
    assert plan.approved is False
    assert plan.root_goal.status == GoalStatus.CANCELLED
    assert all(sg.status == GoalStatus.CANCELLED for sg in plan.subgoals)
    assert plan.metadata["rejection_reason"] == "Out of scope for this quarter"


@pytest.mark.asyncio
async def test_plan_serialization():
    engine = GoalDecompositionEngine(llm_client=None)
    plan = await engine.decompose_goal(
        title="Automate Morning Routine",
        description="Set up reminders and briefing.",
        target_date="2026-12-01",
    )
    d = plan.to_dict()
    assert "plan_id" in d
    assert "root_goal" in d
    assert len(d["subgoals"]) > 0
    assert d["source"] == "fallback"
    assert d["root_goal"]["title"] == "Automate Morning Routine"
    assert d["root_goal"]["target_date"] == "2026-12-01"
