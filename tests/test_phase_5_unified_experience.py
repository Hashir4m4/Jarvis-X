"""
Unified End-to-End Integration Tests for Phase 5 (Prompts 66-75).
Advanced JARVIS Experience Integration Suite.
"""
import pytest
import asyncio
from backend.core.core import JarvisCore
from backend.command_center.models import DesktopCommandRequest, CommandExecutionState
from backend.multimodal.models import ModalityType, VisionInputSource, ImagePayload, MultimodalRequest
from backend.notifications.models import NotificationCategory, NotificationPriority
from backend.ambient.models import AmbientOperatingMode


@pytest.fixture
def core_instance():
    cfg = {
        "storage": {"vault_path": "vault"},
        "voice": {"mode": "MANUAL"}
    }
    core = JarvisCore(config=cfg, session_id="phase5_test_session")
    return core


def test_phase5_service_registration_in_core(core_instance):
    """Verifies that all Phase 5 services are cleanly registered in AppContainer and bound to JarvisCore."""
    assert core_instance.hud_service is not None
    assert core_instance.command_center is not None
    assert core_instance.system_visualization is not None
    assert core_instance.notification_service is not None
    assert core_instance.multimodal_orchestrator is not None
    assert core_instance.workspace_intelligence is not None
    assert core_instance.ambient_intelligence is not None


def test_phase5_hud_aggregation(core_instance):
    """Verifies HUD 2.0 can aggregate state across all core subsystems without crash."""
    snapshot = core_instance.hud_service.get_snapshot()
    assert snapshot is not None
    assert "status" in snapshot.system_status
    assert "operating_state" in snapshot.ai_status
    assert "active_goals" in snapshot.planning or "goals_count" in snapshot.planning


@pytest.mark.asyncio
async def test_phase5_desktop_command_center(core_instance):
    """Verifies Command Center processes safe requests and rejects forbidden shell execution."""
    # 1. Safe command
    req_safe = DesktopCommandRequest(raw_input="system status")
    res_safe = await core_instance.command_center.execute_command(req_safe)
    assert res_safe.state in (CommandExecutionState.COMPLETED, CommandExecutionState.FAILED)

    # 2. Blocked dangerous command
    req_danger = DesktopCommandRequest(raw_input="rm -rf /")
    res_danger = await core_instance.command_center.execute_command(req_danger)
    assert res_danger.state == CommandExecutionState.REJECTED
    assert "potentially destructive" in res_danger.output_text


def test_phase5_notifications_and_ambient_interaction(core_instance):
    """Verifies notification dispatch and ambient suggestion generation."""
    notif = core_instance.notification_service.post_notification(
        title="Workflow Milestone",
        message="Milestone 1 finished.",
        category=NotificationCategory.TASK_COMPLETION,
        priority=NotificationPriority.NORMAL
    )
    assert notif is not None
    assert core_instance.notification_service.get_unread_count() == 1

    # Ambient mode lifecycle
    amb = core_instance.ambient_intelligence
    assert amb.mode == AmbientOperatingMode.DISABLED
    amb.enable()
    assert amb.mode == AmbientOperatingMode.ACTIVE
    amb.pause()
    assert amb.mode == AmbientOperatingMode.PAUSED
    amb.disable()
    assert amb.mode == AmbientOperatingMode.DISABLED


@pytest.mark.asyncio
async def test_phase5_multimodal_vision_permission_guard(core_instance):
    """Verifies that multimodal vision camera capture strictly enforces permission."""
    mm = core_instance.multimodal_orchestrator
    mm.set_camera_permission(False)

    img = ImagePayload(source=VisionInputSource.AUTHORIZED_CAMERA_CAPTURE, data_bytes=b"raw_frame")
    req = MultimodalRequest(
        modalities=[ModalityType.IMAGE, ModalityType.TEXT],
        text_prompt="Inspect scene",
        image_payload=img
    )
    resp = await mm.process_multimodal_request(req)
    assert resp.error_message == "Camera permission not granted."
