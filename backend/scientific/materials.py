"""
AI Materials Research Platform - Models & Service.
Prompt 86 — AI Materials Research Platform.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid

from backend.scientific.provenance import ScientificProvenance, EvidenceClassification


class MaterialClass(str, Enum):
    METAL = "metal"
    ALLOY = "alloy"
    SEMICONDUCTOR = "semiconductor"
    CERAMIC = "ceramic"
    POLYMER = "polymer"
    COMPOSITE = "composite"
    NANOMATERIAL = "nanomaterial"
    TWO_DIMENSIONAL = "two_dimensional"
    FUNCTIONAL = "functional"
    OTHER = "other"


@dataclass
class CrystalStructure:
    space_group: Optional[str] = None
    crystal_system: Optional[str] = None
    lattice_parameters: Dict[str, float] = field(default_factory=dict)  # a, b, c (in Ångströms), alpha, beta, gamma


@dataclass
class MaterialRecord:
    material_id: str
    name: str
    formula: str
    composition: Dict[str, float]  # Element -> mass fraction or atomic fraction
    material_class: MaterialClass
    structure: Optional[CrystalStructure] = None
    properties: Dict[str, Any] = field(default_factory=dict)  # property -> {value, unit, classification, uncertainty}
    synthesis_conditions: Dict[str, Any] = field(default_factory=dict)
    provenance: ScientificProvenance = field(default_factory=ScientificProvenance)
    associated_papers: List[str] = field(default_factory=list)
    associated_datasets: List[str] = field(default_factory=list)
    associated_simulations: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "material_id": self.material_id,
            "name": self.name,
            "formula": self.formula,
            "composition": self.composition,
            "material_class": self.material_class.value if isinstance(self.material_class, MaterialClass) else self.material_class,
            "structure": {
                "space_group": self.structure.space_group if self.structure else None,
                "crystal_system": self.structure.crystal_system if self.structure else None,
                "lattice_parameters": self.structure.lattice_parameters if self.structure else {}
            } if self.structure else None,
            "properties": self.properties,
            "synthesis_conditions": self.synthesis_conditions,
            "provenance": self.provenance.to_dict(),
            "associated_papers": self.associated_papers,
            "associated_datasets": self.associated_datasets,
            "associated_simulations": self.associated_simulations,
            "notes": self.notes,
            "created_at": self.created_at
        }


class MaterialsResearchService:
    """
    Central AI Materials Research Workspace.
    Maintains validated material profiles, property registries, and traceability.
    """

    def __init__(self):
        # material_id -> MaterialRecord
        self._materials: Dict[str, MaterialRecord] = {}

    def register_material(self, record: MaterialRecord) -> tuple[bool, Optional[str]]:
        if not record.material_id or not record.formula:
            return False, "Material registration failed: missing material_id or chemical formula."
        if record.material_id in self._materials:
            return False, f"Material {record.material_id} already exists."

        self._materials[record.material_id] = record
        return True, None

    def get_material(self, material_id: str) -> Optional[MaterialRecord]:
        return self._materials.get(material_id)

    def search_materials(
        self,
        query: Optional[str] = None,
        material_class: Optional[MaterialClass] = None,
        element: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results = []
        for m in self._materials.values():
            if material_class and m.material_class != material_class:
                continue
            if element and element not in m.composition:
                continue
            if query:
                q = query.lower()
                if q not in m.name.lower() and q not in m.formula.lower():
                    continue
            results.append(m.to_dict())
        return results

    def add_property(
        self,
        material_id: str,
        property_name: str,
        value: Any,
        unit: str,
        classification: EvidenceClassification = EvidenceClassification.EXPERIMENTAL,
        uncertainty: Optional[float] = None
    ) -> bool:
        mat = self._materials.get(material_id)
        if not mat:
            return False
        mat.properties[property_name] = {
            "value": value,
            "unit": unit,
            "classification": classification.value if isinstance(classification, EvidenceClassification) else classification,
            "uncertainty": uncertainty,
            "recorded_at": time.time()
        }
        return True

    def compare_materials(self, material_id_a: str, material_id_b: str) -> Optional[Dict[str, Any]]:
        a = self.get_material(material_id_a)
        b = self.get_material(material_id_b)
        if not a or not b:
            return None

        all_props = set(a.properties.keys()).union(set(b.properties.keys()))
        comparison = {}
        for p in all_props:
            comparison[p] = {
                a.name: a.properties.get(p, {"value": "NOT_MEASURED"}),
                b.name: b.properties.get(p, {"value": "NOT_MEASURED"})
            }
        return {
            "material_a": a.to_dict(),
            "material_b": b.to_dict(),
            "property_comparison": comparison
        }
