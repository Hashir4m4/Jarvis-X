import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Set
import time

from backend.kernel.event_bus import EventBus
from backend.memory.memory_api import MemoryAPI
from .models import LearningOutcome, LearningRecord, LearningStatus
from .evaluator import LearningEvaluator

logger = logging.getLogger(__name__)

# Keys whose values are redacted when persisting learning records.
_SENSITIVE_KEY_FRAGMENTS = frozenset([
    'password', 'secret', 'token', 'key', 'auth', 'credential', 'email', 'pii',
])


def sanitize_data(data):
    """Recursively redact values whose dictionary key contains a sensitive fragment."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = k.lower()
            if any(s in k_lower for s in _SENSITIVE_KEY_FRAGMENTS):
                sanitized[k] = '[REDACTED]'
            else:
                sanitized[k] = sanitize_data(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    return data


class LearningEngine:
    def __init__(self, config: Dict[str, Any], event_bus: EventBus, memory_api: MemoryAPI):
        self.config = config
        self.learning_config = config.get("learning", {})
        self.enabled = self.learning_config.get("enabled", True)
        self.max_retained = self.learning_config.get("max_retained_records", 1000)

        self.event_bus = event_bus
        self.memory_api = memory_api
        self.evaluator = LearningEvaluator(self.config)

        self.outcomes: List[LearningOutcome] = []
        self.active_records: List[LearningRecord] = []
        self._persisted_ids: Set[str] = set()

        self.last_learning_cycle: float = 0.0
        self.last_error: Optional[str] = None
        self._started = False

        self._load_records()

    def _load_records(self):
        try:
            results = self.memory_api.search_memory("type:learning_record", limit=self.max_retained, search_vault=False)
            for res in results:
                if "content" in res:
                    try:
                        data = json.loads(res["content"])
                        if "record_id" in data:
                            status_val = data.get("status", "CANDIDATE")
                            rec = LearningRecord(
                                record_id=data["record_id"],
                                pattern=data.get("pattern", ""),
                                context=data.get("context", {}),
                                status=LearningStatus(status_val) if status_val in [s.value for s in LearningStatus] else LearningStatus.CANDIDATE,
                                confidence=data.get("confidence", 0.0),
                                evidence_count=data.get("evidence_count", 0),
                                provenance=data.get("provenance", []),
                                inferred=data.get("inferred", True)
                            )
                            self.active_records.append(rec)
                            if rec.status == LearningStatus.VALIDATED:
                                self._persisted_ids.add(rec.record_id)
                    except (json.JSONDecodeError, KeyError, ValueError) as parse_err:
                        logger.warning(f"Skipping malformed learning record: {parse_err}")
                        self.last_error = f"Malformed record skipped: {parse_err}"
        except Exception as e:
            self.last_error = "Failed to load records"
            logger.error(f"Learning engine init error: {e}")

    async def start(self):
        if not self.enabled:
            logger.info("Autonomous Learning System is disabled by configuration.")
            return
        if self._started:
            logger.warning("Learning engine start() called more than once; ignoring.")
            return

        await self.event_bus.subscribe("orchestrator_state_change", self._handle_task_state)
        self._started = True
        logger.info("Autonomous Learning System started.")

    async def shutdown(self):
        """Unsubscribe from events on shutdown."""
        if self._started:
            await self.event_bus.unsubscribe("orchestrator_state_change", self._handle_task_state)
            self._started = False
            logger.info("Autonomous Learning System shut down.")

    async def _handle_task_state(self, event_type: str, data: Dict[str, Any]):
        if not self.enabled:
            return

        state = data.get("state")
        if state in ("COMPLETED", "FAILED", "CANCELLED"):
            outcome = LearningOutcome(
                task_id=data.get("request_id"),
                category=data.get("task_category", "unknown"),
                status=state,
                metadata=data.get("details", {}),
                error_category=data.get("details", {}).get("error_category") if state == "FAILED" else None,
                source="system"
            )

            existing_idx = next((i for i, o in enumerate(self.outcomes) if o.task_id and o.task_id == outcome.task_id), None)
            if existing_idx is not None:
                outcome.outcome_id = self.outcomes[existing_idx].outcome_id
                self.outcomes[existing_idx] = outcome
            else:
                self.outcomes.append(outcome)

            asyncio.create_task(self._run_learning_cycle())

    async def submit_explicit_feedback(self, data: Dict[str, Any]):
        if not self.enabled:
            return

        feedback_text = data.get("feedback")
        if not feedback_text or not isinstance(feedback_text, str) or not feedback_text.strip():
            logger.warning("Rejected empty or non-string feedback submission.")
            return

        outcome = LearningOutcome(
            task_id=data.get("request_id"),
            status="FEEDBACK",
            user_feedback=feedback_text.strip(),
            source="user_explicit",
            category=data.get("category", "unknown"),
            metadata=data.get("metadata", {})
        )

        existing_idx = next((i for i, o in enumerate(self.outcomes) if o.task_id and o.task_id == outcome.task_id and o.status == "FEEDBACK"), None)
        if existing_idx is not None:
            outcome.outcome_id = self.outcomes[existing_idx].outcome_id
            self.outcomes[existing_idx] = outcome
        else:
            self.outcomes.append(outcome)

        asyncio.create_task(self._run_learning_cycle())

    async def _run_learning_cycle(self):
        try:
            unique_outcomes = {o.task_id if o.task_id else o.outcome_id: o for o in self.outcomes}.values()
            self.outcomes = list(unique_outcomes)

            updated_records = self.evaluator.evaluate(self.outcomes, self.active_records)
            for rec in updated_records:
                if rec not in self.active_records:
                    self.active_records.append(rec)

            # Enforce max_retained_records
            if len(self.active_records) > self.max_retained:
                # Keep validated first, then newest candidates
                self.active_records.sort(key=lambda r: (r.status != LearningStatus.VALIDATED, -r.updated_at))
                self.active_records = self.active_records[:self.max_retained]

            for rec in self.active_records:
                if rec.status == LearningStatus.VALIDATED and rec.record_id not in self._persisted_ids:
                    await self._persist_record(rec)
                    self._persisted_ids.add(rec.record_id)

            self.last_learning_cycle = time.time()
        except Exception as e:
            self.last_error = f"Learning cycle error: {str(e)}"
            logger.error(self.last_error)

    async def _persist_record(self, record: LearningRecord):
        try:
            content = json.dumps({
                "type": "learning_record",
                "record_id": record.record_id,
                "pattern": record.pattern,
                "context": sanitize_data(record.context),
                "status": record.status.value,
                "confidence": record.confidence,
                "evidence_count": record.evidence_count,
                "provenance": record.provenance,
                "inferred": record.inferred
            })
            self.memory_api.write_memory(
                content=content,
                memory_type="learning",
                category="learning_record",
                metadata={"type": "learning_record", "pattern": record.pattern}
            )
        except Exception as e:
            logger.error(f"Failed to persist learning record: {e}")

    def get_validated_learnings(self, category: Optional[str] = None) -> List[LearningRecord]:
        if not self.enabled:
            return []
        validated = [r for r in self.active_records if r.status == LearningStatus.VALIDATED]
        if category:
            validated = [r for r in validated if r.context.get("category") == category]
        return validated

    def get_diagnostics(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "outcomes_collected": len(self.outcomes),
            "candidates": len([r for r in self.active_records if r.status == LearningStatus.CANDIDATE]),
            "validated": len([r for r in self.active_records if r.status == LearningStatus.VALIDATED]),
            "rejected_or_expired": len([r for r in self.active_records if r.status in (LearningStatus.REJECTED, LearningStatus.EXPIRED)]),
            "last_learning_cycle": self.last_learning_cycle,
            "last_error": self.last_error
        }

    def generate_improvement_recommendations(self) -> List["ImprovementRecommendation"]:
        """
        Synthesizes actionable system improvement recommendations from validated learning records.
        Guarantees that recommendations require human approval before changing system commitments.
        """
        from .models import ImprovementRecommendation, ImprovementCategory
        recommendations = []
        for record in self.active_records:
            if record.status == LearningStatus.VALIDATED:
                cat = ImprovementCategory.WORKFLOW_RELIABILITY
                if "user_prefers" in record.pattern or "feedback" in record.pattern:
                    cat = ImprovementCategory.USER_EXPERIENCE
                elif "syntax" in record.pattern or "coding" in record.pattern:
                    cat = ImprovementCategory.CODE_QUALITY
                elif "planning" in record.pattern:
                    cat = ImprovementCategory.PLANNING_ACCURACY

                rec = ImprovementRecommendation(
                    category=cat,
                    title=f"Improvement based on observed pattern: {record.pattern}",
                    description=f"Automated pattern observed across {record.evidence_count} verified outcomes.",
                    expected_benefit="Enhances autonomous reliability and reduces error frequency.",
                    risk_level="LOW",
                    confidence=record.confidence,
                    evidence=list(record.provenance),
                    requires_approval=True,
                )
                recommendations.append(rec)
        return recommendations
