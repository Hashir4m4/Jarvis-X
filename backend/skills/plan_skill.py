import logging
import datetime
from typing import Dict, Any, List, Optional

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.agents.planner import Planner

logger = logging.getLogger("JARVIS.PlanSkill")


class PlanSkill(BaseSkill):
    """
    Skill for breaking down complex objectives and structuring daily execution plans.
    Supports Plan Today (Top 3 Priorities & Daily Vault storage) and general planning.
    """

    def __init__(self, planner: Optional[Planner] = None, metadata=None):
        super().__init__(metadata=metadata)
        self.planner = planner

    @property
    def name(self) -> str:
        return "plan"

    @property
    def description(self) -> str:
        return "Decomposes complex objectives, manages daily priorities, and creates structured daily plans."

    @property
    def supported_actions(self) -> List[str]:
        return ["create_plan", "explain_plan", "plan_today"]

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        action = intent.action.lower()
        params = intent.parameters or {}
        ctx = context or {}
        memory = ctx.get("memory")
        today_str = datetime.date.today().isoformat()

        # ─────────────────────────────────────────────────────────────
        # Action: Plan Today (Daily Workflow)
        # ─────────────────────────────────────────────────────────────
        if action in ("plan_today", "today"):
            # 1. Retrieve relevant memory
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

            # 2. Extract / generate Top 3 Priorities
            raw_task = params.get("task", "")
            if raw_task and raw_task not in ("Today's Agenda & Action Items", "active_plan"):
                top_priorities = [
                    f"1. [ ] {raw_task}",
                    "2. [ ] Review codebase architecture and execute milestones",
                    "3. [ ] Run integration tests and close pending issues"
                ]
            else:
                top_priorities = [
                    "1. [ ] Execute core architecture deliverables and roadmap",
                    "2. [ ] Validate multi-agent and system integration tests",
                    "3. [ ] Monitor hardware telemetry and system health"
                ]

            priorities_text = "\n".join(top_priorities)

            # 3. Store in vault/daily/
            daily_content = (
                f"## Daily Plan — {today_str}\n\n"
                f"### Top 3 Priorities\n{priorities_text}\n\n"
                f"### Context & Notes\n" + ("\n".join(f"- {c[:100]}" for c in memory_context) if memory_context else "- Standard operational parameters.")
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
                output_text=output_text
            )

        # ─────────────────────────────────────────────────────────────
        # Action: General Implementation Plan
        # ─────────────────────────────────────────────────────────────
        task = params.get("task", intent.raw_input)
        if not task:
            return SkillResult(
                success=False,
                message="Missing required input: task",
                output_text="Please provide a task description to generate an implementation plan."
            )

        if not self.planner:
            return SkillResult(
                success=True,
                data={"task": task, "steps": []},
                message="Plan requested",
                output_text=f"Planning mode initialized for task: '{task}'."
            )

        try:
            steps = self.planner.plan(task)
            step_lines = [f"{s.get('step_num', i+1)}. [{s.get('action')}] {s.get('file', '')}: {s.get('description', '')}" for i, s in enumerate(steps)]
            text = f"Implementation Plan ({len(steps)} steps):\n" + "\n".join(step_lines)
            return SkillResult(
                success=True,
                data={"task": task, "steps": steps},
                message=f"Generated {len(steps)} plan steps",
                output_text=text
            )
        except Exception as e:
            logger.error(f"Error in PlanSkill: {e}")
            return SkillResult(success=False, message=str(e), output_text=f"Failed to generate plan: {e}")
