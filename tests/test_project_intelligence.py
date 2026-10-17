"""
Unit and integration tests for Prompt 60 — Personal Project Intelligence Subsystem.
Tests project registration, goal linking, blocker management, decision capture,
and status synthesis.
"""

import pytest
from backend.goals.models import Goal, GoalType, GoalStatus
from backend.project_intelligence.models import (
    PersonalProject,
    ProjectStatus,
    ProjectBlocker,
    ProjectDecisionRecord,
)
from backend.project_intelligence.engine import ProjectIntelligenceEngine


class MockGoalEngine:
    def __init__(self, goals_by_id=None):
        self._goals = goals_by_id or {}

    def get_goal(self, goal_id: str):
        return self._goals.get(goal_id)


def test_project_registration_and_serialization():
    engine = ProjectIntelligenceEngine()
    proj = engine.register_project(
        name="JARVIS X Autonomous OS",
        description="Next-generation autonomous system",
        repository_path="C:\\Data\\Projects\\Jarvis X",
        linked_goal_ids=["g_core_01"],
    )

    assert proj.name == "JARVIS X Autonomous OS"
    assert proj.status == ProjectStatus.ACTIVE
    assert proj.linked_goal_ids == ["g_core_01"]

    data = proj.to_dict()
    assert data["name"] == "JARVIS X Autonomous OS"
    restored = PersonalProject.from_dict(data)
    assert restored.project_id == proj.project_id
    assert restored.name == proj.name


def test_blocker_lifecycle():
    engine = ProjectIntelligenceEngine()
    proj = engine.register_project(name="Project Beta")

    blocker = engine.add_blocker(
        project_id=proj.project_id,
        description="Missing GPU compute quota",
        severity="CRITICAL",
    )
    assert blocker.severity == "CRITICAL"
    assert blocker.resolved is False

    # Status check reflects unresolved blocker
    status_report = engine.analyze_project_status(proj.project_id)
    assert status_report["unresolved_blockers_count"] == 1
    assert status_report["overall_health"] == "AT_RISK"

    # Resolve blocker
    success = engine.resolve_blocker(
        project_id=proj.project_id,
        blocker_id=blocker.blocker_id,
        notes="Allocated local RTX 4090 accelerator",
    )
    assert success is True

    # Status check updates health
    status_report2 = engine.analyze_project_status(proj.project_id)
    assert status_report2["unresolved_blockers_count"] == 0
    assert status_report2["overall_health"] == "HEALTHY"


def test_decision_recording_and_goal_grounding():
    g = Goal(
        goal_id="g_phase4",
        title="Complete Phase 4",
        goal_type=GoalType.LONG_TERM,
        status=GoalStatus.ACTIVE,
        progress=0.75,
    )
    goal_engine = MockGoalEngine({"g_phase4": g})
    engine = ProjectIntelligenceEngine(goal_engine=goal_engine)

    proj = engine.register_project(
        name="Phase 4 Development",
        linked_goal_ids=["g_phase4"],
    )

    dec = engine.record_decision(
        project_id=proj.project_id,
        title="Use Directed Acyclic Graph for Workflows",
        rationale="Enforces deterministic topological ordering and cycle prevention",
        decided_by="Lead Architect",
        related_files=["backend/workflows/engine.py"],
    )
    assert dec.title == "Use Directed Acyclic Graph for Workflows"

    report = engine.analyze_project_status(proj.project_id)
    assert report["total_decisions_recorded"] == 1
    assert len(report["linked_goals"]) == 1
    assert report["linked_goals"][0]["goal_id"] == "g_phase4"
    assert report["linked_goals"][0]["progress"] == 0.75
