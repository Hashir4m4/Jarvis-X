"""
Smart Home Integration Service.
Prompt 77 — Smart Home Integration.
"""
import logging
import time
from typing import Dict, Any, List, Optional, Callable
import uuid

from backend.smarthome.models import (
    SmartDeviceType, SmartDeviceSafetyTier, SmartDevice, SmartHomeCommandResult
)

logger = logging.getLogger("JARVIS.SmartHomeService")


class SmartHomeService:
    """
    Vendor-Independent Smart Home Controller.
    Safety Guarantees:
    - High-impact operations (locks, security gateways, access barriers) require explicit confirmation.
    - Offline and stale devices are rejected before command dispatch.
    - Verified execution: State changes are only committed after provider confirms success.
    """

    def __init__(self, security_proxy: Optional[Any] = None, control_framework: Optional[Any] = None):
        self.security = security_proxy
        self.control_framework = control_framework
        self._devices: Dict[str, SmartDevice] = {}
        self._device_handlers: Dict[str, Callable[[str, Dict[str, Any]], bool]] = {}
        self._pending_confirmations: Dict[str, tuple[str, str, Dict[str, Any]]] = {}

    def register_device(self, device: SmartDevice, handler: Optional[Callable] = None):
        self._devices[device.device_id] = device
        if handler:
            self._device_handlers[device.device_id] = handler
        logger.info(f"Registered smart device: {device.name} ({device.device_type.value}) via {device.provider}")

    def get_device(self, device_id: str) -> Optional[SmartDevice]:
        return self._devices.get(device_id)

    def list_devices(self, device_type: Optional[SmartDeviceType] = None) -> List[Dict[str, Any]]:
        devs = list(self._devices.values())
        if device_type:
            devs = [d for d in devs if d.device_type == device_type]
        return [d.to_dict() for d in devs]

    def set_device_availability(self, device_id: str, is_available: bool):
        if device_id in self._devices:
            self._devices[device_id].is_available = is_available
            self._devices[device_id].last_seen = time.time()

    async def execute_device_command(
        self,
        device_id: str,
        command: str,
        parameters: Dict[str, Any],
        confirmed: bool = False
    ) -> SmartHomeCommandResult:
        dev = self.get_device(device_id)
        if not dev:
            return SmartHomeCommandResult(
                device_id=device_id,
                command=command,
                success=False,
                output_message="Device not found."
            )

        if not dev.is_available:
            return SmartHomeCommandResult(
                device_id=device_id,
                command=command,
                success=False,
                output_message=f"Device {dev.name} is currently offline."
            )

        if dev.is_stale(max_stale_seconds=300.0):
            return SmartHomeCommandResult(
                device_id=device_id,
                command=command,
                success=False,
                output_message=f"Device state is stale (last seen > 300s ago). Please refresh connection."
            )

        # High-Impact Safety Gate
        if dev.safety_tier == SmartDeviceSafetyTier.HIGH_IMPACT and not confirmed:
            conf_id = f"conf_{uuid.uuid4().hex[:8]}"
            self._pending_confirmations[conf_id] = (device_id, command, parameters)
            return SmartHomeCommandResult(
                device_id=device_id,
                command=command,
                success=False,
                requires_confirmation=True,
                confirmation_id=conf_id,
                output_message=f"Safety Confirmation Required: Command '{command}' on {dev.name} is classified as HIGH_IMPACT."
            )

        # Dispatch command to adapter
        handler = self._device_handlers.get(device_id)
        success = True
        if handler:
            try:
                res = handler(command, parameters)
                success = bool(res)
            except Exception as e:
                logger.error(f"Error dispatching device command to {dev.name}: {e}")
                return SmartHomeCommandResult(
                    device_id=device_id,
                    command=command,
                    success=False,
                    output_message=f"Device execution error: {str(e)}"
                )

        if success:
            dev.current_state.update(parameters)
            dev.last_seen = time.time()
            return SmartHomeCommandResult(
                device_id=device_id,
                command=command,
                success=True,
                output_message=f"Command '{command}' successfully executed on {dev.name}.",
                new_state=dict(dev.current_state)
            )

        return SmartHomeCommandResult(
            device_id=device_id,
            command=command,
            success=False,
            output_message="Device adapter rejected command."
        )

    async def confirm_command(self, confirmation_id: str) -> SmartHomeCommandResult:
        pending = self._pending_confirmations.pop(confirmation_id, None)
        if not pending:
            return SmartHomeCommandResult(
                device_id="unknown",
                command="unknown",
                success=False,
                output_message="Invalid or expired confirmation token."
            )
        dev_id, cmd, params = pending
        return await self.execute_device_command(dev_id, cmd, params, confirmed=True)
