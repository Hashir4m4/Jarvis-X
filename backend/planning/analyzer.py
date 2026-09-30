import logging
from typing import Dict, Any, List, Set, Tuple, Optional

from .models import TaskPlan, TaskStep, RiskLevel, StepStatus, PlanStatus

logger = logging.getLogger("JARVIS.PlanAnalyzer")

# Action categories for risk assessment
LOW_RISK_KEYWORDS = {
    "read", "get", "search", "query", "analyze", "diagnose", "list", "check", "compare", "evaluate", "inspect"
}

MEDIUM_RISK_KEYWORDS = {
    "create_file", "create_folder", "write", "generate", "export", "move_file", "copy_file", "save"
}

HIGH_RISK_KEYWORDS = {
    "delete", "remove", "drop", "kill", "terminate", "shutdown", "restart",
    "modify_system", "execute_shell", "run_powershell", "run_cmd", "format",
    "send_external", "post_webhook", "bulk_delete"
}

MALICIOUS_PATTERNS = {
    "rm -rf", "format c:", "drop table", "chmod 777", "curl | bash",
    "wget | bash", "nc -e", "> /dev/tcp", "echo \\x", "exec(", "eval(",
    "../", "..\\", "bypass", "override", "ignore previous instructions",
    "delete all", "wipe", "upload them here"
}


class PlanValidationError(Exception):
    """Raised when a task plan fails safety or structural validation."""
    pass


