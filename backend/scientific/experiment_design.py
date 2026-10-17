"""
AI Experiment Design Assistant.
Prompt 89 — AI Experiment Design Assistant.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid

from backend.scientific.provenance import ScientificProvenance, EvidenceClassification


class DoEMethodology(str, Enum):
    FULL_FACTORIAL = "full_factorial"
    FRACTIONAL_FACTORIAL = "fractional_factorial"
    RESPONSE_SURFACE = "response_surface"
    TAGUCHI = "taguchi"
    BAYESIAN_OPTIMIZATION = "bayesian_optimization"


@dataclass
class ExperimentVariable:
    name: str
    variable_type: str  # "INDEPENDENT", "DEPENDENT", "CONTROL"
    unit: str
    target_or_range: Any
    tolerance: Optional[float] = None


@dataclass
class ExperimentPlan:
    plan_id: str
    title: str
    research_question: str
    variables: List[ExperimentVariable]
    methodology: DoEMethodology
    replicates: int = 3
    safety_hazards: List[str] = field(default_factory=list)
    equipment_required: List[str] = field(default_factory=list)
    is_physically_executable: bool = False  # Mandatory safety gate: False by default
    human_approved: bool = False
    approval_token: Optional[str] = None
    provenance: ScientificProvenance = field(default_factory=ScientificProvenance)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "title": self.title,
            "research_question": self.research_question,
            "variables": [
                {
                    "name": v.name,
                    "variable_type": v.variable_type,
                    "unit": v.unit,
                    "target_or_range": v.target_or_range,
                    "tolerance": v.tolerance
                }
                for v in self.variables
            ],
            "methodology": self.methodology.value if isinstance(self.methodology, DoEMethodology) else self.methodology,
            "replicates": self.replicates,
            "safety_hazards": self.safety_hazards,
            "equipment_required": self.equipment_required,
            "is_physically_executable": self.is_physically_executable,
            "human_approved": self.human_approved,
            "approval_token": self.approval_token,
            "provenance": self.provenance.to_dict(),
            "created_at": self.created_at
        }


class ExperimentDesignService:
    """
    Assists in structuring Design of Experiments (DoE).
    Safety Rule:
    - Never initiates physical experiments autonomously.
    - Requires explicit human approval and safety checklist before plan authorization.
    """

    def __init__(self):
        self._plans: Dict[str, ExperimentPlan] = {}

    def draft_experiment_plan(
        self,
        title: str,
        research_question: str,
        variables: List[ExperimentVariable],
        methodology: DoEMethodology,
        replicates: int = 3,
        safety_hazards: Optional[List[str]] = None
    ) -> ExperimentPlan:
        plan_id = f"exp_{uuid.uuid4().hex[:10]}"
        hazards = safety_hazards or []
        plan = ExperimentPlan(
            plan_id=plan_id,
            title=title,
            research_question=research_question,
            variables=variables,
            methodology=methodology,
            replicates=replicates,
            safety_hazards=hazards,
            is_physically_executable=False,
            human_approved=False,
            approval_token=f"appr_exp_{uuid.uuid4().hex[:8]}",
            provenance=ScientificProvenance(
                classification=EvidenceClassification.HYPOTHESIS,
                reproducibility_notes="AI-assisted DoE draft plan."
            )
        )
        self._plans[plan_id] = plan
        return plan

    def approve_experiment_plan(self, plan_id: str, approval_token: str, reviewer: str) -> tuple[bool, str]:
        plan = self._plans.get(plan_id)
        if not plan:
            return False, "Experiment plan not found."
        if plan.approval_token != approval_token:
            return False, "Invalid approval token."

        plan.human_approved = True
        plan.provenance.reproducibility_notes += f" Reviewed and approved by {reviewer}."
        return True, "Experiment plan authorized by qualified researcher."

    def get_plan(self, plan_id: str) -> Optional[ExperimentPlan]:
        return self._plans.get(plan_id)
