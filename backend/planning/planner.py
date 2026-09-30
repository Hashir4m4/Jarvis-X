import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple
import json

from .models import (
    TaskPlan, TaskStep, PlanStatus, StepStatus,
    RiskLevel, RetryPolicy, ApprovalMode
)
from .analyzer import PlanAnalyzer
from backend.core.models import TaskCategory

logger = logging.getLogger("JARVIS.TaskPlanner")

COMPLEX_PLANNING_TRIGGERS = [
    "research and compare", "and create a report", "and save a report",
    "roadmap", "development plan", "multi-step", "workflow", "decompose",
    "analyze and fix", "compare and recommend", "download and extract", "build and test"
]

SIMPLE_BYPASS_TRIGGERS = [
    "open chrome", "open notepad", "what time is it", "what's the time",
    "cpu usage", "battery status", "set volume", "take a screenshot", "mute volume"
]

class TaskPlanner:
    def __init__(
        self, analyzer: Optional[PlanAnalyzer] = None,
        llm_client: Optional[Any] = None, config: Optional[Dict[str, Any]] = None
    ):
        self.analyzer = analyzer or PlanAnalyzer()
        self.llm = llm_client
        self.config = config or {}
        self.max_plan_steps = self.config.get("max_plan_steps", 10)

    def should_plan(self, goal: str, category: Optional[TaskCategory] = None) -> bool:
        g = goal.lower().strip()
        for bypass in SIMPLE_BYPASS_TRIGGERS:
            if bypass in g: return False
        if category in (TaskCategory.COMPUTER_ACTION, TaskCategory.COMMAND) and " and " not in g:
            return False
        for trigger in COMPLEX_PLANNING_TRIGGERS:
            if trigger in g: return True
        if category in (TaskCategory.PLANNING_TASK, TaskCategory.MULTI_STEP_TASK): return True
        if " and " in g and any(v in g for v in ("save", "report", "compare", "test", "deploy")): return True
        return False

    def create_plan(
        self, goal: str, category: Optional[TaskCategory] = None,
        approval_mode: ApprovalMode = ApprovalMode.REQUIRE_RISKY_STEP_APPROVAL,
        offline_mode: bool = False
    ) -> TaskPlan:
        plan_id = f"plan_{uuid.uuid4().hex[:8]}"
        plan = TaskPlan(plan_id=plan_id, goal=goal, status=PlanStatus.PLANNING, approval_mode=approval_mode)
        steps = self._decompose_goal_into_steps(goal, offline_mode)
        plan.steps = steps[:self.max_plan_steps]
        plan.dependencies = {s.step_id: list(s.dependencies) for s in plan.steps}
        is_valid, errors = self.analyzer.validate_plan(plan, offline_mode=offline_mode)
        if not is_valid:
            plan.status = PlanStatus.FAILED
            plan.metadata["validation_errors"] = errors
            logger.warning(f"[TASK_PLANNER] Plan creation validation failed: {errors}")
        else:
            plan.status = PlanStatus.READY
        return plan

    def _decompose_goal_into_steps(self, goal: str, offline_mode: bool) -> List[TaskStep]:
        if not self.llm or offline_mode:
            return self._fallback_decomposition(goal)
        prompt = f'''You are an autonomous task planner. The user wants to achieve this goal:
"{goal}"
Decompose this goal into a list of atomic, actionable steps.
Output ONLY valid JSON matching this schema:
{{
  "steps": [
    {{
      "step_id": "string (unique)",
      "description": "string",
      "action_type": "string (e.g. read_file, search_web, execute_code)",
      "required_tool": "string (optional tool name)",
      "required_agent": "string (optional agent name)",
      "dependencies": ["list of step_ids"],
      "input_data": {{}},
      "expected_output": "string"
    }}
  ]
}}
Do NOT output any markdown, only raw JSON.
'''
        try:
            response = self.llm.chat_sync([{"role": "user", "content": prompt}])
            data = json.loads(response)
            steps = []
            for s in data.get("steps", []):
                steps.append(TaskStep(
                    step_id=s.get("step_id", f"step_{uuid.uuid4().hex[:4]}"),
                    description=s.get("description", "Unknown task"),
                    action_type=s.get("action_type", "custom"),
                    required_tool=s.get("required_tool"),
                    required_agent=s.get("required_agent"),
                    dependencies=s.get("dependencies", []),
                    input_data=s.get("input_data", {}),
                    expected_output=s.get("expected_output", ""),
                    risk_level=RiskLevel.LOW
                ))
            if steps: return steps
        except Exception as e:
            logger.error(f"[TASK_PLANNER] LLM decomposition failed: {e}")
        return self._fallback_decomposition(goal)

    def _fallback_decomposition(self, goal: str) -> List[TaskStep]:
        s1 = TaskStep(
            step_id="step_1_research",
            description=f"Evaluate requirements for: '{goal}'",
            action_type="research",
            required_agent="planning_agent",
            dependencies=[],
            risk_level=RiskLevel.LOW
        )
        s2 = TaskStep(
            step_id="step_2_execute",
            description=f"Execute core actions for: '{goal}'",
            action_type="execute",
            required_agent="system_agent",
            dependencies=["step_1_research"],
            risk_level=RiskLevel.LOW
        )
        s3 = TaskStep(
            step_id="step_3_verify",
            description=f"Verify completion of: '{goal}'",
            action_type="verify",
            required_agent="system_agent",
            dependencies=["step_2_execute"],
            risk_level=RiskLevel.LOW
        )
        return [s1, s2, s3]

    def modify_plan(
        self, plan: TaskPlan, added_steps: Optional[List[TaskStep]] = None,
        removed_step_ids: Optional[List[str]] = None, offline_mode: bool = False
    ) -> Tuple[bool, List[str]]:
        if removed_step_ids:
            plan.steps = [s for s in plan.steps if s.step_id not in removed_step_ids]
        if added_steps:
            plan.steps.extend(added_steps)
        plan.dependencies = {s.step_id: list(s.dependencies) for s in plan.steps}
        is_valid, errors = self.analyzer.validate_plan(plan, offline_mode=offline_mode)
        if not is_valid:
            plan.status = PlanStatus.FAILED
            logger.warning(f"[TASK_PLANNER] Modified plan validation failed: {errors}")
        else:
            plan.status = PlanStatus.READY
            logger.info(f"[TASK_PLANNER] Plan '{plan.plan_id}' successfully modified and re-validated.")
        return is_valid, errors
