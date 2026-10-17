import logging
from typing import List, Dict, Any, Tuple
from .models import LearningOutcome, LearningRecord, LearningStatus
import time

logger = logging.getLogger(__name__)

class LearningEvaluator:
    """Evaluates collected outcomes to form candidate improvements and validate them."""
    def __init__(self, config: Dict[str, Any]):
        learning_config = config.get("learning", {})
        self.evidence_threshold = learning_config.get("evidence_threshold", 3)
        self.confidence_threshold = learning_config.get("confidence_threshold", 0.8)

    def evaluate(self, outcomes: List[LearningOutcome], existing_records: List[LearningRecord]) -> List[LearningRecord]:
        """
        Processes new outcomes to update existing records or generate new ones.
        Returns only records that were created or modified.
        """
        updated_records = []

        failures_by_category = {}
        for outcome in outcomes:
            if outcome.status == "FAILED" and outcome.error_category:
                key = f"failure_{outcome.category}_{outcome.error_category}"
                if key not in failures_by_category:
                    failures_by_category[key] = []
                failures_by_category[key].append(outcome)
            elif outcome.status == "COMPLETED":
                key = f"success_{outcome.category}"
                if key not in failures_by_category:
                    failures_by_category[key] = []
                failures_by_category[key].append(outcome)
            elif outcome.user_feedback:
                # Check if a record already exists for this feedback outcome
                already_recorded = any(
                    outcome.outcome_id in r.provenance
                    for r in existing_records
                )
                if not already_recorded:
                    record = LearningRecord(
                        pattern="explicit_feedback",
                        context={"feedback": outcome.user_feedback, "category": outcome.category, "metadata": outcome.metadata},
                        status=LearningStatus.VALIDATED,
                        confidence=1.0,
                        evidence_count=1,
                        provenance=[outcome.outcome_id],
                        inferred=False
                    )
                    updated_records.append(record)

        for key, evidences in failures_by_category.items():
            existing = next((r for r in existing_records if r.pattern == key), None)
            if not existing:
                context_data = {"category": evidences[0].category, "metadata": evidences[0].metadata}
                if evidences[0].error_category:
                    context_data["error_category"] = evidences[0].error_category

                existing = LearningRecord(
                    pattern=key,
                    context=context_data,
                    status=LearningStatus.CANDIDATE,
                    confidence=0.0,
                    evidence_count=0,
                    inferred=True
                )
                updated_records.append(existing)
            else:
                if existing not in updated_records:
                    updated_records.append(existing)

            for ev in evidences:
                if ev.outcome_id not in existing.provenance:
                    existing.provenance.append(ev.outcome_id)
                    existing.evidence_count += 1

            existing.confidence = min(1.0, existing.evidence_count / self.evidence_threshold)
            if existing.confidence >= self.confidence_threshold and existing.status == LearningStatus.CANDIDATE:
                existing.status = LearningStatus.VALIDATED
            existing.updated_at = time.time()

        return updated_records
