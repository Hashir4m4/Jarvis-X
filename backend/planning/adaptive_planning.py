"""
JARVIS X — Adaptive Planning and Versioning Subsystem
Monitors approved goals and long-horizon plans, detects invalidations,
computes deterministic impact and structural diffs, generates proposed revisions,
and manages human approval and baseline transitions without autonomous execution.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Union, Callable
import copy
import datetime
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid

from backend.goals.models import Goal, GoalStatus, GoalType
from backend.planning.long_horizon_models import (
    PlanStatus,
    MilestoneStatus,
    Milestone,
    DependencyGraph,
    CriticalPath,
    ResourceEstimate,
    RiskAssessment,
    RiskSeverity,
    PlanRevision,
    LongHorizonPlan,
    PlanModelValidationError,
)
from backend.planning.long_horizon_engine import (
    LongHorizonPlanningEngine,
    PlanningSecurityError,
)

logger = logging.getLogger("JARVIS.AdaptivePlanning")


# =====================================================================
# 1. Triggers & Analysis Classifications
# =====================================================================

class AdaptationTriggerType(str, Enum):
    MILESTONE_DELAYED = "MILESTONE_DELAYED"
    GOAL_STATUS_CHANGED = "GOAL_STATUS_CHANGED"
    GOAL_DEADLINE_CHANGED = "GOAL_DEADLINE_CHANGED"
    GOAL_CONSTRAINT_CHANGED = "GOAL_CONSTRAINT_CHANGED"
    DEPENDENCY_CHANGED = "DEPENDENCY_CHANGED"
    CRITICAL_PATH_CHANGED = "CRITICAL_PATH_CHANGED"
    RISK_ESCALATION = "RISK_ESCALATION"
    RESOURCE_ESTIMATE_CHANGED = "RESOURCE_ESTIMATE_CHANGED"


class AdaptationActionRecommendation(str, Enum):
    NO_CHANGE_REQUIRED = "NO_CHANGE_REQUIRED"
    MONITOR = "MONITOR"
    REVISION_RECOMMENDED = "REVISION_RECOMMENDED"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"


@dataclass
class AdaptationTrigger:
    """
    Structured trigger indicating a detected discrepancy or change in goal/plan conditions.
    """
    trigger_id: str = field(default_factory=lambda: f"trig_{uuid.uuid4().hex[:8]}")
    trigger_type: AdaptationTriggerType = AdaptationTriggerType.MILESTONE_DELAYED
    goal_id: str = ""
    plan_id: str = ""
    timestamp: float = field(default_factory=time.time)
    previous_state: Dict[str, Any] = field(default_factory=dict)
    new_state: Dict[str, Any] = field(default_factory=dict)
    severity: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL
    explanation: str = ""
    recommended_action: AdaptationActionRecommendation = AdaptationActionRecommendation.REVISION_RECOMMENDED
    metadata: Dict[str, Any] = field(default_factory=dict)

    def fingerprint(self) -> str:
        """Deterministic fingerprint for duplicate event protection."""
        content = f"{self.trigger_type.value}:{self.goal_id}:{self.plan_id}:{json.dumps(self.new_state, sort_keys=True)}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trigger_id": self.trigger_id,
            "trigger_type": self.trigger_type.value,
            "goal_id": self.goal_id,
            "plan_id": self.plan_id,
            "timestamp": self.timestamp,
            "previous_state": copy.deepcopy(self.previous_state),
            "new_state": copy.deepcopy(self.new_state),
            "severity": self.severity,
            "explanation": self.explanation,
            "recommended_action": self.recommended_action.value,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdaptationTrigger":
        return cls(
            trigger_id=data.get("trigger_id") or f"trig_{uuid.uuid4().hex[:8]}",
            trigger_type=AdaptationTriggerType(data.get("trigger_type", AdaptationTriggerType.MILESTONE_DELAYED.value)),
            goal_id=data.get("goal_id", ""),
            plan_id=data.get("plan_id", ""),
            timestamp=float(data.get("timestamp", time.time())),
            previous_state=dict(data.get("previous_state", {})),
            new_state=dict(data.get("new_state", {})),
            severity=data.get("severity", "MEDIUM"),
            explanation=data.get("explanation", ""),
            recommended_action=AdaptationActionRecommendation(
                data.get("recommended_action", AdaptationActionRecommendation.REVISION_RECOMMENDED.value)
            ),
            metadata=dict(data.get("metadata", {})),
        )


# =====================================================================
# 2. Structural Diff
# =====================================================================

@dataclass
class PlanStructuralDiff:
    """
    Machine-readable comparison between an approved baseline plan and a proposed revision.
    """
    baseline_revision_number: int
    proposed_revision_number: int
    added_milestones: List[str] = field(default_factory=list)
    removed_milestones: List[str] = field(default_factory=list)
    modified_milestones: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    changed_dependencies: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    duration_delta_days: float = 0.0
    critical_path_changed: bool = False
    new_critical_milestones: List[str] = field(default_factory=list)
    resource_delta: Dict[str, Any] = field(default_factory=dict)
    risk_delta: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_revision_number": self.baseline_revision_number,
            "proposed_revision_number": self.proposed_revision_number,
            "added_milestones": list(self.added_milestones),
            "removed_milestones": list(self.removed_milestones),
            "modified_milestones": copy.deepcopy(self.modified_milestones),
            "changed_dependencies": copy.deepcopy(self.changed_dependencies),
            "duration_delta_days": round(float(self.duration_delta_days), 4),
            "critical_path_changed": bool(self.critical_path_changed),
            "new_critical_milestones": list(self.new_critical_milestones),
            "resource_delta": copy.deepcopy(self.resource_delta),
            "risk_delta": copy.deepcopy(self.risk_delta),
            "summary": self.summary,
        }

    @classmethod
    def compute(cls, baseline: LongHorizonPlan, candidate: LongHorizonPlan) -> "PlanStructuralDiff":
        """
        Computes a deterministic, structural diff between two plans.
        """
        base_ms = {m.milestone_id: m for m in baseline.milestones}
        cand_ms = {m.milestone_id: m for m in candidate.milestones}

        added = sorted(list(cand_ms.keys() - base_ms.keys()))
        removed = sorted(list(base_ms.keys() - cand_ms.keys()))

        modified: Dict[str, Dict[str, Any]] = {}
        changed_deps: Dict[str, Dict[str, Any]] = {}

        common_ids = sorted(list(base_ms.keys() & cand_ms.keys()))
        for m_id in common_ids:
            b_m = base_ms[m_id]
            c_m = cand_ms[m_id]

            m_diff: Dict[str, Any] = {}
            if b_m.title != c_m.title:
                m_diff["title"] = {"old": b_m.title, "new": c_m.title}
            if abs(b_m.estimated_duration - c_m.estimated_duration) > 1e-4:
                m_diff["duration"] = {"old": b_m.estimated_duration, "new": c_m.estimated_duration}
            if b_m.status != c_m.status:
                m_diff["status"] = {"old": b_m.status.value, "new": c_m.status.value}
            if b_m.target_date != c_m.target_date:
                m_diff["target_date"] = {"old": b_m.target_date, "new": c_m.target_date}

            if m_diff:
                modified[m_id] = m_diff

            if set(b_m.depends_on) != set(c_m.depends_on):
                changed_deps[m_id] = {
                    "old": sorted(list(b_m.depends_on)),
                    "new": sorted(list(c_m.depends_on)),
                }

        # CPM duration delta
        base_dur = baseline.critical_path.total_duration if baseline.critical_path else 0.0
        cand_dur = candidate.critical_path.total_duration if candidate.critical_path else 0.0
        dur_delta = cand_dur - base_dur

        base_crit = baseline.critical_path.critical_milestones if baseline.critical_path else []
        cand_crit = candidate.critical_path.critical_milestones if candidate.critical_path else []
        crit_changed = base_crit != cand_crit

        # Resource differences
        res_delta: Dict[str, Any] = {}
        if baseline.resource_estimates and candidate.resource_estimates:
            b_res = baseline.resource_estimates
            c_res = candidate.resource_estimates
            res_delta = {
                "human_effort_delta_hours": round(c_res.estimated_human_effort_hours - b_res.estimated_human_effort_hours, 2),
                "token_budget_delta": c_res.estimated_token_budget - b_res.estimated_token_budget,
                "oversight_changed": b_res.required_human_oversight != c_res.required_human_oversight,
            }

        # Risk delta
        b_risk_count = len(baseline.risk_assessments)
        c_risk_count = len(candidate.risk_assessments)
        risk_delta = {
            "baseline_risk_count": b_risk_count,
            "candidate_risk_count": c_risk_count,
        }

        base_rev = baseline.revisions[-1].revision_number if baseline.revisions else 1
        cand_rev = base_rev + 1

        summary_parts = []
        if added:
            summary_parts.append(f"Added milestones: {added}")
        if removed:
            summary_parts.append(f"Removed milestones: {removed}")
        if modified:
            summary_parts.append(f"Modified milestones: {list(modified.keys())}")
        if changed_deps:
            summary_parts.append(f"Dependencies modified for {len(changed_deps)} milestones")
        if abs(dur_delta) > 1e-4:
            summary_parts.append(f"Duration changed by {dur_delta:+.1f} days")
        if crit_changed:
            summary_parts.append("Critical path structure shifted")

        summary = "; ".join(summary_parts) if summary_parts else "No structural modifications detected."

        return cls(
            baseline_revision_number=base_rev,
            proposed_revision_number=cand_rev,
            added_milestones=added,
            removed_milestones=removed,
            modified_milestones=modified,
            changed_dependencies=changed_deps,
            duration_delta_days=dur_delta,
            critical_path_changed=crit_changed,
            new_critical_milestones=cand_crit,
            resource_delta=res_delta,
            risk_delta=risk_delta,
            summary=summary,
        )


# =====================================================================
# 3. Adaptation Assessment
# =====================================================================

@dataclass
class AdaptationAssessment:
    """
    Comprehensive evaluation of plan validity in light of detected triggers.
    """
    assessment_id: str = field(default_factory=lambda: f"eval_{uuid.uuid4().hex[:8]}")
    plan_id: str = ""
    goal_id: str = ""
    timestamp: float = field(default_factory=time.time)
    recommendation: AdaptationActionRecommendation = AdaptationActionRecommendation.NO_CHANGE_REQUIRED
    triggers: List[AdaptationTrigger] = field(default_factory=list)
    explanation: str = ""
    feasibility_status: str = "FEASIBLE"  # FEASIBLE, AT_RISK, INFEASIBLE
    structural_diff: Optional[PlanStructuralDiff] = None
    proposed_plan: Optional[LongHorizonPlan] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "plan_id": self.plan_id,
            "goal_id": self.goal_id,
            "timestamp": self.timestamp,
            "recommendation": self.recommendation.value,
            "triggers": [t.to_dict() for t in self.triggers],
            "explanation": self.explanation,
            "feasibility_status": self.feasibility_status,
            "structural_diff": self.structural_diff.to_dict() if self.structural_diff else None,
            "has_proposed_plan": self.proposed_plan is not None,
        }


# =====================================================================
# 4. AdaptivePlanningSubsystem
# =====================================================================

class AdaptivePlanningSubsystem:
    """
    Manages change detection, evaluation, revision proposal generation,
    and human baseline replacement workflows.
    Ensures that approved plans are never altered without explicit human approval.
    """

    def __init__(
        self,
        planning_engine: LongHorizonPlanningEngine,
        goal_engine: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        security_proxy: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.planning_engine = planning_engine
        self.goal_engine = goal_engine
        self.event_bus = event_bus
        self.security = security_proxy
        self.config = config or {}

        # Thread synchronization
        self._lock = threading.RLock()

        # In-memory storage for triggers, assessments, and pending revisions
        # {trigger_fingerprint: timestamp} to prevent duplicate processing
        self._processed_triggers: Dict[str, float] = {}
        # {plan_id: [AdaptationAssessment]}
        self._assessments: Dict[str, List[AdaptationAssessment]] = {}
        # {plan_id: LongHorizonPlan (PROPOSED revision awaiting human approval)}
        self._pending_revisions: Dict[str, LongHorizonPlan] = {}

        # Lifecycle monitoring state
        self._monitoring_active: bool = False
        self._event_subscriptions: List[tuple[str, Callable]] = []

        # Load any persisted pending revisions from vault/plans/pending/
        self.load_pending_revisions_from_storage()

    def _get_vault_manager(self) -> Optional[Any]:
        return getattr(self.planning_engine, "_get_vault_manager", lambda: None)()

    def load_pending_revisions_from_storage(self) -> int:
        """
        Loads persisted pending proposal revisions from vault/plans/pending/.
        Supports recovery after application restart.
        """
        with self._lock:
            vault = self._get_vault_manager()
            if not vault:
                return 0

            pending_dir = os.path.join(vault.vault_root, "plans", "pending")
            if not os.path.isdir(pending_dir):
                return 0

            loaded = 0
            for fname in os.listdir(pending_dir):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(pending_dir, fname)
                try:
                    note = vault.read_note(fpath)
                    if not note:
                        continue
                    body = note.get("body", "")
                    p_dict = None
                    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", body)
                    if json_match:
                        p_dict = json.loads(json_match.group(1).strip())
                    elif body.strip().startswith("{"):
                        p_dict = json.loads(body.strip())
                    else:
                        p_dict = note.get("frontmatter", {})

                    if p_dict:
                        plan = LongHorizonPlan.from_dict(p_dict)
                        self._pending_revisions[plan.plan_id] = plan
                        loaded += 1
                except Exception as e:
                    logger.warning(f"Skipping malformed pending revision note '{fname}': {e}")
            logger.info(f"Loaded {loaded} pending revisions from vault/plans/pending/.")
            return loaded

    def _persist_pending_revision(self, plan: LongHorizonPlan) -> bool:
        """Persists pending proposal to vault/plans/pending/<plan_id>.md."""
        vault = self._get_vault_manager()
        if not vault:
            return True

        try:
            filename = f"{plan.plan_id}.md"
            plan_dict = plan.to_dict()
            json_str = json.dumps(plan_dict, indent=2)

            frontmatter = {
                "title": plan.title,
                "plan_id": plan.plan_id,
                "type": "pending_plan_revision",
                "linked_goal_id": plan.linked_goal_id,
                "status": plan.status.value,
                "created_at": plan.created_at,
                "updated_at": plan.updated_at,
            }

            body = (
                f"# Pending Plan Revision: {plan.title}\n\n"
                f"**Plan ID:** `{plan.plan_id}` | **Status:** `{plan.status.value}` (Awaiting Approval)\n\n"
                f"```json\n{json_str}\n```\n"
            )

            # Store in 'plans/pending'
            vault.write_note(
                folder="plans/pending",
                filename=filename,
                content=body,
                metadata=frontmatter,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to persist pending revision for '{plan.plan_id}': {e}")
            return False

    def _delete_persisted_pending_revision(self, plan_id: str) -> bool:
        """Deletes persisted pending proposal file upon approval or rejection."""
        vault = self._get_vault_manager()
        if not vault:
            return True
        try:
            if hasattr(vault, "_safe_resolve_path"):
                target = vault._safe_resolve_path(f"{plan_id}.md", base_folder="plans/pending")
            else:
                target = os.path.join(vault.vault_root, "plans", "pending", f"{plan_id}.md")
            if os.path.isfile(target):
                os.remove(target)
            return True
        except Exception as e:
            logger.error(f"Failed to delete pending revision file for '{plan_id}': {e}")
            return False

    # ─────────────────────────────────────────────────────────────
    # Lifecycle: Register, Start, Stop Monitoring
    # ─────────────────────────────────────────────────────────────

    def start_monitoring(self) -> None:
        """Starts monitoring goal and plan events on the EventBus."""
        with self._lock:
            if self._monitoring_active:
                return
            self._monitoring_active = True

            if self.event_bus and hasattr(self.event_bus, "subscribe"):
                import asyncio
                import inspect

                # Register event subscriptions
                for ev in ["goal_updated", "goal_status_changed", "milestone_delayed", "plan_modified"]:
                    self._event_subscriptions.append((ev, self._handle_event_bus_event))
                    sub_fn = self.event_bus.subscribe
                    if inspect.iscoroutinefunction(sub_fn):
                        try:
                            loop = asyncio.get_running_loop()
                            loop.create_task(sub_fn(ev, self._handle_event_bus_event))
                        except RuntimeError:
                            try:
                                asyncio.run(sub_fn(ev, self._handle_event_bus_event))
                            except Exception:
                                pass
                    else:
                        sub_fn(ev, self._handle_event_bus_event)
            logger.info("AdaptivePlanningSubsystem monitoring started.")

    def stop_monitoring(self) -> None:
        """Stops monitoring and cleans up EventBus subscriptions."""
        with self._lock:
            self._monitoring_active = False
            self._event_subscriptions.clear()
            logger.info("AdaptivePlanningSubsystem monitoring stopped.")

    def _handle_event_bus_event(self, event_type: str, data: Any) -> None:
        """Internal callback for EventBus notifications."""
        if not self._monitoring_active:
            return
        if not isinstance(data, dict):
            return

        plan_id = data.get("plan_id")
        goal_id = data.get("goal_id")
        if not goal_id and not plan_id:
            return

        # Map event_type to trigger
        trigger_type = AdaptationTriggerType.GOAL_STATUS_CHANGED
        if "milestone" in event_type.lower():
            trigger_type = AdaptationTriggerType.MILESTONE_DELAYED
        elif "deadline" in event_type.lower():
            trigger_type = AdaptationTriggerType.GOAL_DEADLINE_CHANGED

        trigger = AdaptationTrigger(
            trigger_type=trigger_type,
            goal_id=goal_id or "",
            plan_id=plan_id or "",
            previous_state=data.get("previous_state", {}),
            new_state=data.get("new_state", {}),
            explanation=data.get("reason", f"EventBus notification: {event_type}"),
        )
        self.process_trigger(trigger)

    # ─────────────────────────────────────────────────────────────
    # Trigger Processing & Invalidation Checks
    # ─────────────────────────────────────────────────────────────

    def process_trigger(self, trigger: AdaptationTrigger) -> Optional[AdaptationAssessment]:
        """
        Processes an adaptation trigger idempotently.
        Prevents duplicate triggers from generating runaway revisions.
        """
        with self._lock:
            fp = trigger.fingerprint()
            now = time.time()
            # Duplicate check: skip if identical trigger processed in last 60 seconds
            if fp in self._processed_triggers and (now - self._processed_triggers[fp]) < 60.0:
                logger.info(f"Skipping duplicate trigger: {trigger.trigger_type.value} ({fp[:8]})")
                return None

            self._processed_triggers[fp] = now

            # Locate associated plan
            plan: Optional[LongHorizonPlan] = None
            if trigger.plan_id:
                plan = self.planning_engine.get_plan(trigger.plan_id)
            elif trigger.goal_id:
                # Find plan linked to goal
                for p in self.planning_engine.list_plans():
                    if p.linked_goal_id == trigger.goal_id:
                        plan = p
                        break

            if not plan:
                logger.warning(f"No plan found for trigger on goal '{trigger.goal_id}', plan '{trigger.plan_id}'.")
                return None

            # Perform adaptation analysis
            assessment = self.analyze_adaptation(plan, trigger)

            # Store assessment history
            if plan.plan_id not in self._assessments:
                self._assessments[plan.plan_id] = []
            self._assessments[plan.plan_id].append(assessment)

            return assessment

    def analyze_adaptation(self, plan: LongHorizonPlan, trigger: AdaptationTrigger) -> AdaptationAssessment:
        """
        Evaluates whether a plan needs revision based on a trigger.
        Produces deterministic recommendations and reasons.
        """
        # Retrieve source goal
        source_goal: Optional[Goal] = None
        if self.goal_engine and hasattr(self.goal_engine, "get_goal"):
            source_goal = self.goal_engine.get_goal(plan.linked_goal_id)

        rec = AdaptationActionRecommendation.NO_CHANGE_REQUIRED
        feasibility = "FEASIBLE"
        explanation = "Plan commitments remain valid."
        proposed_plan: Optional[LongHorizonPlan] = None
        diff: Optional[PlanStructuralDiff] = None

        # 1. Goal Status Cancelled or Completed
        if source_goal and source_goal.status in (GoalStatus.CANCELLED, GoalStatus.COMPLETED):
            rec = AdaptationActionRecommendation.HUMAN_REVIEW_REQUIRED
            feasibility = "INCONSISTENT"
            explanation = f"Source goal status changed to {source_goal.status.value}; plan should be reviewed for retirement."

        # 2. Milestone Delay or Critical Path Shift
        elif trigger.trigger_type == AdaptationTriggerType.MILESTONE_DELAYED:
            delayed_ms_id = trigger.new_state.get("milestone_id")
            slip_days = float(trigger.new_state.get("slip_days", 0.0))

            if delayed_ms_id and slip_days > 0.0:
                # Check if milestone is on critical path
                is_crit = plan.critical_path and (delayed_ms_id in plan.critical_path.critical_milestones)
                if is_crit:
                    rec = AdaptationActionRecommendation.REVISION_REQUIRED
                    feasibility = "AT_RISK"
                    explanation = f"Milestone '{delayed_ms_id}' on critical path delayed by {slip_days} days. Total schedule impacted."
                else:
                    # Check slack
                    sched = plan.critical_path.schedules.get(delayed_ms_id) if plan.critical_path else None
                    slack = sched.slack if sched else 0.0
                    if slip_days > slack:
                        rec = AdaptationActionRecommendation.REVISION_REQUIRED
                        feasibility = "AT_RISK"
                        explanation = f"Milestone '{delayed_ms_id}' delay ({slip_days}d) exceeds slack ({slack}d). Critical path shifted."
                    else:
                        rec = AdaptationActionRecommendation.MONITOR
                        feasibility = "FEASIBLE"
                        explanation = f"Milestone '{delayed_ms_id}' delayed by {slip_days}d within available slack ({slack}d)."

        # 3. Goal Deadline Changed
        elif trigger.trigger_type == AdaptationTriggerType.GOAL_DEADLINE_CHANGED:
            new_deadline = trigger.new_state.get("target_date")
            if new_deadline:
                try:
                    dl_dt = datetime.datetime.fromisoformat(new_deadline.replace("Z", "+00:00"))
                    now_dt = datetime.datetime.now(datetime.timezone.utc)
                    if dl_dt.tzinfo is None:
                        dl_dt = dl_dt.replace(tzinfo=datetime.timezone.utc)
                    rem_days = (dl_dt - now_dt).total_seconds() / 86400.0

                    if plan.critical_path and plan.critical_path.total_duration > rem_days:
                        rec = AdaptationActionRecommendation.REVISION_REQUIRED
                        feasibility = "INFEASIBLE"
                        explanation = f"New deadline ({rem_days:.1f} days) is less than required plan duration ({plan.critical_path.total_duration:.1f} days)."
                    else:
                        rec = AdaptationActionRecommendation.REVISION_RECOMMENDED
                        explanation = f"Goal deadline updated to '{new_deadline}'. Schedule buffer adjusted."
                except Exception:
                    rec = AdaptationActionRecommendation.HUMAN_REVIEW_REQUIRED
                    explanation = "Unparseable deadline date in trigger."

        # 4. Fallback / General Change
        elif trigger.trigger_type in (AdaptationTriggerType.GOAL_STATUS_CHANGED, AdaptationTriggerType.GOAL_CONSTRAINT_CHANGED):
            rec = AdaptationActionRecommendation.REVISION_RECOMMENDED
            explanation = f"Goal parameters modified: {trigger.explanation}"

        # If revision recommended or required, generate a proposed candidate plan
        if rec in (AdaptationActionRecommendation.REVISION_RECOMMENDED, AdaptationActionRecommendation.REVISION_REQUIRED):
            proposed_plan = self._generate_candidate_revision(plan, trigger)
            if proposed_plan:
                diff = PlanStructuralDiff.compute(baseline=plan, candidate=proposed_plan)

        assessment = AdaptationAssessment(
            plan_id=plan.plan_id,
            goal_id=plan.linked_goal_id,
            recommendation=rec,
            triggers=[trigger],
            explanation=explanation,
            feasibility_status=feasibility,
            structural_diff=diff,
            proposed_plan=proposed_plan,
        )
        return assessment

    # ─────────────────────────────────────────────────────────────
    # Revision Proposal Generation & Diffing
    # ─────────────────────────────────────────────────────────────

    def _generate_candidate_revision(
        self,
        baseline: LongHorizonPlan,
        trigger: AdaptationTrigger,
    ) -> LongHorizonPlan:
        """
        Generates a proposed revision candidate without altering the baseline.
        Adjusts milestone durations, dates, or adds recovery milestones.
        """
        candidate = copy.deepcopy(baseline)
        candidate.status = PlanStatus.PROPOSED  # Proposed revision awaits review

        # If a milestone slipped, adjust its duration
        if trigger.trigger_type == AdaptationTriggerType.MILESTONE_DELAYED:
            delayed_id = trigger.new_state.get("milestone_id")
            slip_days = float(trigger.new_state.get("slip_days") or trigger.new_state.get("delay_days", 0.0))
            if not delayed_id and baseline.critical_path and baseline.critical_path.critical_milestones:
                delayed_id = baseline.critical_path.critical_milestones[0]
            for m in candidate.milestones:
                if m.milestone_id == delayed_id:
                    m.estimated_duration += slip_days
                    break

        # Re-sync graph and critical path
        candidate.sync_graph_and_critical_path()

        # Update resource estimates
        if candidate.resource_estimates:
            tot_hours = sum(m.estimated_duration * 8.0 for m in candidate.milestones)
            candidate.resource_estimates.estimated_human_effort_hours = round(tot_hours, 1)
            candidate.resource_estimates.estimated_token_budget = int(len(candidate.milestones) * 25000 + tot_hours * 1000)

        # Update risk assessments (escalate CPM risk)
        candidate.risk_assessments.append(
            RiskAssessment(
                risk_id=f"risk_adapt_{uuid.uuid4().hex[:6]}",
                description=f"Schedule adjusted due to trigger: {trigger.trigger_type.value}",
                probability=0.4,
                impact=0.6,
                severity=RiskSeverity.MEDIUM,
                mitigation_strategy="Monitor revised milestone critical path and review buffer.",
                trigger_conditions=["Subsequent milestone slips > 0.5 days."],
                residual_risk="LOW",
            )
        )

        candidate.updated_at = time.time()
        return candidate

    def propose_revision(
        self,
        plan_id: str,
        assessment: Optional[AdaptationAssessment] = None,
        author: str = "JARVIS",
        reason: str = "Adaptive trigger requires schedule adjustment",
    ) -> LongHorizonPlan:
        """
        Stores the candidate revision in pending proposals without touching the approved baseline.
        Persists proposal to vault/plans/pending/<plan_id>.md for restart recovery.
        """
        with self._lock:
            baseline = self.planning_engine.get_plan(plan_id)
            if not baseline:
                raise PlanModelValidationError(f"Baseline plan '{plan_id}' not found.")

            if assessment is not None and assessment.proposed_plan is not None:
                candidate = assessment.proposed_plan
            else:
                # Synthesize candidate revision on the fly
                trigger = AdaptationTrigger(
                    plan_id=plan_id,
                    trigger_type=AdaptationTriggerType.MILESTONE_DELAYED,
                    new_state={"delay_days": 3.0, "reason": reason},
                    explanation=reason,
                )
                candidate = self._generate_candidate_revision(baseline, trigger)
            base_rev_num = baseline.revisions[-1].revision_number if baseline.revisions else 1
            candidate.metadata["expected_baseline_revision"] = base_rev_num
            candidate.metadata["proposed_by"] = author

            # Persist pending revision file for restart durability
            self._persist_pending_revision(candidate)

            # Store in pending memory registry
            self._pending_revisions[plan_id] = copy.deepcopy(candidate)
            logger.info(f"Proposed revision stored for plan '{plan_id}'. Baseline remains APPROVED.")
            return copy.deepcopy(candidate)

    # ─────────────────────────────────────────────────────────────
    # Human Approval & Baseline Replacement
    # ─────────────────────────────────────────────────────────────

    def approve_revision(
        self,
        plan_id: str,
        reviewer: str = "User",
        rationale: str = "Approved adaptive revision",
    ) -> LongHorizonPlan:
        """
        Human approval gate for replacing an approved baseline with a proposed revision.
        Enforces authorization via SecurityProxy.
        Validates that candidate was based on the current baseline revision (stale check).
        Preserves the previous version permanently in revision history.
        """
        # Authorization check
        self.planning_engine._authorize("write_file", f"Approve plan revision for {plan_id}")

        with self._lock:
            if plan_id not in self._pending_revisions:
                raise PlanModelValidationError(f"No pending revision found for plan '{plan_id}'.")

            candidate = self._pending_revisions[plan_id]
            current_baseline = self.planning_engine._plans.get(plan_id)
            if not current_baseline:
                raise PlanModelValidationError(f"Original baseline plan '{plan_id}' not found.")

            # Stale baseline check: verify expected baseline matches current baseline
            expected_rev = candidate.metadata.get("expected_baseline_revision")
            current_rev = current_baseline.revisions[-1].revision_number if current_baseline.revisions else 1
            if expected_rev is not None and expected_rev != current_rev:
                raise PlanModelValidationError(
                    f"Stale revision conflict: Proposed revision was based on revision {expected_rev}, "
                    f"but baseline has advanced to revision {current_rev}."
                )

            # Backup copy of baseline in case of rollback
            backup_baseline = copy.deepcopy(current_baseline)

            # Create immutable snapshot of current baseline before replacement
            diff = PlanStructuralDiff.compute(baseline=current_baseline, candidate=candidate)
            summary_desc = diff.summary or rationale

            current_baseline.create_revision_snapshot(
                author=reviewer,
                change_reason=f"Superseded by adaptive revision: {rationale}",
                structural_change_summary=summary_desc,
            )

            # Transfer candidate milestones and updates into candidate
            candidate.revisions = copy.deepcopy(current_baseline.revisions)
            candidate.status = PlanStatus.APPROVED  # Returns to approved baseline
            candidate.updated_at = time.time()

            # Create new revision entry for the approved plan
            candidate.create_revision_snapshot(
                author=reviewer,
                change_reason=f"Approved adaptive revision: {rationale}",
                structural_change_summary=summary_desc,
            )

            # Persist updated baseline
            if not self.planning_engine._persist_plan(candidate):
                # Rollback memory state
                self.planning_engine._plans[plan_id] = backup_baseline
                raise IOError(f"Failed to persist approved revision for plan '{plan_id}'. Rolled back.")

            # Update engine in-memory registry
            self.planning_engine._plans[plan_id] = candidate
            # Remove from pending revisions (both in-memory and disk)
            del self._pending_revisions[plan_id]
            self._delete_persisted_pending_revision(plan_id)

            self.planning_engine._publish_event(
                "PLAN_REVISION_APPROVED",
                {"plan_id": plan_id, "reviewer": reviewer, "revision": candidate.revisions[-1].revision_number},
            )
            return copy.deepcopy(candidate)

    def reject_revision(
        self,
        plan_id: str,
        reviewer: str = "User",
        reason: str = "Revision rejected by reviewer",
    ) -> None:
        """
        Explicit rejection of a proposed plan revision.
        Leaves the existing approved baseline fully intact and logs rejection reason.
        """
        self.planning_engine._authorize("plan", f"Reject plan revision for {plan_id}")

        with self._lock:
            if plan_id not in self._pending_revisions:
                raise PlanModelValidationError(f"No pending revision found for plan '{plan_id}'.")

            # Remove from pending memory and disk
            del self._pending_revisions[plan_id]
            self._delete_persisted_pending_revision(plan_id)

            baseline = self.planning_engine._plans.get(plan_id)
            if baseline:
                baseline.metadata[f"rejected_revision_{int(time.time())}"] = {
                    "reviewer": reviewer,
                    "reason": reason,
                }
                self.planning_engine._persist_plan(baseline)

            self.planning_engine._publish_event(
                "PLAN_REVISION_REJECTED",
                {"plan_id": plan_id, "reviewer": reviewer, "reason": reason},
            )

    def get_pending_revision(self, plan_id: str) -> Optional[LongHorizonPlan]:
        """Returns defensive copy of any pending revision for the plan."""
        with self._lock:
            plan = self._pending_revisions.get(plan_id)
            return copy.deepcopy(plan) if plan else None

    def get_assessments(self, plan_id: str) -> List[AdaptationAssessment]:
        """Returns defensive copies of adaptation assessments for a plan."""
        with self._lock:
            evals = self._assessments.get(plan_id, [])
            return [copy.deepcopy(e) for e in evals]

    def get_revision_history(self, plan_id: str) -> List[PlanRevision]:
        """Returns defensive copies of immutable revision snapshots for a plan."""
        with self._lock:
            plan = self.planning_engine.get_plan(plan_id)
            if not plan:
                return []
            return copy.deepcopy(plan.revisions)
