import time
import logging
from typing import List, Dict, Any, Optional
from .agent_registry import AgentRegistry
from .base_agent import BaseAgent
from .agent_models import AgentTaskContext, AgentResult, AgentStatus

logger = logging.getLogger("JARVIS.MultiAgentCoordinator")


class MultiAgentCoordinator:
    """
    Coordinates execution of multi-agent intelligence pipelines under strict governance:
    - Maximum active agents per task (default: 4)
    - Maximum delegation depth (default: 2) to prevent runaway recursion
    - Execution timeout enforcement
    - Safe partial failure synthesis (never crashes if one agent fails)
    - Global cancellation support
    """

    def __init__(
        self,
        registry: AgentRegistry,
        event_bus: Optional[Any] = None,
        security: Optional[Any] = None,
        tools: Optional[Any] = None,
        model_router: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
        max_agents_per_task: Optional[int] = None,
        max_depth: Optional[int] = None,
        default_timeout: Optional[float] = None
    ):
        self.registry = registry
        self.event_bus = event_bus
        self.security = security
        self.tools = tools
        self.model_router = model_router
        self.config = config or {}

        self.max_agents_per_task = max_agents_per_task or self.config.get("max_agents_per_task", 4)
        self.max_depth = max_depth or self.config.get("max_depth", 2)
        self.default_timeout = default_timeout or self.config.get("agent_timeout_seconds", 30.0)
        self._cancelled = False

    def cancel(self):
        """Cancels all currently running agent workflows."""
        self._cancelled = True
        self.registry.cancel_all()
        logger.warning("[COORDINATOR] Multi-agent execution cancelled.")

    def reset_cancellation(self):
        """Resets cancellation flag for future tasks."""
        self._cancelled = False
        for a in self.registry._agents.values():
            a.reset_cancellation()

    def execute_pipeline(
        self,
        agent_ids: List[str],
        task_context: AgentTaskContext
    ) -> Dict[str, Any]:
        """
        Executes a sequence of specialized agents, enforcing depth limits,
        tool restrictions, and partial result preservation.
        """
        self._cancelled = False
        start_time = time.time()
        results: List[AgentResult] = []
        overall_findings: List[str] = []

        # 1. Enforce recursion limit
        if task_context.delegation_depth > self.max_depth:
            logger.error(f"[COORDINATOR] Delegation depth limit exceeded: {task_context.delegation_depth} > {self.max_depth}")
            return {
                "success": False,
                "status": "depth_exceeded",
                "summary": f"Delegation depth limit ({self.max_depth}) exceeded. Recursive agent invocation blocked.",
                "agent_results": [],
                "execution_time": round(time.time() - start_time, 3)
            }

        # 2. Limit maximum agents
        target_ids = agent_ids[:self.max_agents_per_task]
        context_accumulator = task_context.user_goal

        for aid in target_ids:
            if self._cancelled:
                results.append(AgentResult(
                    success=False,
                    agent_id=aid,
                    task_id=task_context.task_id,
                    status=AgentStatus.CANCELLED,
                    summary="Execution cancelled by user."
                ))
                break

            agent = self.registry.get_agent(aid)
            if not agent:
                logger.warning(f"[COORDINATOR] Agent '{aid}' is not registered or unavailable.")
                results.append(AgentResult(
                    success=False,
                    agent_id=aid,
                    task_id=task_context.task_id,
                    status=AgentStatus.UNAVAILABLE,
                    summary=f"Agent '{aid}' is unavailable.",
                    errors=[f"Agent '{aid}' not registered."]
                ))
                continue

            # Pass bounded context
            step_ctx = AgentTaskContext(
                task_id=f"{task_context.task_id}_{aid}",
                user_goal=context_accumulator,
                input_data=task_context.input_data,
                relevant_context=task_context.relevant_context,
                privacy_policy=task_context.privacy_policy,
                timeout_seconds=task_context.timeout_seconds,
                delegation_depth=task_context.delegation_depth,
                max_depth=self.max_depth,
                internet_available=task_context.internet_available,
                local_llm_available=task_context.local_llm_available
            )

            try:
                res = agent.execute(step_ctx)
                results.append(res)
                if res.success:
                    overall_findings.extend(res.findings)
                    context_accumulator += f"\n[{agent.name} Output]: {res.summary}"
            except Exception as e:
                logger.error(f"[COORDINATOR] Error executing agent '{aid}': {e}", exc_info=True)
                results.append(AgentResult(
                    success=False,
                    agent_id=aid,
                    task_id=task_context.task_id,
                    status=AgentStatus.FAILED,
                    summary=f"Execution error in {aid}: {str(e)}",
                    errors=[str(e)]
                ))

        # 3. Synthesize final response
        successful = [r for r in results if r.success]
        synthesis = self._synthesize_results(task_context.user_goal, results)

        return {
            "success": len(successful) > 0,
            "status": "completed" if len(successful) == len(results) else ("partial" if successful else "failed"),
            "summary": synthesis,
            "findings": overall_findings,
            "agent_results": [r.to_dict() for r in results],
            "execution_time": round(time.time() - start_time, 3)
        }

    async def execute_workflow(
        self,
        task: str,
        agent_ids: List[str],
        category: str = "general",
        session_id: str = "default",
        timeout: Optional[float] = None,
        offline_mode: bool = False,
        delegation_depth: int = 1
    ) -> Dict[str, Any]:
        """
        Asynchronous entry point for executing a multi-agent workflow.
        Integrates with asyncio timeouts, event bus telemetry, and depth enforcement.
        """
        actual_timeout = timeout if timeout is not None else self.default_timeout

        task_context = AgentTaskContext(
            user_goal=task,
            timeout_seconds=actual_timeout,
            delegation_depth=delegation_depth,
            max_depth=self.max_depth,
            internet_available=not offline_mode
        )

        # Emit telemetry if event bus is available
        if self.event_bus:
            try:
                await self.event_bus.publish("multi_agent_workflow_start", {
                    "task": task,
                    "agents": agent_ids,
                    "category": category,
                    "session_id": session_id,
                    "depth": delegation_depth
                })
            except Exception as e:
                logger.debug(f"Event bus publish error: {e}")

        # Depth check
        if delegation_depth > self.max_depth:
            msg = f"Multi-agent delegation depth {delegation_depth} exceeds safety threshold ({self.max_depth})."
            logger.error(f"[COORDINATOR] {msg}")
            return {
                "success": False,
                "status": "recursion_limit_exceeded",
                "synthesis": msg,
                "results": {},
                "errors": {"depth": msg},
                "execution_time": 0.0
            }

        start_t = time.time()
        results_map: Dict[str, Any] = {}
        errors_map: Dict[str, str] = {}

        try:
            import asyncio
            target_ids = agent_ids[:self.max_agents_per_task]

            for aid in target_ids:
                if self._cancelled:
                    return {
                        "success": False,
                        "status": "cancelled",
                        "synthesis": "Multi-agent workflow was cancelled by user.",
                        "results": results_map,
                        "errors": errors_map,
                        "execution_time": round(time.time() - start_t, 3)
                    }

                agent = self.registry.get_agent(aid)
                if not agent:
                    err_msg = f"Agent '{aid}' not found or inactive."
                    errors_map[aid] = err_msg
                    continue

                agent_ctx = AgentTaskContext(
                    task_id=f"{task_context.task_id}_{aid}",
                    user_goal=task,
                    timeout_seconds=actual_timeout,
                    delegation_depth=delegation_depth,
                    max_depth=self.max_depth,
                    internet_available=not offline_mode
                )

                # Execute with remaining timeout
                remaining_time = max(0.1, actual_timeout - (time.time() - start_t))
                try:
                    # Run execute in thread if synchronous or directly if coroutine
                    import inspect
                    if inspect.iscoroutinefunction(agent.execute):
                        res: AgentResult = await asyncio.wait_for(agent.execute(agent_ctx), timeout=remaining_time)
                    else:
                        res: AgentResult = await asyncio.wait_for(
                            asyncio.to_thread(agent.execute, agent_ctx),
                            timeout=remaining_time
                        )

                    if res.status == AgentStatus.CANCELLED:
                        return {
                            "success": False,
                            "status": "cancelled",
                            "synthesis": "Multi-agent workflow was cancelled by user.",
                            "results": results_map,
                            "errors": errors_map,
                            "execution_time": round(time.time() - start_t, 3)
                        }

                    if res.success:
                        results_map[aid] = res.to_dict()
                    else:
                        errors_map[aid] = res.summary or "Agent failed."
                except asyncio.TimeoutError:
                    return {
                        "success": False,
                        "status": "timeout",
                        "synthesis": f"Multi-agent task timed out after {actual_timeout}s.",
                        "results": results_map,
                        "errors": {aid: "Timed out"},
                        "execution_time": round(time.time() - start_t, 3)
                    }
                except Exception as ex:
                    errors_map[aid] = str(ex)

            # Synthesize results
            success_count = len(results_map)
            overall_success = success_count > 0 or (len(agent_ids) == 0)

            # Build readable synthesis
            synthesis_parts = []
            for aid, r in results_map.items():
                if aid == "research_agent":
                    synthesis_parts.append(f"Research Findings: {r.get('summary', '')}")
                elif aid == "analysis_agent":
                    synthesis_parts.append(f"Analysis & Comparison: {r.get('summary', '')}")
                elif aid == "planning_agent":
                    synthesis_parts.append(f"Plan Summary: {r.get('summary', '')}")
                elif aid == "coding_agent":
                    synthesis_parts.append(f"Coding Diagnosis: {r.get('summary', '')}")
                elif aid == "system_agent":
                    synthesis_parts.append(f"System State: {r.get('summary', '')}")
                elif aid == "productivity_agent":
                    synthesis_parts.append(f"Productivity Schedule: {r.get('summary', '')}")
                else:
                    synthesis_parts.append(f"{aid}: {r.get('summary', '')}")

            if errors_map:
                synthesis_parts.append(f"Limited capabilities reported for: {', '.join(errors_map.keys())}.")

            final_synthesis = " ".join(synthesis_parts) if synthesis_parts else "Multi-agent task completed with no output."

            res_status = "completed" if (overall_success and not errors_map) else ("partial" if overall_success else "failed")

            return {
                "success": overall_success,
                "status": res_status,
                "synthesis": final_synthesis,
                "results": results_map,
                "errors": errors_map,
                "execution_time": round(time.time() - start_t, 3)
            }

        except Exception as outer_e:
            logger.error(f"[COORDINATOR] Fatal error in workflow execution: {outer_e}", exc_info=True)
            return {
                "success": False,
                "status": "error",
                "synthesis": f"Workflow failed: {str(outer_e)}",
                "results": results_map,
                "errors": {"fatal": str(outer_e)},
                "execution_time": round(time.time() - start_t, 3)
            }
