import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List


class CaptureType(str, enum.Enum):
    FULL_SCREEN = "FULL_SCREEN"
    ACTIVE_WINDOW = "ACTIVE_WINDOW"
    SELECTED_REGION = "SELECTED_REGION"


class VisionTaskType(str, enum.Enum):
    SCREEN_DESCRIPTION = "SCREEN_DESCRIPTION"
    TEXT_EXTRACTION = "TEXT_EXTRACTION"
    ERROR_ANALYSIS = "ERROR_ANALYSIS"
    UI_UNDERSTANDING = "UI_UNDERSTANDING"
    DOCUMENT_SUMMARY = "DOCUMENT_SUMMARY"
    ACTIVE_WINDOW_ANALYSIS = "ACTIVE_WINDOW_ANALYSIS"
    OBJECT_IDENTIFICATION = "OBJECT_IDENTIFICATION"
    CODE_ERROR_ANALYSIS = "CODE_ERROR_ANALYSIS"


class StoragePolicy(str, enum.Enum):
    DO_NOT_STORE = "DO_NOT_STORE"
    TEMPORARY = "TEMPORARY"
    USER_APPROVED_SAVE = "USER_APPROVED_SAVE"


@dataclass
class WindowMetadata:
    """Safe metadata describing the currently active or targeted window."""
    app_name: str = ""
    window_title: str = ""
    bounds: Dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0, "width": 0, "height": 0})
    is_fullscreen: bool = False
    process_id: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "app_name": self.app_name,
            "window_title": self.window_title,
            "bounds": self.bounds,
            "is_fullscreen": self.is_fullscreen,
            "process_id": self.process_id,
        }


@dataclass
class ScreenAnalysisResult:
    """
    Structured representation of screen perception.
    Never passes raw unbounded pixels into the orchestrator without structured metadata.
    """
    capture_id: str = field(default_factory=lambda: f"cap_{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    source_type: CaptureType = CaptureType.FULL_SCREEN
    detected_application: str = "Unknown"
    window_title: str = ""
    extracted_text: str = ""
    detected_ui_elements: List[str] = field(default_factory=list)
    detected_errors: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    confidence: float = 1.0
    privacy_level: str = "LOCAL_ONLY"
    provider: str = "local"
    model: str = "moondream"
    image_path: Optional[str] = None
    has_sensitive_data: bool = False
    sensitive_categories: List[str] = field(default_factory=list)
    suggested_action_plan: Optional[Dict[str, Any]] = None
    target_coordinates: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "capture_id": self.capture_id,
            "timestamp": self.timestamp,
            "source_type": self.source_type.value if hasattr(self.source_type, "value") else str(self.source_type),
            "detected_application": self.detected_application,
            "window_title": self.window_title,
            "extracted_text": self.extracted_text,
            "detected_ui_elements": self.detected_ui_elements,
            "detected_errors": self.detected_errors,
            "summary": self.summary,
            "confidence": self.confidence,
            "privacy_level": self.privacy_level,
            "provider": self.provider,
            "model": self.model,
            "image_path": self.image_path,
            "sensitive_categories": self.sensitive_categories,
            "suggested_action_plan": self.suggested_action_plan,
            "target_coordinates": self.target_coordinates,
            "metadata": self.metadata,
        }
