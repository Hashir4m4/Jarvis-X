"""
Unit and Integration Tests for Prompts 71 & 72 — Vision + Voice Fusion & Multi-Modal Intelligence.
"""
import pytest
import asyncio
from backend.multimodal.models import (
    ModalityType, VisionInputSource, MultimodalProcessingState,
    ImagePayload, MultimodalRequest, MultimodalResponse
)
from backend.multimodal.orchestrator import MultimodalOrchestrator


@pytest.mark.asyncio
async def test_multimodal_camera_permission_enforcement():
    orch = MultimodalOrchestrator(vlm_manager=None)
    orch.set_camera_permission(False)

    img = ImagePayload(source=VisionInputSource.AUTHORIZED_CAMERA_CAPTURE, data_bytes=b"fake_raw_bytes")
    req = MultimodalRequest(
        modalities=[ModalityType.IMAGE, ModalityType.TEXT],
        text_prompt="What is in front of the camera?",
        image_payload=img
    )

    resp = await orch.process_multimodal_request(req)
    assert resp.state == MultimodalProcessingState.AWAITING_PERMISSION
    assert "Camera access denied" in resp.response_text


@pytest.mark.asyncio
async def test_multimodal_vision_voice_fusion():
    orch = MultimodalOrchestrator(vlm_manager=None)
    img = ImagePayload(source=VisionInputSource.USER_UPLOAD, file_path="/path/to/chart.png")
    req = MultimodalRequest(
        modalities=[ModalityType.IMAGE, ModalityType.SPEECH_TRANSCRIPT],
        voice_transcript="Explain this architectural diagram.",
        image_payload=img
    )

    resp = await orch.process_multimodal_request(req)
    assert resp.state == MultimodalProcessingState.COMPLETED
    assert "user_upload" in resp.response_text
    assert ModalityType.IMAGE in resp.modalities_processed
    assert ModalityType.SPEECH_TRANSCRIPT in resp.modalities_processed


@pytest.mark.asyncio
async def test_multimodal_vlm_mock_dispatch():
    class MockVLM:
        async def analyze_image(self, img, prompt):
            return "VLM Output: Detected system architecture diagram with 5 microservices."

    orch = MultimodalOrchestrator(vlm_manager=MockVLM())
    img = ImagePayload(source=VisionInputSource.USER_SELECTED_FILE, file_path="arch.png")
    req = MultimodalRequest(
        modalities=[ModalityType.IMAGE, ModalityType.TEXT],
        text_prompt="Summarize components.",
        image_payload=img
    )

    resp = await orch.process_multimodal_request(req)
    assert resp.state == MultimodalProcessingState.COMPLETED
    assert "Detected system architecture diagram" in resp.response_text
    assert resp.provider_used == "vlm_engine"
