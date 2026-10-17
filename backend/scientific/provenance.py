"""
Phase 7 Scientific Data Contracts & Evidence Classification.
Shared across Prompts 86–100.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class EvidenceClassification(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    PUBLISHED = "PUBLISHED"
    COMPUTED = "COMPUTED"
    SIMULATED = "SIMULATED"
    PREDICTED = "PREDICTED"
    HYPOTHESIS = "HYPOTHESIS"
    INFERRED = "INFERRED"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class ScientificProvenance:
    artifact_id: str = field(default_factory=lambda: f"art_{uuid.uuid4().hex[:12]}")
    source_identifier: str = ""  # DOI, accession, dataset URL, or file path
    author_or_provider: str = "JARVIS Research Subsystem"
    retrieval_timestamp: float = field(default_factory=time.time)
    dataset_version: Optional[str] = "1.0.0"
    file_hash_sha256: Optional[str] = None
    processing_pipeline_version: str = "7.0.0"
    model_version: Optional[str] = None
    instrument_or_solver_metadata: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    units: Dict[str, str] = field(default_factory=dict)
    classification: EvidenceClassification = EvidenceClassification.UNVERIFIED
    validation_status: str = "PENDING"
    reproducibility_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "source_identifier": self.source_identifier,
            "author_or_provider": self.author_or_provider,
            "retrieval_timestamp": self.retrieval_timestamp,
            "dataset_version": self.dataset_version,
            "file_hash_sha256": self.file_hash_sha256,
            "processing_pipeline_version": self.processing_pipeline_version,
            "model_version": self.model_version,
            "instrument_or_solver_metadata": self.instrument_or_solver_metadata,
            "parameters": self.parameters,
            "units": self.units,
            "classification": self.classification.value if isinstance(self.classification, EvidenceClassification) else self.classification,
            "validation_status": self.validation_status,
            "reproducibility_notes": self.reproducibility_notes
        }
