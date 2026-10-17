"""
Unit and integration tests for Prompt 64 — Continuous Improvement Subsystem.
Tests evidence collection, pattern promotion, recommendation synthesis, and authorization guards.
"""

import pytest
from backend.learning.models import (
    LearningOutcome,
    LearningRecord,
    LearningStatus,
    ImprovementRecommendation,
    ImprovementCategory,
)
from backend.learning.evaluator import LearningEvaluator
from backend.learning.engine import LearningEngine


class MockMemoryAPI:
    def __init__(self):
        self.memories = []

    def search_memory(self, *args, **kwargs):
        return []

    def write_memory(self, **kwargs):
        self.memories.append(kwargs)


def test_evaluator_promotes_repeated_evidence():
    evaluator = LearningEvaluator(config={"learning": {"evidence_threshold": 2, "confidence_threshold": 0.8}})

    o1 = LearningOutcome(task_id="t1", category="workflow", status="FAILED", error_category="TIMEOUT")
    o2 = LearningOutcome(task_id="t2", category="workflow", status="FAILED", error_category="TIMEOUT")

    # First occurrence -> Candidate
    recs = evaluator.evaluate([o1], existing_records=[])
    assert len(recs) == 1
    assert recs[0].status == LearningStatus.CANDIDATE
    assert recs[0].evidence_count == 1

    # Second occurrence -> Meets threshold -> Validated
    recs2 = evaluator.evaluate([o2], existing_records=recs)
    assert len(recs2) == 1
    assert recs2[0].status == LearningStatus.VALIDATED
    assert recs2[0].confidence >= 0.8


def test_recommendation_synthesis_and_approval_flag():
    engine = LearningEngine(config={}, event_bus=None, memory_api=MockMemoryAPI())

    # Seed an active validated record
    record = LearningRecord(
        pattern="user_prefers_concise_reports",
        status=LearningStatus.VALIDATED,
        confidence=0.9,
        evidence_count=4,
        provenance=["out_1", "out_2", "out_3", "out_4"],
    )
    engine.active_records.append(record)

    recs = engine.generate_improvement_recommendations()
    assert len(recs) == 1
    rec = recs[0]
    assert rec.category == ImprovementCategory.USER_EXPERIENCE
    assert rec.requires_approval is True
    assert rec.confidence == 0.9
    assert len(rec.evidence) == 4

    data = rec.to_dict()
    assert data["category"] == "USER_EXPERIENCE"
    assert data["requires_approval"] is True
