"""
Unit and Integration Tests for Prompt 77 — Smart Home Integration.
"""
import pytest
import time
from backend.smarthome.models import (
    SmartDeviceType, SmartDeviceSafetyTier, SmartDevice, SmartHomeCommandResult
)
from backend.smarthome.service import SmartHomeService


@pytest.mark.asyncio
async def test_smart_home_standard_device_command():
    service = SmartHomeService()
    light = SmartDevice(
        device_id="light_living_room",
        name="Living Room Light",
        device_type=SmartDeviceType.LIGHT,
        provider="PhilipsHue",
        safety_tier=SmartDeviceSafetyTier.STANDARD,
        current_state={"power": "off", "brightness": 0}
    )
    service.register_device(light)

    res = await service.execute_device_command("light_living_room", "turn_on", {"power": "on", "brightness": 80})
    assert res.success is True
    assert light.current_state["power"] == "on"
    assert light.current_state["brightness"] == 80


@pytest.mark.asyncio
async def test_smart_home_high_impact_safety_gate():
    service = SmartHomeService()
    lock = SmartDevice(
        device_id="lock_front_door",
        name="Front Door Lock",
        device_type=SmartDeviceType.LOCK,
        provider="Yale",
        safety_tier=SmartDeviceSafetyTier.HIGH_IMPACT,
        current_state={"locked": True}
    )
    service.register_device(lock)

    # Attempt to unlock without confirmation
    res_unconfirmed = await service.execute_device_command("lock_front_door", "unlock", {"locked": False})
    assert res_unconfirmed.success is False
    assert res_unconfirmed.requires_confirmation is True
    assert res_unconfirmed.confirmation_id is not None
    assert lock.current_state["locked"] is True

    # Confirm command
    res_confirmed = await service.confirm_command(res_unconfirmed.confirmation_id)
    assert res_confirmed.success is True
    assert lock.current_state["locked"] is False


@pytest.mark.asyncio
async def test_smart_home_offline_and_stale_detection():
    service = SmartHomeService()
    thermostat = SmartDevice(
        device_id="thermo_hallway",
        name="Hallway Thermostat",
        device_type=SmartDeviceType.THERMOSTAT,
        provider="Nest",
        is_available=False
    )
    service.register_device(thermostat)

    res = await service.execute_device_command("thermo_hallway", "set_temp", {"temp": 21})
    assert res.success is False
    assert "offline" in res.output_message

    # Test stale device
    thermostat.is_available = True
    thermostat.last_seen = time.time() - 400.0  # 400 seconds ago (>300s)
    res_stale = await service.execute_device_command("thermo_hallway", "set_temp", {"temp": 21})
    assert res_stale.success is False
    assert "stale" in res_stale.output_message
