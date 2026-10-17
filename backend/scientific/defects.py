"""
Materials Defect Intelligence - Models & Analysis Engine.
Prompt 87 — Materials Defect Intelligence.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid

from backend.scientific.provenance import ScientificProvenance, EvidenceClassification


class DefectDimension(str, Enum):
    POINT = "0D_point"
    LINE = "1D_line"
    PLANAR = "2D_planar"
    VOLUME = "3D_volume"


class DefectType(str, Enum):
    VACANCY = "vacancy"
    INTERSTITIAL = "interstitial"
    SUBSTITUTIONAL = "substitutional"
    EDGE_DISLOCATION = "edge_dislocation"
    SCREW_DISLOCATION = "screw_dislocation"
    GRAIN_BOUNDARY = "grain_boundary"
    STACKING_FAULT = "stacking_fault"
    VOID = "void"


@dataclass
class DefectObservation:
    defect_id: str
    material_id: str
    defect_type: DefectType
    dimension: DefectDimension
    detection_method: str  # e.g., "HRTEM_ALGORITHMIC", "MANUAL_ANNOTATION", "SIMULATED_DFT"
    coordinates: Optional[tuple[float, float, float]] = None
    calibrated_physical_size_nm: Optional[float] = None
    confidence_score: float = 1.0
    provenance: ScientificProvenance = field(default_factory=ScientificProvenance)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "defect_id": self.defect_id,
            "material_id": self.material_id,
            "defect_type": self.defect_type.value if isinstance(self.defect_type, DefectType) else self.defect_type,
            "dimension": self.dimension.value if isinstance(self.dimension, DefectDimension) else self.dimension,
            "detection_method": self.detection_method,
            "coordinates": self.coordinates,
            "calibrated_physical_size_nm": self.calibrated_physical_size_nm,
            "confidence_score": self.confidence_score,
            "provenance": self.provenance.to_dict(),
            "notes": self.notes
        }


class MaterialsDefectIntelligenceService:
    """
    Materials Defect Intelligence Engine.
    Guarantees:
    - Never calculates physical dimensions without explicit pixel-to-nm scale calibration.
    - Distinguishes algorithmically detected vs directly observed vs model predicted defects.
    """

    def __init__(self):
        # material_id -> List[DefectObservation]
        self._defects: Dict[str, List[DefectObservation]] = {}

    def record_defect(self, observation: DefectObservation) -> bool:
        if observation.material_id not in self._defects:
            self._defects[observation.material_id] = []
        self._defects[observation.material_id].append(observation)
        return True

    def calculate_defect_density(
        self,
        material_id: str,
        defect_type: Optional[DefectType] = None,
        calibrated_area_cm2: Optional[float] = None
    ) -> tuple[bool, Optional[float], str]:
        if not calibrated_area_cm2 or calibrated_area_cm2 <= 0:
            return False, None, "Defect density calculation rejected: physical area calibration required and must be > 0."

        obs_list = self._defects.get(material_id, [])
        if defect_type:
            obs_list = [d for d in obs_list if d.defect_type == defect_type]

        count = len(obs_list)
        density = count / calibrated_area_cm2
        return True, density, f"Calculated density: {density:.2e} defects/cm²"

    def list_material_defects(self, material_id: str) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._defects.get(material_id, [])]
