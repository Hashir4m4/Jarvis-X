"""
JARVIS X — Intelligent Priority Evaluator & Dynamic Scheduler
Calculates transparent priority scores across goals, plans, and tasks with human override preservation.
"""

import time
import math
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from .models import (
    PriorityLevel,
    ItemType,
    PriorityScoreExplanation,
    PriorityOverride,
    PriorityRecommendation,
)

logger = logging.getLogger("JARVIS.PriorityEngine")


class PriorityEngine:
    """
    Subsystem responsible for evaluating urgency, impact, dependency blockages, and risks.
    Guarantees:
    - Never uses opaque or fabricated scores; every score includes an explainable breakdown.
    - Honors user overrides unconditionally while recording reasoning.
    - Distinguishes recommendations from unilateral commits.
    """

    def __init__(
        self,
        goal_engine: Optional[Any] = None,
        planning_engine: Optional[Any] = None,
        security_proxy: Optional[Any] = None,
    ):
        self.goal_engine = goal_engine
        self.planning_engine = planning_engine
        self.security = security_proxy
        self._overrides: Dict[str, PriorityOverride] = {}

    def set_user_override(
        self,
        item_id: str,
        item_type: ItemType,
        level: PriorityLevel,
        reason: str,
        author: str = "User",
    ) -> PriorityOverride:
        override = PriorityOverride(
            item_id=item_id,
            item_type=item_type,
            assigned_level=level,
            override_reason=reason,
            author=author,
        )
        self._overrides[item_id] = override
        logger.info(f"Priority override set for {item_type.value}:{item_id} -> {level.value} by {author}")
        return override

    def get_override(self, item_id: str) -> Optional[PriorityOverride]:
        return self._overrides.get(item_id)

    def clear_override(self, item_id: str) -> bool:
        if item_id in self._overrides:
            del self._overrides[item_id]
            return True
        return False

    def evaluate_goal_priority(self, goal: Any) -> PriorityScoreExplanation:
        """Calculates explainable priority score for a Goal."""
        item_id = getattr(goal, "goal_id", "unknown_goal")
        reasons = []

        # 1. Urgency Component (0 to 30 pts)
        urgency = 10.0
        target_date_str = getattr(goal, "target_date", None)
        if target_date_str:
            days_left = self._calculate_days_until(target_date_str)
            if days_left is not None:
                if days_left < 0:
                    urgency = 30.0
                    reasons.append(f"Goal is overdue by {abs(days_left):.1f} days (+30 pts urgency)")
                elif days_left <= 7:
                    urgency = 25.0
                    reasons.append(f"Approaching deadline within {days_left:.1f} days (+25 pts urgency)")
                elif days_left <= 30:
                    urgency = 15.0
                    reasons.append(f"Deadline in {days_left:.1f} days (+15 pts urgency)")
                else:
                    urgency = 5.0
                    reasons.append(f"Ample time remaining: {days_left:.1f} days (+5 pts urgency)")

        # 2. Impact Component (0 to 30 pts)
        impact = 15.0
        goal_type = getattr(goal, "goal_type", None)
        type_str = goal_type.value if hasattr(goal_type, "value") else str(goal_type or "")
        if "LONG_TERM" in type_str:
            impact = 25.0
            reasons.append("Long-term strategic priority (+25 pts impact)")
        elif "MEDIUM_TERM" in type_str:
            impact = 18.0
            reasons.append("Medium-term core priority (+18 pts impact)")
        else:
            impact = 12.0
            reasons.append("Short-term operational priority (+12 pts impact)")

        # 3. Dependency Component (0 to 20 pts)
        subgoals = getattr(goal, "subgoal_ids", [])
        dep_score = min(20.0, len(subgoals) * 5.0)
        if subgoals:
            reasons.append(f"Blocks/coordinates {len(subgoals)} subgoals (+{dep_score:.0f} pts dependency)")

        # 4. Risk / Progress (0 to 20 pts)
        progress = getattr(goal, "progress", 0.0)
        risk_score = 10.0
        if progress < 0.2 and urgency >= 20.0:
            risk_score = 18.0
            reasons.append("High risk: Low progress near deadline (+18 pts risk)")

        effort_score = 5.0

        raw_score = urgency + impact + dep_score + risk_score + effort_score
        raw_score = min(100.0, max(0.0, raw_score))

        override = self.get_override(item_id)
        override_delta = 0.0
        if override:
            reasons.append(f"User override applied: fixed to {override.assigned_level.value} ({override.override_reason})")

        return PriorityScoreExplanation(
            item_id=item_id,
            item_type=ItemType.GOAL,
            composite_score=raw_score,
            urgency_component=urgency,
            impact_component=impact,
            dependency_component=dep_score,
            risk_component=risk_score,
            effort_component=effort_score,
            user_override_delta=override_delta,
            reasoning=reasons,
        )

    def score_to_level(self, score: float, override: Optional[PriorityOverride] = None) -> PriorityLevel:
        if override:
            return override.assigned_level
        if score >= 80.0:
            return PriorityLevel.P0_CRITICAL
        elif score >= 60.0:
            return PriorityLevel.P1_HIGH
        elif score >= 40.0:
            return PriorityLevel.P2_MEDIUM
        elif score >= 20.0:
            return PriorityLevel.P3_LOW
        else:
            return PriorityLevel.P4_DEFERRED

    def get_schedule_recommendations(self) -> List[PriorityRecommendation]:
        """
        Ranks all active goals, milestones, and tasks, returning actionable next-step recommendations.
        """
        recommendations = []
        if not self.goal_engine or not hasattr(self.goal_engine, "list_goals"):
            return recommendations

        active_goals = [
            g for g in self.goal_engine.list_goals()
            if getattr(g, "status", None) and getattr(g.status, "value", str(g.status)) in ("ACTIVE", "PROPOSED")
        ]

        for goal in active_goals:
            explanation = self.evaluate_goal_priority(goal)
            override = self.get_override(goal.goal_id)
            level = self.score_to_level(explanation.composite_score, override)

            is_overdue = explanation.urgency_component >= 28.0
            suggested_action = (
                f"Address immediately: {goal.title}"
                if level in (PriorityLevel.P0_CRITICAL, PriorityLevel.P1_HIGH)
                else f"Maintain scheduled cadence for: {goal.title}"
            )

            rec = PriorityRecommendation(
                item_id=goal.goal_id,
                item_type=ItemType.GOAL,
                title=goal.title,
                recommended_level=level,
                score_explanation=explanation,
                suggested_action=suggested_action,
                is_overdue=is_overdue,
            )
            recommendations.append(rec)

        # Sort recommendations descending by score
        recommendations.sort(
            key=lambda r: (
                r.score_explanation.composite_score if r.score_explanation else 0.0
            ),
            reverse=True,
        )
        return recommendations

    def _calculate_days_until(self, date_str: str) -> Optional[float]:
        try:
            # Handle YYYY-MM-DD or ISO formats
            clean_str = date_str.split("T")[0]
            dt = datetime.strptime(clean_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            delta = (dt - now).total_seconds() / 86400.0
            return delta
        except Exception:
            return None
