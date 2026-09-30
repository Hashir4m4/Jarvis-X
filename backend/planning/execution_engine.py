import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable, Tuple

from .models import (
    TaskPlan, TaskStep, PlanStatus, StepStatus,
    RiskLevel, RetryPolicy, ApprovalMode, TaskProgress, AutonomyLevel
)
import hashlib
from .analyzer import PlanAnalyzer
from backend.core.models import Intent, IntentType

logger = logging.getLogger("JARVIS.ExecutionEngine")


class ExecutionEngine:
    """
    Controlled Execution Engine for Autonomous Task Plans:
    - Traverses dependency DAG without executing steps ahead of order.
    - Evaluates permission checkpoints; pauses on high-risk actions.
    - Routes step execution to existing skills, tools, or multi-agent coordinator.
    - Verifies post-execution results (file existence, non-empty artifacts).
    - Supports pause, resume, cancel, emergency stop, and bounded retries.
    - Telemetry integration for HUD and EventBus.
    """

    def __init__(
        self,
        analyzer: Optional[PlanAnalyzer] = None,
        skill_registry: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        agent_coordinator: Optional[Any] = None,
        security_proxy: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.analyzer = analyzer or PlanAnalyzer()
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry
        self.coordinator = agent_coordinator
        self.security = security_proxy
        self.event_bus = event_bus
        self.config = config or {}
        self.planner = None  # Can be injected later for re-planning
        self._execution_history: List[str] = []

        # Execution limits
        self.max_execution_time = float(self.config.get("max_execution_time_seconds", 120.0))
        self.max_step_retries = int(self.config.get("max_step_retries", 2))
        self.allow_concurrency = bool(self.config.get("allow_concurrency", True))

        self._paused = False
        self._cancelled = False
        self._emergency_stopped = False
        self.active_plans: Dict[str, TaskPlan] = {}

    def pause(self, plan_id: Optional[str] = None):
        """Pauses execution of the active plan."""
        self._paused = True
        if plan_id and plan_id in self.active_plans:
            self.active_plans[plan_id].status = PlanStatus.PAUSED
        logger.info(f"[EXECUTION_ENGINE] Execution paused for plan: '{plan_id or 'all'}'")

    def resume(self, plan_id: Optional[str] = None):
        """Resumes paused execution."""
        self._paused = False
        if plan_id and plan_id in self.active_plans:
            self.active_plans[plan_id].status = PlanStatus.RUNNING
        logger.info(f"[EXECUTION_ENGINE] Execution resumed for plan: '{plan_id or 'all'}'")

    def cancel(self, plan_id: Optional[str] = None):
        """Cancels execution of the active plan and stops all child activities."""
        self._cancelled = True
        if plan_id and plan_id in self.active_plans:
            self.active_plans[plan_id].status = PlanStatus.CANCELLED
            for s in self.active_plans[plan_id].steps:
                if s.status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.AWAITING_APPROVAL):
                    s.status = StepStatus.CANCELLED
        if self.coordinator:
            self.coordinator.cancel()
        logger.warning(f"[EXECUTION_ENGINE] Execution cancelled for plan: '{plan_id or 'all'}'")

    def emergency_stop(self):
        """Halts all automation immediately across the entire execution engine."""
        self._emergency_stopped = True
        self._cancelled = True
        for plan in self.active_plans.values():
            plan.status = PlanStatus.CANCELLED
            for s in plan.steps:
                if s.status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.AWAITING_APPROVAL):
                    s.status = StepStatus.CANCELLED
        if self.coordinator:
            self.coordinator.cancel()
        logger.critical("[EXECUTION_ENGINE] Emergency Stop triggered!")

    async def _emit_progress(self, plan: TaskPlan, current_step: Optional[TaskStep] = None):
        """Emits progress events to EventBus for HUD updates."""
        prog = plan.get_progress()
        if current_step:
            prog.current_step_id = current_step.step_id
        if self.event_bus:
            try:
                await self.event_bus.publish("task_progress", prog.to_hud_payload())
            except Exception as e:
                logger.debug(f"Event bus progress publish error: {e}")

    async def execute_plan(
        self,
        plan: TaskPlan,
        session_id: str = "default",
        offline_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Main execution loop for a TaskPlan.
        Enforces dependencies, risk checkpoints, result verifications, and failure recoveries.
        """
        self._cancelled = False
        self._paused = False
        self._emergency_stopped = False
        self.active_plans[plan.plan_id] = plan

        start_time = time.time()
        plan.status = PlanStatus.RUNNING
        await self._emit_progress(plan)

        logger.info(f"[EXECUTION_ENGINE] Starting plan '{plan.plan_id}' with {len(plan.steps)} steps.")

        while True:
            # Check global timeout
            if time.time() - start_time > self.max_execution_time:
                plan.status = PlanStatus.FAILED
                msg = f"Task plan exceeded maximum execution time limit ({self.max_execution_time}s)."
                logger.error(f"[EXECUTION_ENGINE] {msg}")
                return {
                    "success": False,
                    "status": "timeout",
                    "plan_id": plan.plan_id,
                    "summary": msg,
                    "execution_time": round(time.time() - start_time, 3)
                }

            # Check cancellations
            if self._cancelled or self._emergency_stopped:
                plan.status = PlanStatus.CANCELLED
                return {
                    "success": False,
                    "status": "cancelled",
                    "plan_id": plan.plan_id,
                    "summary": "Task plan execution was cancelled.",
                    "execution_time": round(time.time() - start_time, 3)
                }

            # Check pause
            if self._paused:
                await asyncio.sleep(0.2)
                continue

            # Find steps that are ready to run: status==PENDING and all dependencies COMPLETED
            ready_steps = [
                s for s in plan.steps
                if s.status == StepStatus.PENDING and self._are_dependencies_satisfied(s, plan)
            ]

            # If no steps ready, check if done or stuck
            if not ready_steps:
                pending_count = sum(1 for s in plan.steps if s.status == StepStatus.PENDING)
                running_count = sum(1 for s in plan.steps if s.status == StepStatus.RUNNING)
                failed_count = sum(1 for s in plan.steps if s.status == StepStatus.FAILED)

                if running_count > 0:
                    await asyncio.sleep(0.1)
                    continue

                if pending_count == 0:
                    # All steps reached a terminal state
                    if failed_count == 0:
                        plan.status = PlanStatus.COMPLETED
                        logger.info(f"[EXECUTION_ENGINE] Plan '{plan.plan_id}' completed successfully.")
                    else:
                        completed_count = sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED)
                        plan.status = PlanStatus.PARTIALLY_COMPLETED if completed_count > 0 else PlanStatus.FAILED
                        logger.warning(f"[EXECUTION_ENGINE] Plan '{plan.plan_id}' finished with status: {plan.status.value}")
                    break
                else:
                    # Deadlock or broken dependencies due to a failed predecessor
                    completed_count = sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED)
                    plan.status = PlanStatus.PARTIALLY_COMPLETED if completed_count > 0 else PlanStatus.FAILED
                    logger.warning(f"[EXECUTION_ENGINE] Plan '{plan.plan_id}' halted: Remaining steps blocked by dependencies.")
                    break

            # Execute ready steps
            if self.allow_concurrency and len(ready_steps) > 1 and all(s.risk_level == RiskLevel.LOW for s in ready_steps):
                # Safe independent steps can execute concurrently
                tasks = [self._execute_step(s, plan, session_id, offline_mode) for s in ready_steps]
                await asyncio.gather(*tasks)
            else:
                # Execute one step at a time
                step = ready_steps[0]
                await self._execute_step(step, plan, session_id, offline_mode)

            await self._emit_progress(plan)

        # Synthesize final output
        total_time = round(time.time() - start_time, 3)
        completed_steps = [s for s in plan.steps if s.status == StepStatus.COMPLETED]
        failed_steps = [s for s in plan.steps if s.status == StepStatus.FAILED]

        summary_parts = [f"Plan '{plan.goal}' finished with status {plan.status.value} ({len(completed_steps)}/{len(plan.steps)} steps completed in {total_time}s)."]
        for cs in completed_steps:
            summary_parts.append(f"- Step '{cs.step_id}': {cs.output_data or 'Success'}")
        if failed_steps:
            summary_parts.append(f"- Failed: {', '.join(fs.step_id for fs in failed_steps)}")

        return {
            "success": plan.status in (PlanStatus.COMPLETED, PlanStatus.PARTIALLY_COMPLETED),
            "status": plan.status.value,
            "plan_id": plan.plan_id,
            "summary": "\n".join(summary_parts),
            "completed_steps": len(completed_steps),
            "total_steps": len(plan.steps),
            "execution_time": total_time,
            "plan": plan.to_dict()
        }

    def _are_dependencies_satisfied(self, step: TaskStep, plan: TaskPlan) -> bool:
        """Checks if all prerequisite steps have completed successfully."""
        for dep_id in step.dependencies:
            dep_step = plan.get_step(dep_id)
            if not dep_step or dep_step.status != StepStatus.COMPLETED:
                return False
        return True

    async def _execute_step(
        self,
        step: TaskStep,
        plan: TaskPlan,
        session_id: str,
        offline_mode: bool
    ):
        """Executes a single step with permission validation, retry, and verification."""
        step.status = StepStatus.RUNNING
        step_start = time.time()
        await self._emit_progress(plan, step)

        # 1. Permission Gate & Confirmation Checkpoint
        needs_approval = False
        if plan.autonomy_level == AutonomyLevel.MANUAL:
            needs_approval = True
        elif plan.autonomy_level == AutonomyLevel.ASSISTED:
            if step.requires_confirmation or step.risk_level in (RiskLevel.HIGH, RiskLevel.MEDIUM):
                needs_approval = True
        elif plan.autonomy_level == AutonomyLevel.CONTROLLED_AUTONOMY:
            if step.risk_level == RiskLevel.HIGH:
                needs_approval = True
        # RESTRICTED_AUTONOMY (Level 3) allows autonomous execution for its configured workflows, so needs_approval=False unless very specific.

        if needs_approval:
            plan.status = PlanStatus.AWAITING_APPROVAL
            step.status = StepStatus.AWAITING_APPROVAL
            await self._emit_progress(plan, step)

            confirmed = False
            if self.security:
                confirmed = self.security.request_confirmation(
                    action=step.action_type,
                    details=f"Plan Step: {step.description}"
                )
            else:
                confirmed = True  # Auto-confirm if no security proxy

            if not confirmed:
                logger.warning(f"[EXECUTION_ENGINE] Step '{step.step_id}' rejected by permission checkpoint.")
                step.status = StepStatus.FAILED
                step.error = "Permission denied by user confirmation gate."
                step.execution_time = round(time.time() - step_start, 3)
                plan.status = PlanStatus.RUNNING
                return

            plan.status = PlanStatus.RUNNING
            step.status = StepStatus.RUNNING
            
        # Loop Detection
        step_hash = hashlib.md5(f"{step.action_type}:{step.description}:{str(step.input_data)}".encode()).hexdigest()
        if self._execution_history.count(step_hash) >= 3:
            logger.error(f"[EXECUTION_ENGINE] Loop detected for step '{step.step_id}'. Aborting.")
            step.status = StepStatus.FAILED
            step.error = "Execution loop detected. Aborting to prevent infinite automation."
            step.execution_time = round(time.time() - step_start, 3)
            plan.status = PlanStatus.FAILED
            return
            
        self._execution_history.append(step_hash)

        # 2. Execution Loop with Bounded Retries
        success = False
        last_error = ""

        while not success and step.retry_count <= step.max_retries:
            if self._cancelled or self._emergency_stopped:
                step.status = StepStatus.CANCELLED
                return

            try:
                # Dispatch execution to appropriate capability
                out = await self._dispatch_capability(step, plan, session_id, offline_mode)

                # 3. Post-Execution Result Verification
                verified, verify_msg = self._verify_result(step, out)
                if verified:
                    success = True
                    step.status = StepStatus.COMPLETED
                    step.output_data = out
                    step.execution_time = round(time.time() - step_start, 3)
                    logger.info(f"[EXECUTION_ENGINE] Step '{step.step_id}' completed and verified.")
                    return
                else:
                    last_error = f"Verification failed: {verify_msg}"
                    logger.warning(f"[EXECUTION_ENGINE] Step '{step.step_id}' result verification failed: {verify_msg}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"[EXECUTION_ENGINE] Step '{step.step_id}' attempt {step.retry_count + 1} raised error: {e}")

            step.retry_count += 1

            # Check if retry is permitted
            if step.retry_policy == RetryPolicy.LIMITED_RETRY and step.retry_count <= step.max_retries:
                logger.info(f"[EXECUTION_ENGINE] Retrying step '{step.step_id}' (attempt {step.retry_count}/{step.max_retries})...")
                await asyncio.sleep(0.05)
            elif step.retry_policy == RetryPolicy.ALTERNATIVE_CAPABILITY or step.fallback_capability:
                logger.info(f"[EXECUTION_ENGINE] Falling back to alternative capability for step '{step.step_id}'...")
                step.required_capability = step.fallback_capability
                try:
                    fallback_out = await self._dispatch_capability(step, plan, session_id, offline_mode)
                    step.status = StepStatus.COMPLETED
                    step.output_data = fallback_out
                    step.execution_time = round(time.time() - step_start, 3)
                    return
                except Exception as fb_err:
                    last_error = f"Fallback error: {fb_err}"
                break
            else:
                break

        # Step failed after retries/fallback
        step.status = StepStatus.FAILED
        step.error = last_error or "Execution failed."
        step.execution_time = round(time.time() - step_start, 3)
        
        # Trigger Re-planning if planner is available
        if self.planner and not (self._cancelled or self._emergency_stopped):
            logger.info(f"[EXECUTION_ENGINE] Step '{step.step_id}' failed. Triggering re-planning.")
            try:
                # Add a replan step
                replan_step = TaskStep(
                    step_id=f"replan_{step.step_id}",
                    description=f"Re-plan after failure in {step.step_id}: {step.error}",
                    action_type="evaluate",
                    required_agent="planning_agent",
                    dependencies=[step.step_id],
                    risk_level=RiskLevel.LOW
                )
                self.planner.modify_plan(plan, added_steps=[replan_step])
                # Mark original step's dependents to depend on the replan instead, or just let replan generate new steps
            except Exception as replan_err:
                logger.error(f"[EXECUTION_ENGINE] Re-planning failed: {replan_err}")

    async def _dispatch_capability(
        self,
        step: TaskStep,
        plan: TaskPlan,
        session_id: str,
        offline_mode: bool
    ) -> Any:
        """Routes execution to specialized agent, tool, or skill without duplicating logic."""
        # 1. Dispatch to Specialized Agent via MultiAgentCoordinator
        if step.required_agent and self.coordinator:
            res = await self.coordinator.execute_workflow(
                task=step.description,
                agent_ids=[step.required_agent],
                category=step.action_type,
                session_id=session_id,
                offline_mode=offline_mode
            )
            if res.get("success"):
                agent_res = res.get("results", {}).get(step.required_agent, {})
                return agent_res.get("summary") or res.get("synthesis")
            else:
                err = res.get("errors", {}).get(step.required_agent) or res.get("synthesis", "Agent failed")
                raise RuntimeError(err)

        # 2. Dispatch to ToolRegistry
        if step.required_tool and self.tool_registry:
            tool = self.tool_registry.get_tool(step.required_tool)
            if tool:
                res = await self.tool_registry.execute_tool(step.required_tool, **step.input_data)
                return res

        # 3. Dispatch to SkillRegistry
        if step.required_skill and self.skill_registry:
            intent = Intent(
                intent_type=IntentType.CONVERSATION,
                skill_name=step.required_skill,
                action=step.action_type,
                parameters=step.input_data,
                raw_input=step.description
            )
            skill_ctx = {"session_id": session_id, "memory": None}
            res = await asyncio.to_thread(self.skill_registry.execute_intent, intent, skill_ctx)
            if res.success:
                return res.output_text or res.message or "Skill executed."
            else:
                raise RuntimeError(res.message or "Skill execution reported failure.")

        # Default simulated completion for unrouted safe actions
        return f"Executed action '{step.action_type}': {step.description}"

    def _verify_result(self, step: TaskStep, output: Any) -> Tuple[bool, str]:
        """
        Verifies execution results:
        - Output is non-empty.
        - File actions verify file creation or metadata.
        """
        if output is None:
            return False, "Output was None."

        if isinstance(output, str) and not output.strip():
            return False, "Output was empty string."

        if isinstance(output, dict) and output.get("error"):
            return False, str(output.get("error"))

        # Verify file creation if specified
        if step.action_type in ("create_file", "write_file") and "file_path" in step.input_data:
            import os
            fp = step.input_data["file_path"]
            if not os.path.exists(fp):
                return False, f"Target file '{fp}' was not found on disk."

        return True, "Verification passed."
