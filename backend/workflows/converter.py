"""
JARVIS X — Workflow Conversion & Planning Bridge
Converts an approved LongHorizonPlan into an executable Workflow without auto-executing.
"""

import logging
from typing import Optional, Dict, Any, List
from backend.planning.long_horizon_models import LongHorizonPlan, PlanStatus, Milestone
from .models import Workflow, WorkflowStep, WorkflowStatus, ExecutionPolicy, ExecutionRiskLevel

logger = logging.getLogger("JARVIS.WorkflowConverter")


class PlanToWorkflowConverter:
    """
    Transforms approved strategic plans into structured workflows.
    Guarantees:
    - Only APPROVED or ACTIVE plans can be converted into workflows.
    - Preserves milestone sequence, dependencies, and risk evaluations.
    - Does NOT execute or trigger any workflows during conversion.
    """

    def __init__(self, capability_registry: Optional[Any] = None):
        self.capability_registry = capability_registry

    def convert(self, plan: LongHorizonPlan) -> Workflow:
        if not isinstance(plan, LongHorizonPlan):
            raise TypeError("Expected LongHorizonPlan instance for workflow conversion.")

        if plan.status not in (PlanStatus.APPROVED, PlanStatus.ACTIVE):
            raise ValueError(
                f"Cannot convert plan '{plan.plan_id}' with status '{plan.status.value}'. "
                "Only APPROVED or ACTIVE plans may be converted to executable workflows."
            )

        workflow_steps: List[WorkflowStep] = []

        # Sort milestones by sequence
        sorted_milestones = sorted(plan.milestones, key=lambda m: m.sequence)

        for ms in sorted_milestones:
            # Check risk level from milestone metadata or risk assessment
            exec_risk = ExecutionRiskLevel.LOW
            if hasattr(ms, "risk_assessment") and ms.risk_assessment:
                risk_obj = ms.risk_assessment
                if hasattr(risk_obj, "severity"):
                    sev = risk_obj.severity.value if hasattr(risk_obj.severity, "value") else str(risk_obj.severity)
                    if sev in ("HIGH", "CRITICAL"):
                        exec_risk = ExecutionRiskLevel.HIGH
            elif "risk_level" in ms.metadata:
                risk_str = ms.metadata["risk_level"]
                try:
                    exec_risk = ExecutionRiskLevel(risk_str)
                except ValueError:
                    exec_risk = ExecutionRiskLevel.LOW

            # Default policy: require approval for HIGH or CRITICAL
            requires_approval = exec_risk in (ExecutionRiskLevel.HIGH, ExecutionRiskLevel.CRITICAL)

            # Map to suitable default skill and action based on title / description
            skill_name, action, params = self._resolve_milestone_capability(ms, plan)

            step = WorkflowStep(
                step_id=f"step_{ms.milestone_id}",
                title=ms.title,
                skill_name=skill_name,
                action=action,
                parameters=params,
                dependencies=[f"step_{dep_id}" for dep_id in ms.dependencies],
                policy=ExecutionPolicy(
                    max_retries=2,
                    timeout_seconds=60.0,
                    backoff_multiplier=1.5,
                    requires_approval=requires_approval,
                    risk_level=exec_risk,
                ),
            )
            workflow_steps.append(step)

        current_rev = len(plan.revisions) if plan.revisions else 1
        plan_deadline = plan.metadata.get("deadline") or plan.metadata.get("target_date")

        workflow = Workflow(
            title=f"Workflow for: {plan.title}",
            description=f"Derived from approved strategic plan {plan.plan_id}",
            origin_plan_id=plan.plan_id,
            origin_goal_id=plan.linked_goal_id,
            steps=workflow_steps,
            status=WorkflowStatus.PENDING_APPROVAL,
            metadata={
                "converted_from_plan_revision": current_rev,
                "plan_deadline": plan_deadline,
                "critical_milestones": [f"step_{m_id}" for m_id in plan.critical_path.critical_milestones] if plan.critical_path else [],
            },
        )
        logger.info(f"Converted Plan '{plan.plan_id}' to Workflow '{workflow.workflow_id}' with {len(workflow.steps)} steps.")
        return workflow

    def _resolve_milestone_capability(self, ms: Milestone, plan: LongHorizonPlan) -> tuple[str, str, Dict[str, Any]]:
        title_lower = ms.title.lower()
        desc_lower = ms.description.lower()

        if any(w in title_lower or w in desc_lower for w in ("code", "implement", "develop", "refactor", "bug")):
            return "coding", "generate_code", {"prompt": ms.description or ms.title}
        elif any(w in title_lower or w in desc_lower for w in ("vault", "document", "note", "save")):
            return "vault", "create_note", {"title": ms.title, "content": ms.description}
        elif any(w in title_lower or w in desc_lower for w in ("system", "process", "metric", "monitor")):
            return "metrics", "get_metrics", {}
        else:
            return "system", "get_system_info", {"milestone_id": ms.milestone_id}
