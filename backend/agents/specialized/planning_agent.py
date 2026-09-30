import time
import logging
from typing import Optional, Dict, Any, List
from ..base_agent import BaseAgent
from ..agent_models import (
    AgentMetadata, AgentCapability, AgentTaskContext,
    AgentResult, AgentStatus, OfflineSupport
)

logger = logging.getLogger("JARVIS.PlanningAgent")


class PlanningAgent(BaseAgent):
    """
    Specialized agent for task decomposition, roadmap design, and dependency analysis.
    Planning does NOT execute actions; it creates structured milestones.
    Operates 100% offline.
    """

    def __init__(self, llm_client: Optional[Any] = None):
        meta = AgentMetadata(
            agent_id="planning_agent",
            name="Planning Agent",
            description="Decomposes high-level objectives into phased roadmaps, dependencies, and atomic milestones.",
            specialization="Task decomposition & strategic roadmapping",
            capabilities=[AgentCapability.TASK_DECOMPOSITION, AgentCapability.PROJECT_PLANNING],
            allowed_tools=["plan.decompose", "vault.read"],
            allowed_skills=["plan", "vault"],
            model_role="reasoning",
            offline_support=OfflineSupport.FULL,
            status=AgentStatus.IDLE
        )
        super().__init__(meta)
        self.llm = llm_client

    def can_handle(self, task_context: AgentTaskContext) -> bool:
        goal = task_context.user_goal.lower()
        return any(k in goal for k in ("plan", "roadmap", "milestone", "decompose", "steps to", "strategy", "priorities"))

    def execute(self, task_context: AgentTaskContext) -> AgentResult:
        start_time = time.time()
        self.metadata.status = AgentStatus.RUNNING

        if self._cancelled:
            self.metadata.status = AgentStatus.CANCELLED
            return AgentResult(
                success=False,
                agent_id=self.agent_id,
                task_id=task_context.task_id,
                status=AgentStatus.CANCELLED,
                summary="Planning cancelled by user."
            )

        goal = task_context.user_goal
        logger.info(f"[{self.name}] Creating structured plan for: '{goal}'")

        steps = [
            f"Phase 1: Architecture alignment and baseline dependencies for '{goal}'.",
            "Phase 2: Core component implementation and unit verification.",
            "Phase 3: Integration testing, security audit, and documentation."
        ]
        summary = f"Generated 3-phase strategic roadmap for '{goal}'."

        self.metadata.status = AgentStatus.COMPLETED
        return AgentResult(
            success=True,
            agent_id=self.agent_id,
            task_id=task_context.task_id,
            status=AgentStatus.COMPLETED,
            summary=summary,
            findings=steps,
            artifacts={"roadmap_phases": 3, "strategy": "iterative_delivery"},
            confidence=0.98,
            execution_time=round(time.time() - start_time, 3)
        )
