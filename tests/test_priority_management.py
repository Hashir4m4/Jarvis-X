"""
Unit and integration tests for Prompt 59 — Advanced Intelligent Priority Management.
Tests explainable multi-component scoring, deadline pressure, user overrides,
and ranked scheduling recommendations.
"""

import pytest
from backend.goals.models import Goal, GoalType, GoalStatus
from backend.priority.models import (
    PriorityLevel,
    ItemType,
    PriorityScoreExplanation,
    PriorityOverride,
)
from backend.priority.engine import PriorityEngine


class MockGoalEngine:
    def __init__(self, goals: list = None):
        self._goals = goals or []

    def list_goals(self):
        return self._goals


def test_priority_score_components_explainable():
    engine = PriorityEngine()
    goal = Goal(
        goal_id="g_urgent",
        title="Urgent Strategic Deliverable",
        goal_type=GoalType.LONG_TERM,
        status=GoalStatus.ACTIVE,
        target_date="2026-10-20",  # ~3 days away
        subgoal_ids=["sub_1", "sub_2"],
        progress=0.1,
    )

    explanation = engine.evaluate_goal_priority(goal)
    assert isinstance(explanation, PriorityScoreExplanation)
    assert explanation.composite_score > 60.0
    assert explanation.urgency_component == 25.0
    assert explanation.impact_component == 25.0
    assert explanation.dependency_component == 10.0
    assert len(explanation.reasoning) >= 3
    # Verify serialization
    data = explanation.to_dict()
    assert "composite_score" in data
    assert "reasoning" in data


def test_user_override_preservation():
    engine = PriorityEngine()
    goal = Goal(
        goal_id="g_low_auto",
        title="Minor Background Goal",
        goal_type=GoalType.SHORT_TERM,
        status=GoalStatus.ACTIVE,
        target_date="2027-01-01",
    )

    # Automatically, it would score low
    explanation = engine.evaluate_goal_priority(goal)
    assert engine.score_to_level(explanation.composite_score) in (PriorityLevel.P3_LOW, PriorityLevel.P4_DEFERRED)

    # Human user sets explicit override to P0_CRITICAL
    override = engine.set_user_override(
        item_id=goal.goal_id,
        item_type=ItemType.GOAL,
        level=PriorityLevel.P0_CRITICAL,
        reason="Board of Directors demonstration",
        author="User",
    )
    assert override.assigned_level == PriorityLevel.P0_CRITICAL

    # Re-evaluating honors override
    assert engine.get_override(goal.goal_id) is not None
    level = engine.score_to_level(explanation.composite_score, override)
    assert level == PriorityLevel.P0_CRITICAL

    # Clearing override restores automatic calculation
    engine.clear_override(goal.goal_id)
    assert engine.get_override(goal.goal_id) is None


def test_ranked_schedule_recommendations():
    g1 = Goal(
        goal_id="g_critical",
        title="Mission Critical API Launch",
        goal_type=GoalType.LONG_TERM,
        status=GoalStatus.ACTIVE,
        target_date="2026-10-18",  # 1 day away
        subgoal_ids=["s1", "s2", "s3"],
        progress=0.05,
    )
    g2 = Goal(
        goal_id="g_routine",
        title="Routine Documentation",
        goal_type=GoalType.SHORT_TERM,
        status=GoalStatus.ACTIVE,
        target_date="2027-06-01",
        progress=0.5,
    )

    goal_engine = MockGoalEngine([g2, g1])
    priority_engine = PriorityEngine(goal_engine=goal_engine)

    recs = priority_engine.get_schedule_recommendations()
    assert len(recs) == 2
    # Highest priority item must be first
    assert recs[0].item_id == "g_critical"
    assert recs[0].recommended_level in (PriorityLevel.P0_CRITICAL, PriorityLevel.P1_HIGH)
    assert recs[1].item_id == "g_routine"
    assert recs[1].recommended_level in (PriorityLevel.P2_MEDIUM, PriorityLevel.P3_LOW, PriorityLevel.P4_DEFERRED)
