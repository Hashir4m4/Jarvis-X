import logging
import os
from typing import Dict, Any, List, Optional

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.agents.agent_manager import AgentManager

logger = logging.getLogger("JARVIS.CodingSkill")


class CodingSkill(BaseSkill):
    """
    Skill for autonomous multi-agent software engineering.
    Coordinates Planner -> Coder -> Reviewer -> Executor pipeline.
    """

    def __init__(self, agent_manager: Optional[AgentManager] = None, metadata=None):
        super().__init__(metadata=metadata)
        self.agent_mgr = agent_manager

    @property
    def name(self) -> str:
        return "coding"

    @property
    def description(self) -> str:
        return "Autonomous multi-agent software engineering pipeline (Planner -> Coder -> Reviewer -> Executor)."

    @property
    def supported_actions(self) -> List[str]:
        return ["run_task", "generate_code", "review_code", "run_code"]

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        action = intent.action.lower()
        params = intent.parameters or {}
        ctx = context or {}

        if not self.agent_mgr:
            return SkillResult(
                success=False,
                message="AgentManager not initialized",
                output_text="The Multi-Agent coding subsystem is currently offline."
            )

        try:
            if action in ("run_task", "execute_task"):
                task = params.get("task", intent.raw_input)
                repo_path = params.get("repo_path")
                timeout = params.get("timeout", 60.0)

                logger.info(f"[CodingSkill] Starting multi-agent pipeline for task: '{task}'")
                report = self.agent_mgr.run_task(task=task, repo_path=repo_path, timeout=timeout)

                status = report.get("status", "ok")
                steps = report.get("steps", [])
                step_summary = []
                for s in steps:
                    status_emoji = "✓" if s.get("status") in ("written", "tested", "executed") else "•"
                    step_summary.append(f"{status_emoji} Step {s.get('step_num')}: [{s.get('action')}] {s.get('file')} — {s.get('status')}")

                output_text = (
                    f"### Multi-Agent Coding Result ({status.upper()})\n"
                    f"**Task**: {task}\n\n"
                    f"**Execution Pipeline**:\n" + "\n".join(step_summary) + "\n\n"
                    f"*Total Execution Time: {report.get('execution_time_seconds', 0)}s*"
                )

                # If memory is in context, create an Obsidian report in vault/outputs/
                if "memory" in ctx and hasattr(ctx["memory"], "create_report"):
                    try:
                        ctx["memory"].create_report(
                            title=f"Coding Deliverable - {task[:40]}",
                            content=output_text,
                            report_type="code_generation",
                            tags=["coding", "multi_agent"]
                        )
                    except Exception as e:
                        logger.warning(f"Failed to write coding deliverable to vault: {e}")

                return SkillResult(
                    success=(status == "ok"),
                    data=report,
                    message=f"Completed {len(steps)} steps",
                    output_text=output_text
                )

            elif action == "generate_code":
                step_info = {"file": params.get("file", "script.py"), "description": params.get("task", intent.raw_input), "action": "CREATE"}
                code = self.agent_mgr.coder.generate(step_info)
                return SkillResult(
                    success=bool(code),
                    data={"code": code},
                    message="Code generated",
                    output_text=f"```python\n{code}\n```"
                )

            elif action == "review_code":
                code = params.get("code", "")
                filename = params.get("file", "snippet.py")
                review = self.agent_mgr.reviewer.review(filename, code, "Review code block")
                return SkillResult(
                    success=True,
                    data=review,
                    message="Code reviewed",
                    output_text=f"Review: Grade {review.get('grade', 'B')}. Feedback: {review.get('feedback', 'No issues')}"
                )

            elif action == "run_code":
                script = params.get("script", "")
                result = self.agent_mgr.executor.run_file(script, "python")
                return SkillResult(
                    success=(result.get("status") == "ok"),
                    data=result,
                    message="Script executed",
                    output_text=f"Execution output:\n{result.get('stdout', '')}"
                )

            else:
                return SkillResult(
                    success=False,
                    message=f"Unknown coding action: {action}",
                    output_text=f"Unknown coding action '{action}'."
                )

        except Exception as e:
            logger.error(f"Error executing CodingSkill ({action}): {e}", exc_info=True)
            return SkillResult(success=False, message=str(e), output_text=f"Multi-agent coding failure: {e}")
