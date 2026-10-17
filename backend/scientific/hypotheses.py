"""
AI Hypothesis Generation & Falsification Engine.
Prompt 94 — AI Hypothesis Generation.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time
import uuid

from backend.scientific.provenance import ScientificProvenance, EvidenceClassification


@dataclass
class ScientificHypothesis:
    hypothesis_id: str
    scientific_question: str
    proposed_explanation: str
    supporting_observations: List[str]
    contradictory_evidence: List[str]
    assumptions: List[str]
    falsifiable_predictions: List[str]
    suggested_test_plan: str
    confidence_rationale: str
    provenance: ScientificProvenance = field(default_factory=ScientificProvenance)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "scientific_question": self.scientific_question,
            "proposed_explanation": self.proposed_explanation,
            "supporting_observations": self.supporting_observations,
            "contradictory_evidence": self.contradictory_evidence,
            "assumptions": self.assumptions,
            "falsifiable_predictions": self.falsifiable_predictions,
            "suggested_test_plan": self.suggested_test_plan,
            "confidence_rationale": self.confidence_rationale,
            "provenance": self.provenance.to_dict(),
            "created_at": self.created_at
        }


class HypothesisGenerationService:
    """
    Scientific Hypothesis Generator & Evaluation Engine.
    Guarantees:
    - Never declares a hypothesis as a discovery.
    - Explicitly retains contradictory evidence and requires falsifiable predictions.
    """

    def __init__(self):
        self._hypotheses: Dict[str, ScientificHypothesis] = {}

    def formulate_hypothesis(
        self,
        scientific_question: str,
        proposed_explanation: str,
        supporting_observations: List[str],
        falsifiable_predictions: List[str],
        contradictory_evidence: Optional[List[str]] = None,
        assumptions: Optional[List[str]] = None,
        suggested_test_plan: str = "Perform controlled X-ray diffraction and transport measurements."
    ) -> tuple[bool, Optional[ScientificHypothesis], str]:
        if not scientific_question or not proposed_explanation:
            return False, None, "Invalid hypothesis: question and proposed explanation required."
        if not falsifiable_predictions:
            return False, None, "Invalid hypothesis: must contain at least one falsifiable prediction."

        hyp_id = f"hyp_{uuid.uuid4().hex[:10]}"
        hyp = ScientificHypothesis(
            hypothesis_id=hyp_id,
            scientific_question=scientific_question,
            proposed_explanation=proposed_explanation,
            supporting_observations=supporting_observations,
            contradictory_evidence=contradictory_evidence or [],
            assumptions=assumptions or [],
            falsifiable_predictions=falsifiable_predictions,
            suggested_test_plan=suggested_test_plan,
            confidence_rationale="Evidence-grounded inductive formulation.",
            provenance=ScientificProvenance(
                classification=EvidenceClassification.HYPOTHESIS,
                reproducibility_notes="Requires independent experimental/computational testing."
            )
        )
        self._hypotheses[hyp_id] = hyp
        return True, hyp, "Hypothesis formulated with falsification criteria."

    def get_hypothesis(self, hypothesis_id: str) -> Optional[ScientificHypothesis]:
        return self._hypotheses.get(hypothesis_id)

    def list_hypotheses(self) -> List[Dict[str, Any]]:
        return [h.to_dict() for h in self._hypotheses.values()]
