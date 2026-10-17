"""
Scientific Image Analysis Platform.
Prompt 88 — Scientific Image Analysis.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import hashlib
import uuid

from backend.scientific.provenance import ScientificProvenance, EvidenceClassification


class MicroscopyModality(str, Enum):
    OPTICAL = "optical"
    SEM = "scanning_electron_microscopy"
    TEM = "transmission_electron_microscopy"
    AFM = "atomic_force_microscopy"
    STEM = "scanning_transmission_electron_microscopy"
    XRD_DIFFRACTION_PATTERN = "xrd_diffraction_pattern"


@dataclass
class PhysicalScaleCalibration:
    pixels_per_unit: float  # e.g., 10.5 pixels per nm
    unit: str  # "nm", "um", "pm"
    scale_bar_detected: bool = False
    calibrated_by: str = "instrument_metadata"

    def pixels_to_physical(self, pixels: float) -> float:
        return pixels / self.pixels_per_unit if self.pixels_per_unit > 0 else 0.0


@dataclass
class ScientificImageRecord:
    image_id: str
    filename: str
    modality: MicroscopyModality
    pixel_dimensions: tuple[int, int]
    raw_image_hash: str
    calibration: Optional[PhysicalScaleCalibration] = None
    acquisition_metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: ScientificProvenance = field(default_factory=ScientificProvenance)
    is_processed: bool = False
    parent_raw_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_id": self.image_id,
            "filename": self.filename,
            "modality": self.modality.value if isinstance(self.modality, MicroscopyModality) else self.modality,
            "pixel_dimensions": self.pixel_dimensions,
            "raw_image_hash": self.raw_image_hash,
            "calibration": {
                "pixels_per_unit": self.calibration.pixels_per_unit,
                "unit": self.calibration.unit,
                "scale_bar_detected": self.calibration.scale_bar_detected
            } if self.calibration else None,
            "acquisition_metadata": self.acquisition_metadata,
            "is_processed": self.is_processed,
            "parent_raw_id": self.parent_raw_id,
            "provenance": self.provenance.to_dict(),
            "created_at": self.created_at
        }


class ScientificImageAnalysisService:
    """
    Scientific Image Analysis Platform.
    Guarantees:
    - Original raw micrographs are immutable.
    - Physical feature dimension calculations strictly require verified scale calibration.
    """

    def __init__(self):
        # image_id -> ScientificImageRecord
        self._images: Dict[str, ScientificImageRecord] = {}

    def register_image(
        self,
        filename: str,
        image_bytes: bytes,
        modality: MicroscopyModality,
        pixel_dimensions: tuple[int, int],
        calibration: Optional[PhysicalScaleCalibration] = None,
        acquisition_metadata: Optional[Dict[str, Any]] = None
    ) -> ScientificImageRecord:
        image_id = f"img_{uuid.uuid4().hex[:12]}"
        sha = hashlib.sha256(image_bytes).hexdigest()

        rec = ScientificImageRecord(
            image_id=image_id,
            filename=filename,
            modality=modality,
            pixel_dimensions=pixel_dimensions,
            raw_image_hash=sha,
            calibration=calibration,
            acquisition_metadata=acquisition_metadata or {},
            provenance=ScientificProvenance(
                file_hash_sha256=sha,
                classification=EvidenceClassification.EXPERIMENTAL,
                reproducibility_notes="Immutable raw microscopy record."
            )
        )
        self._images[image_id] = rec
        return rec

    def measure_feature_physical_size(
        self,
        image_id: str,
        pixel_length: float
    ) -> tuple[bool, Optional[float], str]:
        rec = self._images.get(image_id)
        if not rec:
            return False, None, "Image not found."

        if not rec.calibration:
            return False, None, "Physical measurement rejected: scale calibration not present for this micrograph."

        physical_val = rec.calibration.pixels_to_physical(pixel_length)
        return True, physical_val, f"{physical_val:.3f} {rec.calibration.unit}"

    def get_image(self, image_id: str) -> Optional[ScientificImageRecord]:
        return self._images.get(image_id)
