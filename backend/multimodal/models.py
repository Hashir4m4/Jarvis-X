"""
Multimodal Intelligence & Fusion Models.
Prompts 71 & 72 — Vision + Voice Fusion & Multi-Modal Intelligence.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class ModalityType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    SPEECH_TRANSCRIPT = "speech_transcript"
    STRUCTURED_CONTEXT = "structured_context"


class VisionInputSource(str, Enum):
    USER_UPLOAD = "user_upload"
    USER_SELECTED_FILE = "user_selected_file"
    AUTHORIZED_CAMERA_CAPTURE = "authorized_camera_capture"
    AUTHORIZED_SCREEN_CAPTURE = "authorized_screen_capture"


class MultimodalProcessingState(str, Enum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    AWAITING_PERMISSION = "AWAITING_PERMISSION"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class ImagePayload:
    source: VisionInputSource
    data_bytes: Optional[bytes] = None
    file_path: Optional[str] = None
    mime_type: str = "image/png"
    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: int = 0
    camera_permission_granted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source.value if isinstance(self.source, VisionInputSource) else str(self.source),
            "file_path": self.file_path,
            "mime_type": self.mime_type,
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
            "camera_permission_granted": self.camera_permission_granted
        }


@dataclass
class MultimodalRequest:
    request_id: str = field(default_factory=lambda: f"mm_{uuid.uuid4().hex[:8]}")
    user_id: str = "local_user"
    session_id: str = "default_session"
    modalities: List[ModalityType] = field(default_factory=list)
    text_prompt: Optional[str] = None
    voice_transcript: Optional[str] = None
    image_payload: Optional[ImagePayload] = None
    structured_context: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "modalities": [m.value if isinstance(m, ModalityType) else str(m) for m in self.modalities],
            "text_prompt": self.text_prompt,
            "voice_transcript": self.voice_transcript,
            "image_payload": self.image_payload.to_dict() if self.image_payload else None,
            "structured_context": dict(self.structured_context),
            "timestamp": self.timestamp
        }


@dataclass
class MultimodalResponse:
    request_id: str
    state: MultimodalProcessingState
    response_text: str
    provider_used: str = "local_vlm"
    modalities_processed: List[ModalityType] = field(default_factory=list)
    confidence: Optional[float] = None
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "state": self.state.value if isinstance(self.state, MultimodalProcessingState) else str(self.state),
            "response_text": self.response_text,
            "provider_used": self.provider_used,
            "modalities_processed": [m.value if isinstance(m, ModalityType) else str(m) for m in self.modalities_processed],
            "confidence": self.confidence,
            "latency_ms": self.latency_ms,
            "error_message": self.error_message,
            "metadata": dict(self.metadata)
        }
