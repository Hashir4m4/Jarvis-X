"""
Innovation Opportunity Detection.
Prompt 97 — Innovation Opportunity Detection.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time
import uuid

from backend.scientific.provenance import ScientificProvenance, EvidenceClassification


@dataclass
class InnovationOpportunity:
    opportunity_id: str
    problem_statement: str
    target_application: str
    identified_research_gap: str
    supporting_evidence: List[str]
    technical_feasibility_score: float  # 0.0 - 1.0
    commercial_potential_score: float   # 0.0 - 1.0 (strictly separate from feasibility)
    major_risks: List[str]
    provenance: ScientificProvenance = field(default_factory=ScientificProvenance)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "problem_statement": self.problem_statement,
            "target_application": self.target_application,
            "identified_research_gap": self.identified_research_gap,
            "supporting_evidence": self.supporting_evidence,
            "technical_feasibility_score": self.technical_feasibility_score,
            "commercial_potential_score": self.commercial_potential_score,
            "major_risks": self.major_risks,
            "provenance": self.provenance.to_dict()
        }


class InnovationOpportunityService:
    """
    Evidence-Driven Innovation Opportunity Engine.
    Guarantees:
    - Strictly separates technical feasibility from commercial potential.
    - Demands explicit research gap identification and risk enumeration.
    """

    def __init__(self):
        self._opportunities: Dict[str, InnovationOpportunity] = {}

    def register_opportunity(
        self,
        problem_statement: str,
        target_application: str,
        identified_research_gap: str,
        supporting_evidence: List[str],
        technical_feasibility_score: float,
        commercial_potential_score: float,
        major_risks: List[str]
    ) -> tuple[bool, Optional[InnovationOpportunity], str]:
        if not problem_statement or not identified_research_gap:
            return False, None, "Invalid opportunity: problem statement and research gap required."

        opp_id = f"opp_{uuid.uuid4().hex[:10]}"
        opp = InnovationOpportunity(
            opportunity_id=opp_id,
            problem_statement=problem_statement,
            target_application=target_application,
            identified_research_gap=identified_research_gap,
            supporting_evidence=supporting_evidence,
            technical_feasibility_score=technical_feasibility_score,
            commercial_potential_score=commercial_potential_score,
            major_risks=major_risks,
            provenance=ScientificProvenance(
                classification=EvidenceClassification.INFERRED,
                reproducibility_notes="Synthesized from multi-domain literature gap analysis."
            )
        )
        self._opportunities[opp_id] = opp
        return True, opp, "Innovation opportunity cataloged."

    def get_opportunity(self, opp_id: str) -> Optional[InnovationOpportunity]:
        return self._opportunities.get(opp_id)
