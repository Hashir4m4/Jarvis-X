"""
Unit and Integration Tests for Prompt 67 — Desktop Command Center.
"""
import pytest
import asyncio
from backend.command_center.models import CommandExecutionState, DesktopCommandRequest, DesktopCommandResult
from backend.command_center.service import DesktopCommandCenter
from backend.core.models import CoreResponse, Intent, IntentType


@pytest.mark.asyncio
async def test_command_center_safety_validation():
    center = DesktopCommandCenter(jarvis_core=None)
    req = DesktopCommandRequest(raw_input="rm -rf /")
    result = await center.execute_command(req)

    assert result.state == CommandExecutionState.REJECTED
    assert "potentially destructive" in result.output_text
    assert len(center.get_history()) == 1


@pytest.mark.asyncio
async def test_command_center_emergency_stop_enforcement():
    class MockControl:
        def is_emergency_stop_active(self):
            return True

    center = DesktopCommandCenter(jarvis_core=object(), control_framework=MockControl())
    req = DesktopCommandRequest(raw_input="do something")
    result = await center.execute_command(req)

    assert result.state == CommandExecutionState.REJECTED
    assert "Emergency Stop" in result.output_text


@pytest.mark.asyncio
async def test_command_center_successful_execution():
    class MockCore:
        async def process_input(self, user_in):
            intent = Intent(
                intent_type=IntentType.SYSTEM_CONTROL,
                skill_name="system",
                action="get_system_info",
                parameters={},
                confidence=1.0,
                raw_input=user_in.content
            )
            return CoreResponse(
                text="System status: nominal.",
                channel=user_in.channel,
                intent=intent,
                data={"cpu": 12.5}
            )

    center = DesktopCommandCenter(jarvis_core=MockCore())
    req = DesktopCommandRequest(raw_input="system status")
    result = await center.execute_command(req)

    assert result.state == CommandExecutionState.COMPLETED
    assert result.output_text == "System status: nominal."
    assert result.intent_skill == "system"
    assert result.data["cpu"] == 12.5
    assert len(center.get_history()) == 1


@pytest.mark.asyncio
async def test_command_center_cancellation_and_suggestions():
    center = DesktopCommandCenter(jarvis_core=None)
    suggestions = center.get_suggestions("show")
    assert any("goals" in s for s in suggestions)

    req = DesktopCommandRequest(raw_input="test command")
    center._active_requests[req.request_id] = req
    cancelled = center.cancel_command(req.request_id)
    assert cancelled is True
    assert req.request_id not in center._active_requests
