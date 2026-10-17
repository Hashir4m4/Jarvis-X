"""
Unit and Integration Tests for Prompt 79 — Hardware Control Layer.
"""
import pytest
from backend.hardware.models import (
    HardwareCategory, HardwarePrivilegeLevel, HardwareDeviceProfile, HardwareCommandResult
)
from backend.hardware.service import HardwareControlService


@pytest.mark.asyncio
async def test_hardware_discovery_and_safe_action():
    service = HardwareControlService()
    hardware_list = service.list_hardware()
    assert len(hardware_list) >= 3

    # Audio safe action
    res = await service.execute_hardware_action("audio_master", "set_volume", {"level": 65})
    assert res.success is True
    assert res.resulting_state["volume"] == 65


@pytest.mark.asyncio
async def test_hardware_privileged_approval_gate():
    service = HardwareControlService()

    # Power subsystem is PRIVILEGED
    res_unapproved = await service.execute_hardware_action("power_subsystem", "set_power_plan", {"plan": "HighPerformance"})
    assert res_unapproved.success is False
    assert res_unapproved.requires_approval is True
    assert res_unapproved.approval_token is not None

    # Approve and execute
    res_approved = await service.approve_and_execute(res_unapproved.approval_token)
    assert res_approved.success is True
    assert res_approved.resulting_state["plan"] == "HighPerformance"


@pytest.mark.asyncio
async def test_hardware_unsupported_action():
    service = HardwareControlService()
    res = await service.execute_hardware_action("audio_master", "overclock_dac", {})
    assert res.success is False
    assert "not supported" in res.output_message
