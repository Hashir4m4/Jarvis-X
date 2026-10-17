"""
Deep-Tech Project Intelligence.
Prompt 99 — Deep-Tech Project Intelligence.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid

from backend.scientific.provenance import ScientificProvenance, EvidenceClassification


class ResearchStage(str, Enum):
    IDEA = "IDEA"
    LITERATURE_REVIEW = "LITERATURE_REVIEW"
    PLANNING = "PLANNING"
    EXPERIMENT_DESIGN = "EXPERIMENT_DESIGN"
    DATA_COLLECTION = "DATA_COLLECTION"
    SIMULATION = "SIMULATION"
    VALIDATION = "VALIDATION"
    REPORTING = "REPORTING"
    COMPLETED = "COMPLETED"


@dataclass
class DeepTechProject:
    project_id: str
    title: str
    core_objective: str
    stage: ResearchStage = ResearchStage.IDEA
    associated_materials: List[str] = field(default_factory=list)
    associated_papers: List[str] = field(default_factory=list)
    associated_experiments: List[str] = field(default_factory=list)
    associated_simulations: List[str] = field(default_factory=list)
    associated_hypotheses: List[str] = field(default_factory=list)
    progress_milestones: List[str] = field(default_factory=list)
    provenance: ScientificProvenance = field(default_factory=ScientificProvenance)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "core_objective": self.core_objective,
            "stage": self.stage.value if isinstance(self.stage, ResearchStage) else self.stage,
            "associated_materials": self.associated_materials,
            "associated_papers": self.associated_papers,
            "associated_experiments": self.associated_experiments,
            "associated_simulations": self.associated_simulations,
            "associated_hypotheses": self.associated_hypotheses,
            "progress_milestones": self.progress_milestones,
            "provenance": self.provenance.to_dict(),
            "created_at": self.created_at
        }


class DeepTechProjectIntelligenceService:
    """
    Scientific Project Orchestration & Artifact Binder.
    Guarantees:
    - Integrates research artifacts (materials, simulations, hypotheses) into cohesive projects.
    - Preserves stage progression history and research provenance.
    """

    def __init__(self):
        self._projects: Dict[str, DeepTechProject] = {}

    def create_project(self, title: str, core_objective: str) -> DeepTechProject:
        project_id = f"proj_{uuid.uuid4().hex[:10]}"
        proj = DeepTechProject(
            project_id=project_id,
            title=title,
            core_objective=core_objective,
            stage=ResearchStage.IDEA,
            progress_milestones=["Project initiated."]
        )
        self._projects[project_id] = proj
        return proj

    def advance_project_stage(self, project_id: str, new_stage: ResearchStage) -> bool:
        proj = self._projects.get(project_id)
        if not proj:
            return False
        proj.stage = new_stage
        proj.progress_milestones.append(f"Transitioned to stage: {new_stage.value} at {time.time()}")
        return True

    def link_artifact(self, project_id: str, artifact_type: str, artifact_id: str) -> bool:
        proj = self._projects.get(project_id)
        if not proj:
            return False
        if artifact_type == "material":
            proj.associated_materials.append(artifact_id)
        elif artifact_type == "paper":
            proj.associated_papers.append(artifact_id)
        elif artifact_type == "experiment":
            proj.associated_experiments.append(artifact_id)
        elif artifact_type == "simulation":
            proj.associated_simulations.append(artifact_id)
        elif artifact_type == "hypothesis":
            proj.associated_hypotheses.append(artifact_id)
        else:
            return False
        return True

    def get_project(self, project_id: str) -> Optional[DeepTechProject]:
        return self._projects.get(project_id)