class PlanAnalyzer:
    """
    Validates task plans before execution:
    1. Dependency graph cycle detection & topological ordering.
    2. Capability availability (skills, tools, agents).
    3. Granular risk assessment & permission tagging.
    4. Offline capability validation.
    """

    def __init__(
        self,
        skill_registry: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        agent_registry: Optional[Any] = None
    ):
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry
        self.agent_registry = agent_registry

    def validate_plan(
        self,
        plan: TaskPlan,
        offline_mode: bool = False
    ) -> Tuple[bool, List[str]]:
        """
        Runs comprehensive validation on a TaskPlan:
        - Checks non-empty steps
        - Validates all step dependencies exist
        - Checks for cycles in the dependency graph
        - Verifies required skills, tools, and agents
        - Enforces offline constraints
        Returns (is_valid, list_of_errors).
        """
        errors: List[str] = []

        if not plan.steps:
            errors.append("Task plan must contain at least one step.")
            return False, errors

        step_ids = {s.step_id for s in plan.steps}

        # 1. Validate dependencies exist
        for s in plan.steps:
            for dep in s.dependencies:
                if dep not in step_ids:
                    errors.append(f"Step '{s.step_id}' depends on non-existent step '{dep}'.")
                if dep == s.step_id:
                    errors.append(f"Step '{s.step_id}' cannot depend on itself.")

        # 2. Check for circular dependencies via Kahn's algorithm or DFS
        cycle_detected = self._has_cycle(plan)
        if cycle_detected:
            errors.append("Circular dependency detected in plan steps.")

        # 3. Validate capabilities & availability
        for s in plan.steps:
            cap_errors = self._validate_step_capabilities(s, offline_mode)
            errors.extend(cap_errors)

        # 4. Assess risk and assign confirmation checkpoints
        try:
            self.assess_risks(plan)
        except PlanValidationError as e:
            errors.append(str(e))

        is_valid = len(errors) == 0
        if not is_valid:
            logger.warning(f"[PLAN_ANALYZER] Plan '{plan.plan_id}' validation failed with {len(errors)} error(s): {errors}")
        else:
            plan.status = PlanStatus.READY
            logger.info(f"[PLAN_ANALYZER] Plan '{plan.plan_id}' passed validation successfully.")

        return is_valid, errors

    def _has_cycle(self, plan: TaskPlan) -> bool:
        """Detects cycles in the dependency graph using Depth-First Search."""
        adj: Dict[str, List[str]] = {s.step_id: list(s.dependencies) for s in plan.steps}
        visited: Dict[str, int] = {s.step_id: 0 for s in plan.steps}  # 0=unvisited, 1=visiting, 2=visited

        def dfs(node: str) -> bool:
            visited[node] = 1
            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    continue
                if visited[neighbor] == 1:
                    return True
                if visited[neighbor] == 0:
                    if dfs(neighbor):
                        return True
            visited[node] = 2
            return False

        for sid in plan.steps:
            if visited[sid.step_id] == 0:
                if dfs(sid.step_id):
                    return True
        return False

    def get_topological_order(self, plan: TaskPlan) -> List[str]:
        """
        Returns a valid topological ordering of step IDs.
        Raises PlanValidationError if a cycle exists.
        """
        in_degree: Dict[str, int] = {s.step_id: 0 for s in plan.steps}
        adj: Dict[str, List[str]] = {s.step_id: [] for s in plan.steps}

        for s in plan.steps:
            for dep in s.dependencies:
                if dep in adj:
                    adj[dep].append(s.step_id)
                    in_degree[s.step_id] += 1

        queue = [sid for sid, deg in in_degree.items() if deg == 0]
        order = []

        while queue:
            curr = queue.pop(0)
            order.append(curr)
            for nxt in adj.get(curr, []):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    queue.append(nxt)

        if len(order) != len(plan.steps):
            raise PlanValidationError("Cannot resolve topological order: Cycle detected.")

        return order

    def _validate_step_capabilities(self, step: TaskStep, offline_mode: bool) -> List[str]:
        """Checks if required skill, tool, or agent exists and is available."""
        errors: List[str] = []

        # Check Skill
        if step.required_skill and self.skill_registry:
            skill = self.skill_registry.get_skill(step.required_skill)
            if not skill:
                errors.append(f"Required skill '{step.required_skill}' for step '{step.step_id}' not found.")

        # Check Tool
        if step.required_tool and self.tool_registry:
            tool = self.tool_registry.get_tool(step.required_tool)
            if not tool:
                errors.append(f"Required tool '{step.required_tool}' for step '{step.step_id}' not found.")

        # Check Agent
        if step.required_agent and self.agent_registry:
            agent = self.agent_registry.get_agent(step.required_agent)
            if not agent:
                errors.append(f"Required agent '{step.required_agent}' for step '{step.step_id}' not found.")

        # Offline restrictions
        if offline_mode:
            live_terms = ["web_search", "web.search", "browser.search", "online", "live_crawl", "weather_live"]
            req_cap = (step.required_capability or "").lower()
            req_tool = (step.required_tool or "").lower()
            desc = (step.description or "").lower()

            if any(term in req_cap or term in req_tool or term in desc for term in live_terms):
                if not step.fallback_capability:
                    errors.append(f"Step '{step.step_id}' requires live internet access, which is unavailable in offline mode.")

        return errors

    def assess_risks(self, plan: TaskPlan):
        """
        Analyzes every step for risk, setting risk_level and requires_confirmation.
        Aggregates overall plan risk summary.
        """
        overall_risk = RiskLevel.LOW

        for step in plan.steps:
            text = f"{step.action_type} {step.description} {step.required_tool or ''} {step.input_data}".lower()

            # Security / Malicious Check
            if any(p in text for p in MALICIOUS_PATTERNS):
                raise PlanValidationError(f"Malicious or prohibited pattern detected in step '{step.step_id}'.")

            # High Risk Check
            if any(k in text for k in HIGH_RISK_KEYWORDS) or step.action_type in ("delete_file", "kill_process", "shutdown"):
                step.risk_level = RiskLevel.HIGH
                step.requires_confirmation = True
                overall_risk = RiskLevel.HIGH
            # Medium Risk Check
            elif any(k in text for k in MEDIUM_RISK_KEYWORDS) or step.action_type in ("write_file", "create_folder"):
                step.risk_level = RiskLevel.MEDIUM
                if overall_risk != RiskLevel.HIGH:
                    overall_risk = RiskLevel.MEDIUM
            else:
                step.risk_level = RiskLevel.LOW

        plan.risk_summary = overall_risk.value
