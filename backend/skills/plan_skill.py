import logging
import datetime
from typing import Dict, Any, List, Optional, Union

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.agents.planner import Planner
from backend.planning.long_horizon_engine import (
    LongHorizonPlanningEngine,
    PlanningSecurityError,
    PlanningClarificationRequired,
)
from backend.planning.adaptive_planning import (
    AdaptivePlanningSubsystem,
    AdaptationTrigger,
    AdaptationTriggerType,
)
from backend.planning.long_horizon_models import (
    PlanStatus,
    MilestoneStatus,
    PlanModelValidationError,
)

logger = logging.getLogger("JARVIS.PlanSkill")


class PlanSkill(BaseSkill):
    """
    Skill for breaking down complex objectives, managing strategic long-horizon plans,
    handling adaptive replanning, daily priorities, and structuring execution plans.
    Integrates with LongHorizonPlanningEngine, AdaptivePlanningSubsystem, and Planner.
    """

    def __init__(
        self,
        planner: Optional[Planner] = None,
        planning_engine: Optional[LongHorizonPlanningEngine] = None,
        adaptive_planning: Optional[AdaptivePlanningSubsystem] = None,
        metadata=None,
    ):
        super().__init__(metadata=metadata)
        self.planner = planner
        self.planning_engine = planning_engine
        self.adaptive_planning = adaptive_planning

    @property
    def name(self) -> str:
        return "plan"

    @property
    def description(self) -> str:
        return "Synthesizes and manages long-horizon plans, computes critical paths, adapts plans, and organizes daily execution."

    @property
    def supported_actions(self) -> List[str]:
        return [
            # Daily & Task Planner actions
            "create_plan",
            "explain_plan",
            "plan_today",
            # Long-Horizon Strategic Planning actions
            "synthesize_plan",
            "create_long_horizon_plan",
            "get_plan",
            "view_plan",
            "list_plans",
            "submit_plan_for_approval",
            "approve_plan",
            "reject_plan",
            "activate_plan",
            "get_critical_path",
            # Adaptive Planning actions
            "assess_adaptation",
            "propose_revision",
            "approve_revision",
            "reject_revision",
            "get_pending_revision",
            "get_revision_history",
        ]

    def _get_planning_engine(self, context: Optional[Dict[str, Any]] = None) -> Optional[LongHorizonPlanningEngine]:
        if self.planning_engine:
            return self.planning_engine
        ctx = context or {}
        eng = ctx.get("planning_engine")
        if eng:
            return eng
        return None

    def _get_adaptive_planning(self, context: Optional[Dict[str, Any]] = None) -> Optional[AdaptivePlanningSubsystem]:
        if self.adaptive_planning:
            return self.adaptive_planning
        ctx = context or {}
        adp = ctx.get("adaptive_planning")
        if adp:
            return adp
        return None

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        action = intent.action.lower() if intent.action else "explain_plan"
        params = intent.parameters or {}
        ctx = context or {}
        memory = ctx.get("memory")
        today_str = datetime.date.today().isoformat()
        planning_engine = self._get_planning_engine(ctx)
        adaptive_planning = self._get_adaptive_planning(ctx)

        try:
            # ─────────────────────────────────────────────────────────────
            # Action: Plan Today (Daily Workflow)
            # ─────────────────────────────────────────────────────────────
            if action in ("plan_today", "today"):
                memory_context = []
                if memory:
                    try:
                        notes = memory.retrieve_context("active tasks, open goals, user preferences", limit=3)
                        for n in notes:
                            if isinstance(n, dict) and "content" in n:
                                memory_context.append(n["content"])
                            elif isinstance(n, str):
                                memory_context.append(n)
                    except Exception as e:
                        logger.debug(f"Memory retrieval error: {e}")

                raw_task = params.get("task", "")
                if raw_task and raw_task not in ("Today's Agenda & Action Items", "active_plan"):
                    top_priorities = [
                        f"1. [ ] {raw_task}",
                        "2. [ ] Review codebase architecture and execute milestones",
                        "3. [ ] Run integration tests and close pending issues",
                    ]
                else:
                    top_priorities = [
                        "1. [ ] Execute core architecture deliverables and roadmap",
                        "2. [ ] Validate multi-agent and system integration tests",
                        "3. [ ] Monitor hardware telemetry and system health",
                    ]

                priorities_text = "\n".join(top_priorities)
                daily_content = (
                    f"## Daily Plan — {today_str}\n\n"
                    f"### Top 3 Priorities\n{priorities_text}\n\n"
                    f"### Context & Notes\n"
                    + (
                        "\n".join(f"- {c[:100]}" for c in memory_context)
                        if memory_context
                        else "- Standard operational parameters."
                    )
                )

                vault_path = None
                if memory and hasattr(memory, "create_daily_note"):
                    try:
                        vault_path = memory.create_daily_note(content=daily_content, date_str=today_str)
                    except Exception as e:
                        logger.warning(f"Failed to store plan in daily vault: {e}")

                output_text = (
                    f"### 📋 Daily Execution Plan — {today_str}\n\n"
                    f"**Top 3 Priorities Today**:\n{priorities_text}\n\n"
                    f"*Saved to Obsidian Daily Note: `{vault_path or 'vault/daily/'}`*"
                )

                return SkillResult(
                    success=True,
                    data={"date": today_str, "priorities": top_priorities, "vault_path": vault_path},
                    message="Daily plan created",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Synthesize / Create Long-Horizon Plan
            # ─────────────────────────────────────────────────────────────
            elif action in ("synthesize_plan", "create_long_horizon_plan"):
                if not planning_engine:
                    return SkillResult(
                        success=False,
                        message="LongHorizonPlanningEngine not configured",
                        output_text="Strategic planning engine is not available.",
                    )
                goal_id = params.get("goal_id") or params.get("id")
                if not goal_id:
                    # Try to locate by title if provided
                    title_candidate = params.get("title") or params.get("task")
                    if title_candidate and planning_engine.goal_engine and hasattr(planning_engine.goal_engine, "list_goals"):
                        matches = [
                            g for g in planning_engine.goal_engine.list_goals()
                            if title_candidate.lower() in g.title.lower()
                        ]
                        if len(matches) == 1:
                            goal_id = matches[0].goal_id
                if not goal_id:
                    return SkillResult(
                        success=False,
                        message="Missing required input: goal_id",
                        output_text="Please specify the goal to formulate a strategic plan for (e.g. goal_id or goal title).",
                    )

                title = params.get("title")
                deadline = params.get("deadline") or params.get("target_date")
                author = params.get("author", "User")
                plan = planning_engine.create_plan(goal_id=goal_id, title=title, author=author, deadline=deadline)

                ms_summary = "\n".join(
                    f"- **{m.sequence}. {m.title}** ({m.estimated_duration}d): {len(m.success_criteria)} criteria"
                    for m in plan.milestones
                )
                output_text = (
                    f"### 🗺️ Strategic Plan Synthesized: **{plan.title}**\n\n"
                    f"- **Plan ID**: `{plan.plan_id}` (Linked Goal: `{plan.linked_goal_id}`)\n"
                    f"- **Status**: `{plan.status.value}`\n"
                    f"- **Critical Path Duration**: **{plan.critical_path.total_duration_days} days**\n"
                    f"- **Milestones ({len(plan.milestones)})**:\n{ms_summary}\n\n"
                    f"*Note: Plan is in `DRAFT` status and requires review and human approval before activation.*"
                )
                return SkillResult(
                    success=True,
                    data={"plan": plan.to_dict()},
                    message=f"Plan '{plan.title}' synthesized successfully",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Get / View Plan
            # ─────────────────────────────────────────────────────────────
            elif action in ("get_plan", "view_plan"):
                if not planning_engine:
                    return SkillResult(
                        success=False,
                        message="LongHorizonPlanningEngine not configured",
                        output_text="Planning engine not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                if not plan_id:
                    return SkillResult(
                        success=False,
                        message="Missing required input: plan_id",
                        output_text="Please specify a plan_id to view.",
                    )
                plan = planning_engine.get_plan(plan_id)
                if not plan:
                    return SkillResult(
                        success=False,
                        message=f"Plan '{plan_id}' not found",
                        output_text=f"No strategic plan found with ID `{plan_id}`.",
                    )

                ms_lines = []
                for m in plan.milestones:
                    crit_tag = "🔥 [Critical Path]" if m.milestone_id in plan.critical_path.critical_milestones else ""
                    ms_lines.append(f"{m.sequence}. **{m.title}** (`{m.milestone_id}`) — {m.estimated_duration} days {crit_tag}")
                    for sc in m.success_criteria:
                        ms_lines.append(f"   - [ ] {sc}")

                output_text = (
                    f"### 🗺️ Strategic Plan: **{plan.title}** (`{plan.plan_id}`)\n\n"
                    f"- **Status**: `{plan.status.value}`\n"
                    f"- **Linked Goal**: `{plan.linked_goal_id}`\n"
                    f"- **Critical Path Duration**: {plan.critical_path.total_duration_days} days\n"
                    f"- **Critical Path Milestones**: {', '.join(plan.critical_path.critical_milestones)}\n"
                    f"- **Revisions**: {len(plan.revisions)} snapshot(s)\n\n"
                    f"#### Milestones:\n" + "\n".join(ms_lines)
                )
                return SkillResult(
                    success=True,
                    data={"plan": plan.to_dict()},
                    message="Plan retrieved",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # Action: List Plans
            # ─────────────────────────────────────────────────────────────
            elif action in ("list_plans", "plans"):
                if not planning_engine:
                    return SkillResult(
                        success=False,
                        message="LongHorizonPlanningEngine not configured",
                        output_text="Planning engine not available.",
                    )
                status_filter = params.get("status")
                plans = planning_engine.list_plans(status=status_filter)
                if not plans:
                    return SkillResult(
                        success=True,
                        data={"plans": []},
                        message="No plans found",
                        output_text="No long-horizon strategic plans recorded.",
                    )

                lines = []
                for p in plans:
                    lines.append(
                        f"- **{p.title}** (`{p.plan_id}`): `{p.status.value}` | Goal: `{p.linked_goal_id}` | "
                        f"{len(p.milestones)} milestones ({p.critical_path.total_duration_days}d)"
                    )
                output_text = f"### 🗺️ Strategic Plans ({len(plans)}):\n" + "\n".join(lines)
                return SkillResult(
                    success=True,
                    data={"plans": [p.to_dict() for p in plans]},
                    message=f"Found {len(plans)} plans",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Submit for Approval
            # ─────────────────────────────────────────────────────────────
            elif action in ("submit_plan_for_approval", "submit_plan"):
                if not planning_engine:
                    return SkillResult(
                        success=False,
                        message="LongHorizonPlanningEngine not configured",
                        output_text="Planning engine not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                author = params.get("author", "User")
                submitted = planning_engine.submit_for_approval(plan_id, author=author)
                return SkillResult(
                    success=True,
                    data={"plan": submitted.to_dict()},
                    message=f"Plan '{submitted.plan_id}' submitted for approval",
                    output_text=f"Plan **{submitted.title}** (`{submitted.plan_id}`) has been transitioned to `PROPOSED` status for human review.",
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Approve Plan
            # ─────────────────────────────────────────────────────────────
            elif action in ("approve_plan", "approve"):
                if not planning_engine:
                    return SkillResult(
                        success=False,
                        message="LongHorizonPlanningEngine not configured",
                        output_text="Planning engine not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                reviewer = params.get("reviewer", "User")
                approved = planning_engine.approve_plan(plan_id, reviewer=reviewer)
                return SkillResult(
                    success=True,
                    data={"plan": approved.to_dict()},
                    message=f"Plan '{approved.plan_id}' approved",
                    output_text=f"✅ Plan **{approved.title}** (`{approved.plan_id}`) has been approved by {reviewer}. Ready for activation.",
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Reject Plan
            # ─────────────────────────────────────────────────────────────
            elif action in ("reject_plan", "reject"):
                if not planning_engine:
                    return SkillResult(
                        success=False,
                        message="LongHorizonPlanningEngine not configured",
                        output_text="Planning engine not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                reviewer = params.get("reviewer", "User")
                reason = params.get("reason", "Rejected by user")
                rejected = planning_engine.reject_plan(plan_id, reviewer=reviewer, reason=reason)
                return SkillResult(
                    success=True,
                    data={"plan": rejected.to_dict()},
                    message=f"Plan '{rejected.plan_id}' rejected",
                    output_text=f"Plan **{rejected.title}** (`{rejected.plan_id}`) was `REJECTED`: {reason}.",
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Activate Plan
            # ─────────────────────────────────────────────────────────────
            elif action in ("activate_plan", "activate"):
                if not planning_engine:
                    return SkillResult(
                        success=False,
                        message="LongHorizonPlanningEngine not configured",
                        output_text="Planning engine not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                user = params.get("user", "User")
                activated = planning_engine.activate_plan(plan_id, user=user)
                return SkillResult(
                    success=True,
                    data={"plan": activated.to_dict()},
                    message=f"Plan '{activated.plan_id}' activated",
                    output_text=f"🚀 Strategic Plan **{activated.title}** (`{activated.plan_id}`) is now `ACTIVE`.",
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Get Critical Path
            # ─────────────────────────────────────────────────────────────
            elif action in ("get_critical_path", "critical_path"):
                if not planning_engine:
                    return SkillResult(
                        success=False,
                        message="LongHorizonPlanningEngine not configured",
                        output_text="Planning engine not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                cpm = planning_engine.get_critical_path(plan_id)
                if not cpm:
                    return SkillResult(
                        success=False,
                        message=f"Critical path not found for plan '{plan_id}'",
                        output_text=f"Could not compute or retrieve critical path for plan `{plan_id}`.",
                    )
                crit_list = ", ".join(f"`{m}`" for m in cpm.critical_milestones)
                output_text = (
                    f"### 🔥 Critical Path Analysis — Plan `{plan_id}`\n\n"
                    f"- **Total Duration**: **{cpm.total_duration_days} days**\n"
                    f"- **Bottleneck Milestones**: {crit_list}\n"
                    f"- Any slippage in these milestones directly delays the final delivery date."
                )
                return SkillResult(
                    success=True,
                    data={"critical_path": cpm.to_dict()},
                    message="Critical path calculated",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Assess Adaptation Requirements
            # ─────────────────────────────────────────────────────────────
            elif action in ("assess_adaptation", "assess"):
                if not adaptive_planning:
                    return SkillResult(
                        success=False,
                        message="AdaptivePlanningSubsystem not configured",
                        output_text="Adaptive planning subsystem is not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                trigger_type_str = params.get("trigger_type", "MILESTONE_DELAYED")
                trigger_type = AdaptationTriggerType(trigger_type_str)
                details = params.get("details", {})
                trigger = AdaptationTrigger(
                    plan_id=plan_id,
                    trigger_type=trigger_type,
                    details=details,
                )
                assessment = adaptive_planning.process_trigger(trigger)
                output_text = (
                    f"### 🔄 Adaptation Assessment for Plan `{plan_id}`\n\n"
                    f"- **Recommendation**: `{assessment.recommendation.value}`\n"
                    f"- **Severity**: `{assessment.severity.value}`\n"
                    f"- **Rationale**: {assessment.rationale}\n"
                    f"- **Schedule Impact**: {assessment.schedule_impact_days} day(s)\n"
                    f"- **Affected Milestones**: {', '.join(assessment.affected_milestones) if assessment.affected_milestones else 'None'}"
                )
                return SkillResult(
                    success=True,
                    data={"assessment": assessment.to_dict()},
                    message="Adaptation assessment complete",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Propose Revision
            # ─────────────────────────────────────────────────────────────
            elif action in ("propose_revision", "propose_plan_revision"):
                if not adaptive_planning:
                    return SkillResult(
                        success=False,
                        message="AdaptivePlanningSubsystem not configured",
                        output_text="Adaptive planning subsystem is not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                author = params.get("author", "JARVIS")
                reason = params.get("reason", "Adaptive trigger requires schedule adjustment")
                candidate, diff = adaptive_planning.propose_revision(
                    plan_id=plan_id,
                    author=author,
                    reason=reason,
                )
                output_text = (
                    f"### 📝 Proposed Plan Revision: `{plan_id}` (v{candidate.revisions[-1].revision_number if candidate.revisions else 'next'})\n\n"
                    f"- **Reason**: {reason}\n"
                    f"- **Duration Shift**: {diff.duration_delta_days:+.1f} days (New Critical Path: {candidate.critical_path.total_duration_days}d)\n"
                    f"- **Modified Milestones**: {len(diff.modified_milestones)}\n"
                    f"- **Critical Path Changed**: {diff.critical_path_changed}\n\n"
                    f"*Stored as pending proposal. Requires explicit human approval to replace approved baseline.*"
                )
                return SkillResult(
                    success=True,
                    data={"candidate": candidate.to_dict(), "diff": diff.to_dict()},
                    message="Revision proposed",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Approve Revision
            # ─────────────────────────────────────────────────────────────
            elif action in ("approve_revision", "approve_plan_revision"):
                if not adaptive_planning:
                    return SkillResult(
                        success=False,
                        message="AdaptivePlanningSubsystem not configured",
                        output_text="Adaptive planning subsystem is not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                reviewer = params.get("reviewer", "User")
                approved = adaptive_planning.approve_revision(plan_id=plan_id, reviewer=reviewer)
                return SkillResult(
                    success=True,
                    data={"plan": approved.to_dict()},
                    message=f"Revision approved for plan '{plan_id}'",
                    output_text=f"✅ Revision approved. Plan **{approved.title}** (`{plan_id}`) baseline updated to Revision {len(approved.revisions)}.",
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Reject Revision
            # ─────────────────────────────────────────────────────────────
            elif action in ("reject_revision", "reject_plan_revision"):
                if not adaptive_planning:
                    return SkillResult(
                        success=False,
                        message="AdaptivePlanningSubsystem not configured",
                        output_text="Adaptive planning subsystem is not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                reviewer = params.get("reviewer", "User")
                reason = params.get("reason", "Rejected by user")
                rejected = adaptive_planning.reject_revision(plan_id=plan_id, reviewer=reviewer, reason=reason)
                return SkillResult(
                    success=True,
                    data={"plan": rejected.to_dict()},
                    message=f"Pending revision rejected for plan '{plan_id}'",
                    output_text=f"Pending revision for plan `{plan_id}` was discarded. Baseline preserved unchanged.",
                )

            # ─────────────────────────────────────────────────────────────
            # Action: Get Pending Revision
            # ─────────────────────────────────────────────────────────────
            elif action in ("get_pending_revision", "pending_revision"):
                if not adaptive_planning:
                    return SkillResult(
                        success=False,
                        message="AdaptivePlanningSubsystem not configured",
                        output_text="Adaptive planning subsystem is not available.",
                    )
                plan_id = params.get("plan_id") or params.get("id")
                pending = adaptive_planning.get_pending_revision(plan_id)
                if not pending:
                    return SkillResult(
                        success=True,
                        data={"pending": None},
                        message="No pending revisions",
                        output_text=f"Plan `{plan_id}` has no pending revision proposals awaiting approval.",
                    )
                output_text = (
                    f"### ⏳ Pending Proposal for Plan `{plan_id}`\n\n"
                    f"- Proposed by: `{pending.get('candidate_plan', {}).get('metadata', {}).get('proposed_by', 'JARVIS')}`\n"
                    f"- Reason: {pending.get('candidate_plan', {}).get('metadata', {}).get('change_reason', 'None')}\n"
                    f"- Status: `PROPOSED` (Awaiting review)"
                )
                return SkillResult(
                    success=True,
                    data=pending,
                    message="Pending revision retrieved",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # Action: General Implementation Plan (Planner fallback)
            # ─────────────────────────────────────────────────────────────
            elif action in ("create_plan", "explain_plan"):
                task = params.get("task", intent.raw_input)
                if not task:
                    return SkillResult(
                        success=False,
                        message="Missing required input: task",
                        output_text="Please provide a task description to generate an implementation plan.",
                    )

                if not self.planner:
                    return SkillResult(
                        success=True,
                        data={"task": task, "steps": []},
                        message="Plan requested",
                        output_text=f"Planning mode initialized for task: '{task}'.",
                    )

                steps = self.planner.plan(task)
                step_lines = [
                    f"{s.get('step_num', i+1)}. [{s.get('action')}] {s.get('file', '')}: {s.get('description', '')}"
                    for i, s in enumerate(steps)
                ]
                text = f"Implementation Plan ({len(steps)} steps):\n" + "\n".join(step_lines)
                return SkillResult(
                    success=True,
                    data={"task": task, "steps": steps},
                    message=f"Generated {len(steps)} plan steps",
                    output_text=text,
                )

            else:
                return SkillResult(
                    success=False,
                    message=f"Unsupported action: '{action}'",
                    output_text=f"I don't know how to perform action '{action}' in the planning domain.",
                )

        except PlanningSecurityError as pse:
            logger.warning(f"PlanSkill authorization denied: {pse}")
            return SkillResult(
                success=False,
                message=str(pse),
                output_text=f"🔒 Permission Denied: {pse}",
            )
        except PlanningClarificationRequired as pcr:
            logger.info(f"PlanSkill clarification requested: {pcr}")
            return SkillResult(
                success=False,
                message=str(pcr),
                output_text=f"❓ Clarification Required: {pcr}",
            )
        except PlanModelValidationError as ve:
            logger.warning(f"PlanSkill validation error: {ve}")
            return SkillResult(
                success=False,
                message=str(ve),
                output_text=f"Validation Error: {ve}",
            )
        except IOError as ioe:
            logger.error(f"PlanSkill persistence failure: {ioe}")
            return SkillResult(
                success=False,
                message=str(ioe),
                output_text=f"Storage Failure: {ioe}",
            )
        except Exception as e:
            logger.error(f"Unexpected error in PlanSkill: {e}", exc_info=True)
            return SkillResult(
                success=False,
                message=str(e),
                output_text=f"An error occurred while managing plans: {e}",
            )
