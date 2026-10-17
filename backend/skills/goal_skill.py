"""
JARVIS X — Goal Management Skill
Provides authoritative user-facing interface for goal creation, intelligent decomposition,
lifecycle tracking, progress roll-ups, and hierarchy inspection via GoalManagerEngine and GoalDecompositionEngine.
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Union

from backend.skills.base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.goals.models import (
    Goal,
    GoalTask,
    GoalType,
    GoalStatus,
    GoalValidationError,
)
from backend.goals.engine import GoalManagerEngine
from backend.goals.decomposition import GoalDecompositionEngine, ProposedGoalPlan

logger = logging.getLogger("JARVIS.GoalSkill")


class GoalSkill(BaseSkill):
    """
    Skill for Goal Management, Decomposition, and Lifecycle tracking in JARVIS OS.
    Integrates directly with GoalManagerEngine and GoalDecompositionEngine.
    """

    def __init__(
        self,
        engine: Optional[GoalManagerEngine] = None,
        decomposition_engine: Optional[GoalDecompositionEngine] = None,
        metadata=None,
    ):
        super().__init__(metadata=metadata)
        self.engine = engine
        self.decomposition_engine = decomposition_engine
        self._pending_plans: Dict[str, ProposedGoalPlan] = {}

    @property
    def name(self) -> str:
        return "goal"

    @property
    def description(self) -> str:
        return "Creates, decomposes, tracks, and manages hierarchical goals and subgoals."

    @property
    def supported_actions(self) -> List[str]:
        return [
            "create_goal",
            "decompose_goal",
            "approve_plan",
            "reject_plan",
            "list_goals",
            "list_active_goals",
            "view_goal",
            "view_goal_hierarchy",
            "check_progress",
            "update_goal",
            "pause_goal",
            "resume_goal",
            "complete_goal",
            "cancel_goal",
        ]

    def _get_engine(self, context: Optional[Dict[str, Any]] = None) -> GoalManagerEngine:
        if self.engine:
            return self.engine
        ctx = context or {}
        eng = ctx.get("goal_engine")
        if eng:
            return eng
        # Fallback to in-memory engine if not provided
        self.engine = GoalManagerEngine(memory_api=ctx.get("memory"))
        return self.engine

    def _get_decomposition_engine(self, context: Optional[Dict[str, Any]] = None) -> GoalDecompositionEngine:
        if self.decomposition_engine:
            return self.decomposition_engine
        ctx = context or {}
        decomp = ctx.get("goal_decomposition_engine")
        if decomp:
            return decomp
        self.decomposition_engine = GoalDecompositionEngine()
        return self.decomposition_engine

    def _find_goal_by_identifier(self, engine: GoalManagerEngine, identifier: str) -> Optional[Goal]:
        if not identifier:
            return None
        clean_id = identifier.strip().strip(".?\"'")
        # Try exact goal_id match first
        g = engine.get_goal(clean_id)
        if g:
            return g
        # Try case-insensitive title search
        lower_id = clean_id.lower()
        candidates = [goal for goal in engine.list_goals() if lower_id in goal.title.lower()]
        if len(candidates) == 1:
            return candidates[0]
        # Return exact title match if multiple matches contain substring
        for c in candidates:
            if c.title.lower() == lower_id:
                return c
        return None

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        action = intent.action.lower() if intent.action else "list_goals"
        params = intent.parameters or {}
        engine = self._get_engine(context)
        decomp_engine = self._get_decomposition_engine(context)

        try:
            # ─────────────────────────────────────────────────────────────
            # 1. Create Goal
            # ─────────────────────────────────────────────────────────────
            if action in ("create_goal", "create", "new_goal"):
                title = params.get("title") or params.get("goal_title") or params.get("text")
                if not title and intent.raw_input:
                    title = params.get("goal_name") or params.get("name")
                if not title or not str(title).strip():
                    return SkillResult(
                        success=False,
                        message="Missing required input: title",
                        output_text="Please specify a title for the goal. Example: 'Create a goal to launch the website'",
                    )
                title = str(title).strip().rstrip(".")
                description = params.get("description", "")
                goal_type = params.get("goal_type", GoalType.SHORT_TERM)
                target_date = params.get("target_date")
                completion_criteria = params.get("completion_criteria", [])

                goal = engine.create_goal(
                    title=title,
                    description=description,
                    goal_type=goal_type,
                    target_date=target_date,
                    completion_criteria=completion_criteria,
                )
                output_text = (
                    f"### 🎯 Goal Created: **{goal.title}**\n\n"
                    f"- **ID:** `{goal.goal_id}`\n"
                    f"- **Type:** `{goal.goal_type.value}`\n"
                    f"- **Status:** `{goal.status.value}`\n"
                    f"- **Target Date:** `{goal.target_date or 'None specified'}`\n"
                )
                return SkillResult(
                    success=True,
                    data={"goal": goal.to_dict()},
                    message=f"Goal '{goal.title}' created successfully.",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # 2. Decompose Goal
            # ─────────────────────────────────────────────────────────────
            elif action in ("decompose_goal", "decompose", "breakdown"):
                title = params.get("title") or params.get("goal_title")
                goal_id = params.get("goal_id") or params.get("id")
                target_goal = None

                if goal_id:
                    target_goal = self._find_goal_by_identifier(engine, goal_id)
                elif title:
                    target_goal = self._find_goal_by_identifier(engine, title)

                # If no existing goal found or title wasn't an ID, use provided title or active goal
                if not target_goal:
                    if not title or title in (".", "this goal", "goal"):
                        # Attempt finding latest active goal
                        active = engine.list_goals(status=GoalStatus.ACTIVE)
                        if active:
                            target_goal = active[-1]
                            title = target_goal.title
                        else:
                            return SkillResult(
                                success=False,
                                message="Missing goal to decompose",
                                output_text="Please specify which goal to break down. Example: 'Break down goal goal_12345 into smaller tasks'",
                            )
                    else:
                        target_goal = Goal(title=title.strip().rstrip("."))

                # Run decomposition asynchronously or synchronously
                try:
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None

                    if loop and loop.is_running():
                        import concurrent.futures
                        with concurrent.futures.ThreadPoolExecutor() as pool:
                            plan = pool.submit(
                                lambda: asyncio.run(decomp_engine.decompose_goal(
                                    title=target_goal.title,
                                    description=target_goal.description,
                                    target_date=target_goal.target_date
                                ))
                            ).result()
                    else:
                        plan = asyncio.run(decomp_engine.decompose_goal(
                            title=target_goal.title,
                            description=target_goal.description,
                            target_date=target_goal.target_date
                        ))
                except Exception as e:
                    # Fallback sync call
                    plan = decomp_engine._rule_based_fallback(
                        target_goal.title,
                        target_goal.description,
                        target_goal.target_date
                    )

                # Store proposed plan for approval workflow
                self._pending_plans[plan.plan_id] = plan

                subgoal_lines = []
                for i, sg in enumerate(plan.subgoals, 1):
                    tasks_count = len(sg.tasks)
                    subgoal_lines.append(f"{i}. **{sg.title}** ({tasks_count} tasks, type: `{sg.goal_type.value}`)")

                clarifications_text = ""
                if plan.clarification_questions:
                    cq_lines = "\n".join(f"  - {q}" for q in plan.clarification_questions)
                    clarifications_text = f"\n\n> [!WARNING]\n> **Unresolved Clarifications Required Before Approval:**\n{cq_lines}\n"

                output_text = (
                    f"### 📋 Proposed Goal Decomposition Plan\n\n"
                    f"**Plan ID:** `{plan.plan_id}` (Status: `PROPOSED — Awaiting Approval`)\n\n"
                    f"**Main Goal:** {plan.root_goal.title}\n\n"
                    f"**Proposed Subgoals ({len(plan.subgoals)}):**\n"
                    + ("\n".join(subgoal_lines) if subgoal_lines else "- No subgoals generated.")
                    + clarifications_text
                    + f"\n\n*To activate this goal plan, review and confirm approval.*"
                )

                return SkillResult(
                    success=True,
                    data={"plan_id": plan.plan_id, "plan": plan.to_dict()},
                    message=f"Generated decomposition plan '{plan.plan_id}' with {len(plan.subgoals)} subgoals.",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # 3. Approve Plan
            # ─────────────────────────────────────────────────────────────
            elif action in ("approve_plan", "approve_goal_plan", "confirm_plan"):
                plan_id = params.get("plan_id")
                force = bool(params.get("force", False))
                if not plan_id and self._pending_plans:
                    plan_id = list(self._pending_plans.keys())[-1]

                if not plan_id or plan_id not in self._pending_plans:
                    return SkillResult(
                        success=False,
                        message="Plan not found",
                        output_text="No pending proposed goal plan found to approve.",
                    )

                plan = self._pending_plans[plan_id]
                saved_root = engine.save_approved_plan(plan, force_unresolved_clarifications=force)
                del self._pending_plans[plan_id]

                output_text = (
                    f"### ✅ Goal Plan Approved & Activated\n\n"
                    f"- **Root Goal:** **{saved_root.title}** (`{saved_root.goal_id}`)\n"
                    f"- **Status:** `{saved_root.status.value}`\n"
                    f"- **Active Subgoals:** {len(saved_root.subgoal_ids)}\n\n"
                    f"*(Note: Approval activates the goal tracking structure; tasks are not executed autonomously.)*"
                )
                return SkillResult(
                    success=True,
                    data={"root_goal": saved_root.to_dict()},
                    message=f"Plan '{plan_id}' approved and persisted.",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # 4. Reject Plan
            # ─────────────────────────────────────────────────────────────
            elif action in ("reject_plan", "reject_goal_plan"):
                plan_id = params.get("plan_id")
                reason = params.get("reason", "User rejected proposal")
                if not plan_id and self._pending_plans:
                    plan_id = list(self._pending_plans.keys())[-1]

                if not plan_id or plan_id not in self._pending_plans:
                    return SkillResult(
                        success=False,
                        message="Plan not found",
                        output_text="No pending goal plan found to reject.",
                    )

                plan = self._pending_plans.pop(plan_id)
                plan.reject(reason=reason)
                return SkillResult(
                    success=True,
                    data={"plan_id": plan_id, "approved": False},
                    message=f"Plan '{plan_id}' rejected.",
                    output_text=f"Proposed goal plan `{plan_id}` was rejected.",
                )

            # ─────────────────────────────────────────────────────────────
            # 5. List All Goals
            # ─────────────────────────────────────────────────────────────
            elif action in ("list_goals", "list_all_goals"):
                goals = engine.list_goals()
                if not goals:
                    return SkillResult(
                        success=True,
                        data={"goals": []},
                        message="No goals found",
                        output_text="No goals have been recorded in the system yet. Say 'Create a goal to...' to set one up.",
                    )
                lines = [
                    f"- **{g.title}** (`{g.goal_id}`) — `{g.status.value}` | Progress: `{round(g.progress * 100, 1)}%`"
                    for g in goals
                ]
                output_text = f"### 🎯 All Recorded Goals ({len(goals)})\n\n" + "\n".join(lines)
                return SkillResult(
                    success=True,
                    data={"goals": [g.to_dict() for g in goals]},
                    message=f"Found {len(goals)} goals.",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # 6. List Active Goals
            # ─────────────────────────────────────────────────────────────
            elif action in ("list_active_goals", "active_goals"):
                active_goals = engine.list_goals(status=GoalStatus.ACTIVE)
                if not active_goals:
                    return SkillResult(
                        success=True,
                        data={"goals": []},
                        message="No active goals",
                        output_text="You have no active goals at the moment.",
                    )
                lines = [
                    f"- **{g.title}** (`{g.goal_id}`) — Type: `{g.goal_type.value}` | Progress: `{round(g.progress * 100, 1)}%`"
                    for g in active_goals
                ]
                output_text = f"### 🚀 Active Goals ({len(active_goals)})\n\n" + "\n".join(lines)
                return SkillResult(
                    success=True,
                    data={"goals": [g.to_dict() for g in active_goals]},
                    message=f"Found {len(active_goals)} active goals.",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # 7. View Specific Goal
            # ─────────────────────────────────────────────────────────────
            elif action in ("view_goal", "get_goal", "show_goal"):
                identifier = params.get("goal_id") or params.get("id") or params.get("title")
                goal = self._find_goal_by_identifier(engine, identifier)
                if not goal:
                    return SkillResult(
                        success=False,
                        message="Goal not found",
                        output_text=f"Could not find goal with identifier: '{identifier}'.",
                    )
                tasks_text = "\n".join(f"  - [{'x' if t.completed else ' '}] {t.description}" for t in goal.tasks) or "  - None"
                output_text = (
                    f"### 🎯 Goal: **{goal.title}**\n\n"
                    f"- **ID:** `{goal.goal_id}`\n"
                    f"- **Type:** `{goal.goal_type.value}`\n"
                    f"- **Status:** `{goal.status.value}`\n"
                    f"- **Progress:** `{round(goal.progress * 100, 1)}%`\n"
                    f"- **Target Date:** `{goal.target_date or 'None'}`\n"
                    f"- **Subgoals:** `{len(goal.subgoal_ids)}`\n\n"
                    f"**Tasks:**\n{tasks_text}\n"
                )
                return SkillResult(
                    success=True,
                    data={"goal": goal.to_dict()},
                    message=f"Retrieved goal '{goal.title}'.",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # 8. View Goal Hierarchy
            # ─────────────────────────────────────────────────────────────
            elif action in ("view_goal_hierarchy", "hierarchy", "goal_tree"):
                root_id = params.get("root_goal_id") or params.get("goal_id")
                trees = engine.get_goal_hierarchy(root_id)
                if not trees:
                    return SkillResult(
                        success=True,
                        data={"hierarchy": []},
                        message="No hierarchy found",
                        output_text="No goal hierarchies found.",
                    )

                def render_tree(node: Dict[str, Any], depth: int = 0) -> str:
                    indent = "  " * depth
                    prog = round(node.get("progress", 0.0) * 100, 1)
                    res = f"{indent}- **{node['title']}** (`{node['goal_id']}`) — `{node['status']}` ({prog}%)\n"
                    for child in node.get("subgoals", []):
                        res += render_tree(child, depth + 1)
                    return res

                tree_text = "".join(render_tree(t) for t in trees)
                output_text = f"### 🌳 Goal Hierarchy Tree\n\n{tree_text}"
                return SkillResult(
                    success=True,
                    data={"hierarchy": trees},
                    message="Retrieved goal hierarchy",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # 9. Check Goal Progress
            # ─────────────────────────────────────────────────────────────
            elif action in ("check_progress", "get_progress", "progress"):
                identifier = params.get("goal_id") or params.get("id") or params.get("title")
                goal = self._find_goal_by_identifier(engine, identifier)
                if not goal:
                    return SkillResult(
                        success=False,
                        message="Goal not found",
                        output_text=f"Could not find goal for progress check: '{identifier}'.",
                    )
                prog = engine.calculate_progress(goal.goal_id)
                pct = round(prog * 100, 1)
                output_text = (
                    f"### 📊 Progress for **{goal.title}**\n\n"
                    f"- **Progress:** `{pct}%`\n"
                    f"- **Status:** `{goal.status.value}`\n"
                    f"- **Tasks Complete:** {sum(1 for t in goal.tasks if t.completed)} / {len(goal.tasks)}\n"
                    f"- **Subgoals:** {len(goal.subgoal_ids)}\n"
                )
                return SkillResult(
                    success=True,
                    data={"goal_id": goal.goal_id, "progress": prog, "percentage": pct},
                    message=f"Progress for '{goal.title}' is {pct}%.",
                    output_text=output_text,
                )

            # ─────────────────────────────────────────────────────────────
            # 10. Update Goal Details
            # ─────────────────────────────────────────────────────────────
            elif action in ("update_goal", "update"):
                identifier = params.get("goal_id") or params.get("id")
                goal = self._find_goal_by_identifier(engine, identifier)
                if not goal:
                    return SkillResult(
                        success=False,
                        message="Goal not found",
                        output_text=f"Could not find goal to update: '{identifier}'.",
                    )
                updates = params.get("updates", {})
                for k in ("title", "description", "target_date", "status"):
                    if k in params:
                        updates[k] = params[k]

                updated_goal = engine.update_goal(goal.goal_id, updates)
                return SkillResult(
                    success=True,
                    data={"goal": updated_goal.to_dict()},
                    message=f"Goal '{updated_goal.title}' updated successfully.",
                    output_text=f"Goal **{updated_goal.title}** (`{updated_goal.goal_id}`) has been updated.",
                )

            # ─────────────────────────────────────────────────────────────
            # 11. Pause Goal
            # ─────────────────────────────────────────────────────────────
            elif action in ("pause_goal", "pause"):
                identifier = params.get("goal_id") or params.get("id")
                goal = self._find_goal_by_identifier(engine, identifier)
                if not goal:
                    return SkillResult(
                        success=False,
                        message="Goal not found",
                        output_text=f"Please specify a valid goal ID to pause. Could not find: '{identifier}'.",
                    )
                paused = engine.pause_goal(goal.goal_id)
                return SkillResult(
                    success=True,
                    data={"goal": paused.to_dict()},
                    message=f"Goal '{paused.title}' paused.",
                    output_text=f"Goal **{paused.title}** (`{paused.goal_id}`) is now `PAUSED`.",
                )

            # ─────────────────────────────────────────────────────────────
            # 12. Resume Goal
            # ─────────────────────────────────────────────────────────────
            elif action in ("resume_goal", "resume"):
                identifier = params.get("goal_id") or params.get("id")
                goal = self._find_goal_by_identifier(engine, identifier)
                if not goal:
                    return SkillResult(
                        success=False,
                        message="Goal not found",
                        output_text=f"Please specify a valid goal ID to resume. Could not find: '{identifier}'.",
                    )
                resumed = engine.resume_goal(goal.goal_id)
                return SkillResult(
                    success=True,
                    data={"goal": resumed.to_dict()},
                    message=f"Goal '{resumed.title}' resumed.",
                    output_text=f"Goal **{resumed.title}** (`{resumed.goal_id}`) is now `ACTIVE`.",
                )

            # ─────────────────────────────────────────────────────────────
            # 13. Complete Goal
            # ─────────────────────────────────────────────────────────────
            elif action in ("complete_goal", "complete"):
                identifier = params.get("goal_id") or params.get("id")
                force = bool(params.get("force", False))
                goal = self._find_goal_by_identifier(engine, identifier)
                if not goal:
                    return SkillResult(
                        success=False,
                        message="Goal not found",
                        output_text=f"Could not find goal to complete: '{identifier}'.",
                    )
                completed = engine.complete_goal(goal.goal_id, force=force)
                return SkillResult(
                    success=True,
                    data={"goal": completed.to_dict()},
                    message=f"Goal '{completed.title}' completed.",
                    output_text=f"🎉 Goal **{completed.title}** (`{completed.goal_id}`) has been marked `COMPLETED`.",
                )

            # ─────────────────────────────────────────────────────────────
            # 14. Cancel Goal
            # ─────────────────────────────────────────────────────────────
            elif action in ("cancel_goal", "cancel"):
                identifier = params.get("goal_id") or params.get("id")
                preserve_children = params.get("preserve_children", True)
                goal = self._find_goal_by_identifier(engine, identifier)
                if not goal:
                    return SkillResult(
                        success=False,
                        message="Goal not found",
                        output_text=f"Could not find goal to cancel: '{identifier}'.",
                    )
                cancelled = engine.cancel_goal(goal.goal_id, preserve_children=preserve_children)
                return SkillResult(
                    success=True,
                    data={"goal": cancelled.to_dict()},
                    message=f"Goal '{cancelled.title}' cancelled.",
                    output_text=f"Goal **{cancelled.title}** (`{cancelled.goal_id}`) has been `CANCELLED`.",
                )

            else:
                return SkillResult(
                    success=False,
                    message=f"Unsupported action: '{action}'",
                    output_text=f"I don't know how to perform action '{action}' on goals.",
                )

        except PermissionError as pe:
            logger.warning(f"GoalSkill mutation authorization denied: {pe}")
            return SkillResult(
                success=False,
                message=str(pe),
                output_text=f"🔒 Permission Denied: {pe}",
            )
        except GoalValidationError as ve:
            logger.warning(f"GoalSkill validation error: {ve}")
            return SkillResult(
                success=False,
                message=str(ve),
                output_text=f"Validation Error: {ve}",
            )
        except IOError as ioe:
            logger.error(f"GoalSkill persistence failure: {ioe}")
            return SkillResult(
                success=False,
                message=str(ioe),
                output_text=f"Storage Failure: {ioe}",
            )
        except Exception as e:
            logger.error(f"Unexpected error in GoalSkill: {e}", exc_info=True)
            return SkillResult(
                success=False,
                message=str(e),
                output_text=f"An error occurred while managing goals: {e}",
            )
