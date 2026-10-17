"""
JARVIS X — Long-Horizon Autonomous Planning Engine
Synthesizes, schedules, estimates, assesses risks, and manages the lifecycle
of strategic long-horizon plans for approved goals in JARVIS OS.
Strictly non-executing: plans, schedules, and models only.
"""

from typing import Dict, Any, List, Optional, Set, Union
import copy
import datetime
import json
import logging
import os
import re
import threading
import time
import uuid

from .long_horizon_models import (
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
from backend.goals.models import Goal, GoalStatus, GoalType, GoalValidationError

logger = logging.getLogger("JARVIS.LongHorizonPlanningEngine")


class PlanningClarificationRequired(ValueError):
    """Raised when a goal lacks sufficient information to produce a meaningful plan."""
    pass


class PlanningSecurityError(PermissionError):
    """Raised when an operation is denied by SecurityProxy."""
    pass


class LongHorizonPlanningEngine:
    """
    Core Long-Horizon Autonomous Planning Engine.
    Manages strategic plans derived from authoritative GoalManagerEngine goals.
    Strictly handles planning, scheduling, resource estimation, risk evaluation,
    approval workflows, and vault persistence under vault/plans/<plan_id>.md.
    Never executes tasks or actions.
    """

    def __init__(
        self,
        goal_engine: Optional[Any] = None,
        memory_api: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        security_proxy: Optional[Any] = None,
        llm_client: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.goal_engine = goal_engine
        self.memory_api = memory_api
        self.event_bus = event_bus
        self.security = security_proxy
        self.llm = llm_client
        self.config = config or {}

        # Re-entrant thread lock for plan registry operations
        self._lock = threading.RLock()

        # In-memory plan cache {plan_id: LongHorizonPlan}
        self._plans: Dict[str, LongHorizonPlan] = {}

        # Load persisted plans from vault/plans/
        self.load_from_storage()

    # ─────────────────────────────────────────────────────────────
    # Persistence & Rollback Layer (vault/plans/<plan_id>.md)
    # ─────────────────────────────────────────────────────────────

    def _get_vault_manager(self) -> Optional[Any]:
        """Extracts VaultManager from memory_api if present."""
        if not self.memory_api:
            return None
        return getattr(self.memory_api, "vault", None)

    def load_from_storage(self) -> int:
        """
        Loads and validates all persisted plans from vault/plans/.
        Rejects corrupted or malformed files safely without crashing.
        """
        with self._lock:
            self._plans.clear()
            vault = self._get_vault_manager()
            if not vault:
                return 0

            plans_dir = os.path.join(vault.vault_root, "plans")
            if not os.path.isdir(plans_dir):
                return 0

            loaded_count = 0
            for fname in os.listdir(plans_dir):
                if not fname.endswith(".md"):
                    continue
                fpath = os.path.join(plans_dir, fname)
                try:
                    note = vault.read_note(fpath)
                    if not note:
                        continue
                    body = note.get("body", "")
                    p_dict = None
                    json_match = re.search(r"```json\s*([\s\S]*?)\s*```", body)
                    if json_match:
                        p_dict = json.loads(json_match.group(1).strip())
                    elif "plan_data" in note.get("frontmatter", {}):
                        raw = note["frontmatter"]["plan_data"]
                        p_dict = json.loads(raw) if isinstance(raw, str) else raw
                    elif body.strip().startswith("{"):
                        p_dict = json.loads(body.strip())
                    else:
                        p_dict = note.get("frontmatter", {})

                    if p_dict:
                        plan = LongHorizonPlan.from_dict(p_dict)
                        self._plans[plan.plan_id] = plan
                        loaded_count += 1
                except Exception as e:
                    logger.warning(f"Skipping malformed or corrupted plan record '{fname}': {e}")

            logger.info(f"Loaded {loaded_count} long-horizon plans from vault/plans/.")
            return loaded_count

    def _persist_plan(self, plan: LongHorizonPlan) -> bool:
        """
        Persists a LongHorizonPlan record to vault/plans/<plan_id>.md.
        Uses YAML frontmatter and an embedded JSON payload for lossless round-tripping.
        """
        vault = self._get_vault_manager()
        if not vault:
            return True  # In-memory test mode

        try:
            filename = f"{plan.plan_id}.md"
            plan_dict = plan.to_dict()
            json_str = json.dumps(plan_dict, indent=2)

            frontmatter = {
                "title": plan.title,
                "plan_id": plan.plan_id,
                "type": "long_horizon_plan",
                "linked_goal_id": plan.linked_goal_id,
                "status": plan.status.value,
                "milestone_count": len(plan.milestones),
                "revision_count": len(plan.revisions),
                "created_at": plan.created_at,
                "updated_at": plan.updated_at,
            }

            cpm_str = f"Total duration: {plan.critical_path.total_duration if plan.critical_path else 0.0} days"
            crit_ms = ", ".join(plan.critical_path.critical_milestones) if plan.critical_path else "None"

            body = (
                f"# Long-Horizon Strategic Plan: {plan.title}\n\n"
                f"**Plan ID:** `{plan.plan_id}` | **Status:** `{plan.status.value}` | **Goal:** `{plan.linked_goal_id}`\n\n"
                f"## Overview\n{plan.description or 'No overview description.'}\n\n"
                f"## Critical Path\n- {cpm_str}\n- Critical Milestones: `{crit_ms}`\n\n"
                f"## Milestones\n"
                + ("\n".join(f"- `{m.milestone_id}`: {m.title} (Duration: {m.estimated_duration}d, Depends: {m.depends_on})" for m in plan.milestones) if plan.milestones else "- No milestones defined.")
                + "\n\n"
                f"```json\n{json_str}\n```\n"
            )

            vault.write_note(
                folder="plans",
                filename=filename,
                content=body,
                metadata=frontmatter,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to persist plan '{plan.plan_id}': {e}")
            return False

    def _delete_persisted_plan(self, plan_id: str) -> bool:
        """Deletes the plan markdown note from vault storage."""
        vault = self._get_vault_manager()
        if not vault:
            return True
        try:
            if hasattr(vault, "_safe_resolve_path"):
                target_path = vault._safe_resolve_path(f"{plan_id}.md", base_folder="plans")
            else:
                target_path = os.path.join(vault.vault_root, "plans", f"{plan_id}.md")
            if os.path.isfile(target_path):
                os.remove(target_path)
            return True
        except Exception as e:
            logger.error(f"Failed to delete plan file '{plan_id}.md': {e}")
            return False

    # ─────────────────────────────────────────────────────────────
    # Security & EventBus Helpers
    # ─────────────────────────────────────────────────────────────

    def _authorize(self, action_name: str, details: str) -> None:
        """
        Enforces authorization through SecurityProxy.
        Raises PlanningSecurityError if authorization is denied.
        """
        if not self.security:
            return

        if hasattr(self.security, "is_dangerous") and self.security.is_dangerous(action_name):
            if hasattr(self.security, "request_confirmation"):
                confirmed = self.security.request_confirmation(action_name, details)
                if not confirmed:
                    logger.warning(f"SecurityProxy DENIED action '{action_name}': {details}")
                    raise PlanningSecurityError(f"Action '{action_name}' was denied by security policy.")
        elif hasattr(self.security, "get_permission_level"):
            # Check if confirmation callback is set and denies
            perm = self.security.get_permission_level(action_name)
            # If RESTRICTED or CONFIRM and confirmation fails:
            if perm.value in ("CONFIRM", "RESTRICTED") and getattr(self.security, "confirmation_callback", None):
                cb = self.security.confirmation_callback
                if not cb(action_name, details):
                    raise PlanningSecurityError(f"Action '{action_name}' rejected by confirmation callback.")

    def _publish_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Safely publishes planning events to EventBus without breaking caller state."""
        if not self.event_bus:
            return
        try:
            if hasattr(self.event_bus, "publish"):
                import asyncio
                import inspect
                publish_fn = self.event_bus.publish
                if inspect.iscoroutinefunction(publish_fn):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(publish_fn(event_type, data))
                    except RuntimeError:
                        try:
                            asyncio.run(publish_fn(event_type, data))
                        except Exception:
                            pass
                else:
                    publish_fn(event_type, data)
        except Exception as e:
            logger.warning(f"EventBus publication failed for {event_type}: {e}")

    # ─────────────────────────────────────────────────────────────
    # Goal-to-Plan Synthesis
    # ─────────────────────────────────────────────────────────────

    def _retrieve_source_goal(self, goal_id: str) -> Goal:
        """
        Retrieves the authoritative Goal object from GoalManagerEngine or local lookup.
        """
        if not goal_id or not str(goal_id).strip():
            raise PlanModelValidationError("goal_id must be a non-empty string.")

        if self.goal_engine is not None and hasattr(self.goal_engine, "get_goal"):
            goal = self.goal_engine.get_goal(goal_id)
            if not goal:
                raise PlanModelValidationError(f"Source goal '{goal_id}' not found in GoalManagerEngine.")
            return goal

        # If goal_engine is a dictionary or mocked store
        if isinstance(self.goal_engine, dict):
            if goal_id in self.goal_engine:
                return self.goal_engine[goal_id]
            raise PlanModelValidationError(f"Source goal '{goal_id}' not found in GoalManagerEngine.")

        raise PlanModelValidationError(f"No goal engine available to resolve goal '{goal_id}'.")

    def synthesize_plan(
        self,
        goal_id: str,
        title: Optional[str] = None,
        author: str = "JARVIS",
        deadline: Optional[str] = None,
    ) -> LongHorizonPlan:
        """
        Synthesizes a proposed LongHorizonPlan from an existing authoritative Goal.
        Enforces strict non-execution: creates strategic milestone structure, schedules,
        resource estimations, and risk matrices only.
        """
        self._authorize("plan", f"Synthesize long-horizon plan for goal {goal_id}")
        source_goal = self._retrieve_source_goal(goal_id)

        # Check for sufficient information
        goal_text = f"{source_goal.title.strip()} {source_goal.description.strip()}".strip()
        criteria_count = len(source_goal.completion_criteria)
        tasks_count = len(source_goal.tasks)
        subgoals_count = len(source_goal.subgoal_ids)

        if len(goal_text) <= 15 and criteria_count == 0 and tasks_count == 0 and subgoals_count == 0:
            raise PlanningClarificationRequired(
                f"Source goal '{goal_id}' lacks sufficient detail to formulate a plan. Clarification required."
            )

        target_deadline = deadline or source_goal.target_date
        plan_title = title or f"Strategic Plan: {source_goal.title}"
        plan_id = f"lhplan_{uuid.uuid4().hex[:8]}"

        # Synthesis: generate milestones, dependencies, resources, risks
        milestones = self._generate_milestones(source_goal, target_deadline)
        graph = DependencyGraph.from_milestones(milestones)
        cpm = CriticalPath.compute(milestones, graph)

        # Validate schedule against deadline constraints if target_date exists
        self._validate_deadline_constraints(cpm, target_deadline)

        resources = self._estimate_resources(source_goal, milestones, cpm)
        risks = self._assess_risks(source_goal, milestones, cpm, target_deadline)

        plan = LongHorizonPlan(
            plan_id=plan_id,
            linked_goal_id=source_goal.goal_id,
            title=plan_title,
            description=f"Strategic plan synthesized from goal '{source_goal.title}'. {source_goal.description}".strip(),
            status=PlanStatus.DRAFT,
            milestones=milestones,
            dependency_graph=graph,
            critical_path=cpm,
            resource_estimates=resources,
            risk_assessments=risks,
            revisions=[],
            created_at=time.time(),
            updated_at=time.time(),
            metadata={
                "source_goal_type": source_goal.goal_type.value,
                "synthesized_by": author,
                "target_deadline": target_deadline,
            },
        )

        # Create initial baseline revision snapshot
        plan.create_revision_snapshot(
            author=author,
            change_reason="Initial plan synthesis",
            structural_change_summary=f"Synthesized {len(milestones)} milestones from goal {source_goal.goal_id}",
        )

        return plan

    def _generate_milestones(self, goal: Goal, target_deadline: Optional[str]) -> List[Milestone]:
        """
        Deterministic synthesis of strategic milestones based on goal subgoals, tasks, and type.
        """
        milestones: List[Milestone] = []

        # If goal already has child subgoals in GoalManagerEngine, convert subgoals to milestones
        if goal.subgoal_ids and self.goal_engine and hasattr(self.goal_engine, "get_goal"):
            seq = 1
            prev_id: Optional[str] = None
            for sid in goal.subgoal_ids:
                subg = self.goal_engine.get_goal(sid)
                if subg:
                    ms_id = f"ms_{subg.goal_id}"
                    dur = max(1.0, float(len(subg.tasks) * 2.0)) if subg.tasks else 3.0
                    deps = [prev_id] if prev_id else []
                    ms = Milestone(
                        milestone_id=ms_id,
                        title=subg.title,
                        description=subg.description or f"Execute milestone corresponding to subgoal {subg.goal_id}",
                        sequence=seq,
                        estimated_duration=dur,
                        success_criteria=list(subg.completion_criteria) or [f"Complete {subg.title}"],
                        depends_on=deps,
                        deliverables=[f"Outcome report for {subg.title}"],
                        required_capabilities=["system", "coding"] if "code" in subg.title.lower() else ["general"],
                        status=MilestoneStatus.PENDING,
                    )
                    milestones.append(ms)
                    prev_id = ms_id
                    seq += 1

        # Otherwise deterministic multi-phase synthesis
        if not milestones:
            # Phase 1: Research, Architecture & Discovery
            m1_id = f"ms_{uuid.uuid4().hex[:6]}_audit"
            m1 = Milestone(
                milestone_id=m1_id,
                title="Discovery and Architectural Design",
                description="Analyze requirements, domain boundaries, and existing state.",
                sequence=1,
                estimated_duration=2.0,
                success_criteria=["Architecture specification documented", "Dependencies identified"],
                depends_on=[],
                deliverables=["Architecture Specification Document"],
                required_capabilities=["architect", "analyst"],
                status=MilestoneStatus.PENDING,
            )

            # Phase 2: Core Implementation
            m2_id = f"ms_{uuid.uuid4().hex[:6]}_core"
            m2 = Milestone(
                milestone_id=m2_id,
                title="Core Domain Implementation",
                description="Develop core logic, services, and domain components.",
                sequence=2,
                estimated_duration=4.0,
                success_criteria=["Core logic implemented", "Unit tests passing"],
                depends_on=[m1_id],
                deliverables=["Core implementation code", "Unit test suite"],
                required_capabilities=["developer"],
                status=MilestoneStatus.PENDING,
            )

            # Phase 3: Integration & Security Validation (can run parallel or sequential)
            m3_id = f"ms_{uuid.uuid4().hex[:6]}_qa"
            m3 = Milestone(
                milestone_id=m3_id,
                title="System Integration and Security Review",
                description="End-to-end integration verification, regression tests, and security audit.",
                sequence=3,
                estimated_duration=3.0,
                success_criteria=["Zero regressions", "Security audit passed"],
                depends_on=[m2_id],
                deliverables=["Verification Report", "Audit Clearance"],
                required_capabilities=["qa_engineer", "security_auditor"],
                status=MilestoneStatus.PENDING,
            )

            # Phase 4: Final Verification & Sign-off
            m4_id = f"ms_{uuid.uuid4().hex[:6]}_signoff"
            m4 = Milestone(
                milestone_id=m4_id,
                title="Stakeholder Sign-Off and Release Preparation",
                description="Final review against completion criteria and operational handoff.",
                sequence=4,
                estimated_duration=1.0,
                success_criteria=list(goal.completion_criteria) or ["User sign-off obtained"],
                depends_on=[m3_id],
                deliverables=["Release Notes", "Hand-off Documentation"],
                required_capabilities=["operator"],
                status=MilestoneStatus.PENDING,
            )
            milestones = [m1, m2, m3, m4]

        return milestones

    def _validate_deadline_constraints(self, cpm: CriticalPath, target_deadline: Optional[str]) -> None:
        """
        Validates whether total estimated duration exceeds available time before target_deadline.
        Raises PlanModelValidationError if deadline is mathematically impossible.
        """
        if not target_deadline:
            return

        try:
            deadline_dt = datetime.datetime.fromisoformat(target_deadline.replace("Z", "+00:00"))
            now_dt = datetime.datetime.now(datetime.timezone.utc)
            if deadline_dt.tzinfo is None:
                deadline_dt = deadline_dt.replace(tzinfo=datetime.timezone.utc)

            remaining_days = (deadline_dt - now_dt).total_seconds() / 86400.0

            if remaining_days <= 0:
                raise PlanModelValidationError(
                    f"Impossible deadline constraint: Target deadline '{target_deadline}' is in the past."
                )

            # If CPM duration exceeds remaining days
            if cpm.total_duration > remaining_days:
                raise PlanModelValidationError(
                    f"Impossible schedule: Critical path duration ({cpm.total_duration:.1f} days) "
                    f"exceeds available window to deadline ({remaining_days:.1f} days)."
                )
        except ValueError as e:
            if "Impossible" in str(e):
                raise
            # If not parseable as ISO, handled by milestone date validator
            pass

    def _estimate_resources(
        self,
        goal: Goal,
        milestones: List[Milestone],
        cpm: CriticalPath,
    ) -> ResourceEstimate:
        """
        Projects resource envelopes and capability requirements.
        Distinguishes estimates from reserved/verified availability.
        """
        capabilities: Set[str] = set()
        total_hours = 0.0

        for m in milestones:
            capabilities.update(m.required_capabilities)
            # 8 working hours per day of estimated duration
            total_hours += m.estimated_duration * 8.0

        token_budget = int(len(milestones) * 25000 + total_hours * 1000)

        compute_req = "standard"
        if total_hours > 80.0 or len(milestones) > 6:
            compute_req = "high-compute"

        oversight = "mandatory-per-milestone" if goal.goal_type == GoalType.LONG_TERM else "periodic"

        return ResourceEstimate(
            required_capabilities=sorted(list(capabilities)),
            estimated_human_effort_hours=round(total_hours, 1),
            estimated_compute_requirements=compute_req,
            estimated_token_budget=token_budget,
            required_human_oversight=oversight,
            assumptions=[
                "Estimates are projections only; no execution resources are reserved.",
                "Standard 8-hour working day per milestone duration unit.",
                "Zero concurrent human blockers on critical path.",
            ],
            confidence=0.85,
        )

    def _assess_risks(
        self,
        goal: Goal,
        milestones: List[Milestone],
        cpm: CriticalPath,
        target_deadline: Optional[str],
    ) -> List[RiskAssessment]:
        """
        Identifies deadline, dependency, technical, and external risks.
        """
        risks: List[RiskAssessment] = []

        # 1. Critical Path Bottleneck Risk
        if len(cpm.critical_milestones) >= 2:
            risks.append(
                RiskAssessment(
                    risk_id=f"risk_cpm_{uuid.uuid4().hex[:6]}",
                    description=f"Critical path dependencies ({len(cpm.critical_milestones)} milestones) offer zero slack.",
                    probability=0.4,
                    impact=0.7,
                    severity=RiskSeverity.HIGH,
                    mitigation_strategy="Prioritize early reviews and monitor zero-slack milestones closely.",
                    trigger_conditions=["Any milestone on critical path slips by > 1 day."],
                    residual_risk="MEDIUM",
                )
            )

        # 2. Scope & Technical Uncertainty Risk
        if len(goal.description) > 300 or len(milestones) >= 4:
            risks.append(
                RiskAssessment(
                    risk_id=f"risk_tech_{uuid.uuid4().hex[:6]}",
                    description="High complexity scope may introduce unmodeled technical dependencies.",
                    probability=0.3,
                    impact=0.5,
                    severity=RiskSeverity.MEDIUM,
                    mitigation_strategy="Conduct milestone 1 discovery gates before expanding implementation.",
                    trigger_conditions=["Discovery uncovers > 2 unforeseen third-party dependencies."],
                    residual_risk="LOW",
                )
            )

        # 3. Deadline Compression Risk
        if target_deadline:
            risks.append(
                RiskAssessment(
                    risk_id=f"risk_dl_{uuid.uuid4().hex[:6]}",
                    description="Fixed target date limits schedule buffer.",
                    probability=0.35,
                    impact=0.8,
                    severity=RiskSeverity.HIGH,
                    mitigation_strategy="Implement scope shed or milestone deferral if progress flags.",
                    trigger_conditions=["Milestone duration exceeds 120% of estimate."],
                    residual_risk="LOW",
                )
            )

        return risks

    # ─────────────────────────────────────────────────────────────
    # Plan Lifecycle Operations
    # ─────────────────────────────────────────────────────────────

    def create_plan(
        self,
        goal_id: str,
        title: Optional[str] = None,
        author: str = "JARVIS",
        deadline: Optional[str] = None,
    ) -> LongHorizonPlan:
        """
        Synthesizes, validates, caches, and persists a new LongHorizonPlan in DRAFT status.
        Requires authorization.
        """
        self._authorize("create_file", f"Create plan for goal {goal_id}")
        with self._lock:
            plan = self.synthesize_plan(goal_id=goal_id, title=title, author=author, deadline=deadline)

            # Persist with rollback guarantee
            if not self._persist_plan(plan):
                raise IOError(f"Failed to persist plan '{plan.plan_id}' to vault storage.")

            self._plans[plan.plan_id] = plan
            self._publish_event("PLAN_CREATED", {"plan_id": plan.plan_id, "goal_id": plan.linked_goal_id, "status": plan.status.value})
            return copy.deepcopy(plan)

    def submit_for_approval(self, plan_id: str, author: str = "JARVIS") -> LongHorizonPlan:
        """
        Transitions a DRAFT plan to PROPOSED status, awaiting human approval.
        """
        self._authorize("plan", f"Submit plan {plan_id} for approval")
        with self._lock:
            if plan_id not in self._plans:
                raise PlanModelValidationError(f"Plan '{plan_id}' not found.")

            plan = self._plans[plan_id]
            prev_status = plan.status

            plan.transition_to(PlanStatus.PROPOSED)
            plan.create_revision_snapshot(
                author=author,
                change_reason="Submitted for human approval",
                structural_change_summary="Status changed to PROPOSED",
            )

            if not self._persist_plan(plan):
                # Rollback
                plan.status = prev_status
                plan.revisions.pop()
                raise IOError(f"Persistence failure submitting plan '{plan_id}'. Rolled back.")

            self._publish_event("PLAN_PROPOSED", {"plan_id": plan.plan_id, "goal_id": plan.linked_goal_id})
            return copy.deepcopy(plan)

    def approve_plan(self, plan_id: str, reviewer: str = "User") -> LongHorizonPlan:
        """
        Explicit human approval of a proposed plan.
        Transitions PROPOSED -> APPROVED.
        Approval and activation remain strictly separate: plan is NOT active yet.
        """
        self._authorize("plan", f"Approve plan {plan_id}")
        with self._lock:
            if plan_id not in self._plans:
                raise PlanModelValidationError(f"Plan '{plan_id}' not found.")

            plan = self._plans[plan_id]
            prev_status = plan.status

            plan.transition_to(PlanStatus.APPROVED)
            plan.create_revision_snapshot(
                author=reviewer,
                change_reason=f"Approved by {reviewer}",
                structural_change_summary="Status transitioned to APPROVED",
            )

            if not self._persist_plan(plan):
                plan.status = prev_status
                plan.revisions.pop()
                raise IOError(f"Persistence failure approving plan '{plan_id}'. Rolled back.")

            self._publish_event("PLAN_APPROVED", {"plan_id": plan.plan_id, "reviewer": reviewer})
            return copy.deepcopy(plan)

    def reject_plan(self, plan_id: str, reviewer: str = "User", reason: str = "") -> LongHorizonPlan:
        """
        Explicit human rejection of a proposed plan.
        Transitions PROPOSED -> REJECTED.
        """
        self._authorize("plan", f"Reject plan {plan_id}")
        with self._lock:
            if plan_id not in self._plans:
                raise PlanModelValidationError(f"Plan '{plan_id}' not found.")

            plan = self._plans[plan_id]
            prev_status = plan.status

            plan.transition_to(PlanStatus.REJECTED)
            plan.metadata["rejection_reason"] = reason
            plan.create_revision_snapshot(
                author=reviewer,
                change_reason=f"Rejected by {reviewer}: {reason}",
                structural_change_summary="Status transitioned to REJECTED",
            )

            if not self._persist_plan(plan):
                plan.status = prev_status
                plan.revisions.pop()
                raise IOError(f"Persistence failure rejecting plan '{plan_id}'. Rolled back.")

            self._publish_event("PLAN_REJECTED", {"plan_id": plan.plan_id, "reviewer": reviewer, "reason": reason})
            return copy.deepcopy(plan)

    def activate_plan(self, plan_id: str, user: str = "User") -> LongHorizonPlan:
        """
        Transitions an APPROVED plan to ACTIVE.
        Strict check: Plan MUST be APPROVED first. Unapproved plan can never become ACTIVE.
        """
        self._authorize("plan", f"Activate plan {plan_id}")
        with self._lock:
            if plan_id not in self._plans:
                raise PlanModelValidationError(f"Plan '{plan_id}' not found.")

            plan = self._plans[plan_id]
            prev_status = plan.status

            plan.transition_to(PlanStatus.ACTIVE)
            plan.create_revision_snapshot(
                author=user,
                change_reason=f"Activated by {user}",
                structural_change_summary="Status transitioned to ACTIVE",
            )

            if not self._persist_plan(plan):
                plan.status = prev_status
                plan.revisions.pop()
                raise IOError(f"Persistence failure activating plan '{plan_id}'. Rolled back.")

            self._publish_event("PLAN_ACTIVE", {"plan_id": plan.plan_id})
            return copy.deepcopy(plan)

    def modify_plan(
        self,
        plan_id: str,
        milestones: Optional[List[Milestone]] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        author: str = "User",
        change_reason: str = "Manual modification",
    ) -> LongHorizonPlan:
        """
        Modifies an existing plan, recalculating dependency graph and CPM.
        Maintains immutable snapshot history before modifications.
        """
        self._authorize("write_file", f"Modify plan {plan_id}")
        with self._lock:
            if plan_id not in self._plans:
                raise PlanModelValidationError(f"Plan '{plan_id}' not found.")

            plan = self._plans[plan_id]
            original_snapshot = copy.deepcopy(plan)

            # Create revision snapshot before mutation
            plan.create_revision_snapshot(
                author=author,
                change_reason=change_reason,
                structural_change_summary="Plan contents modified",
            )

            if title is not None:
                plan.title = title
            if description is not None:
                plan.description = description
            if milestones is not None:
                plan.milestones = milestones

            try:
                plan.sync_graph_and_critical_path()
                plan.validate()
            except Exception as e:
                # Restore original
                self._plans[plan_id] = original_snapshot
                raise PlanModelValidationError(f"Modification rejected due to validation failure: {e}")

            if not self._persist_plan(plan):
                self._plans[plan_id] = original_snapshot
                raise IOError(f"Persistence failure modifying plan '{plan_id}'. Rolled back.")

            self._publish_event("PLAN_MODIFIED", {"plan_id": plan.plan_id, "author": author})
            return copy.deepcopy(plan)

    def get_plan(self, plan_id: str) -> Optional[LongHorizonPlan]:
        """Returns a defensive copy of a plan by ID."""
        self._authorize("read_file", f"Get plan {plan_id}")
        with self._lock:
            plan = self._plans.get(plan_id)
            return copy.deepcopy(plan) if plan else None

    def list_plans(self, status: Optional[Union[PlanStatus, str]] = None) -> List[LongHorizonPlan]:
        """Returns defensive copies of plans, optionally filtered by status."""
        self._authorize("list_files", "List plans")
        with self._lock:
            if isinstance(status, str):
                status = PlanStatus(status)
            results = []
            for p in self._plans.values():
                if status is None or p.status == status:
                    results.append(copy.deepcopy(p))
            return results

    def get_critical_path(self, plan_id: str) -> Optional[CriticalPath]:
        """Returns the CriticalPath computation for a plan."""
        self._authorize("read_file", f"Get critical path for plan {plan_id}")
        with self._lock:
            plan = self._plans.get(plan_id)
            if not plan:
                return None
            return copy.deepcopy(plan.critical_path)
