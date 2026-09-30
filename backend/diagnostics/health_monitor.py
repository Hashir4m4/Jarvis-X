"""
JARVIS Component Health Monitor

Coordinates health check scheduling, event-triggered checks, and
proactive failure detection.

INTEGRATION RULES:
- Reuses EventBus from kernel — no new background loops created.
- Reuses MonitorRegistry for periodic polling notifications.
- Subscribes to existing events: proactive_event, voice_state, component_error.
- Health notifications are deduplicated per component per cooldown window.
- Non-critical component failures do not block startup.
- Notifications published through existing EventBus (not a new channel).
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable

from .models import (
    HealthStatus, HealthCheckResult, HealthReport, CheckTrigger
)
from .component_registry import ComponentRegistry
from .health_checks import HealthCheckRegistry

logger = logging.getLogger("JARVIS.HealthMonitor")

# Cooldown between notifications for the same component (seconds)
_NOTIFICATION_COOLDOWN = 120.0


class ComponentHealthMonitor:
    """
    Coordinates health checks and proactive failure detection.

    Responsibilities:
    - Run startup diagnostics on critical components.
    - Subscribe to EventBus events that may indicate component failures.
    - Trigger targeted health checks on relevant events.
    - Deduplicate health notifications to avoid spamming the user.
    - Report degraded capability through existing notification channels.

    This class does NOT create its own polling loop.
    It subscribes to the existing MonitorRegistry/EventBus infrastructure.
    """

    def __init__(
        self,
        component_registry: ComponentRegistry,
        health_check_registry: HealthCheckRegistry,
        event_bus: Optional[Any] = None,
        notify_callback: Optional[Callable[[str, str], Awaitable[None]]] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.registry = component_registry
        self.checks = health_check_registry
        self.event_bus = event_bus
        self._notify = notify_callback  # async fn(component_id, message)
        self.config = config or {}

        # Deduplication state: component_id → last_notification_time
        self._last_notification: Dict[str, float] = {}
        # Last known statuses for change detection
        self._last_known_status: Dict[str, HealthStatus] = {}

        self._running = False

    # ── Startup ──────────────────────────────────────────────────

    async def run_startup_diagnostics(
        self,
        critical_only: bool = False,
        trigger: CheckTrigger = CheckTrigger.STARTUP
    ) -> HealthReport:
        """
        Runs health checks on all (or only critical) components.

        Non-critical failures are noted but do not block startup.
        Critical failures are prominently reported.
        """
        logger.info("[HealthMonitor] Running startup diagnostics...")
        results: Dict[str, HealthCheckResult] = {}

        target_ids = (
            [r.component_id for r in self.registry.get_critical()]
            if critical_only else
            self.checks.list_ids()
        )

        for cid in target_ids:
            result = await self.checks.run(cid, trigger=trigger, timeout=5.0)
            if result:
                results[cid] = result
                self.registry.update_status(cid, result.status, result.error_summary)
                self._last_known_status[cid] = result.status

        overall = self.registry.get_overall_status()
        report = HealthReport(
            results=results,
            overall_status=overall,
            trigger=trigger
        )

        _healthy = sum(1 for r in results.values() if r.status == HealthStatus.HEALTHY)
        _total = len(results)
        logger.info(
            f"[HealthMonitor] Startup diagnostics complete: "
            f"{_healthy}/{_total} components healthy. Overall: {overall.value}"
        )
        return report

    # ── EventBus Subscription ─────────────────────────────────────

    async def start(self):
        """Subscribes to relevant EventBus events for proactive detection."""
        if self._running or not self.event_bus:
            return
        self._running = True

        await self.event_bus.subscribe("proactive_event", self._on_proactive_event)
        await self.event_bus.subscribe("voice_state", self._on_voice_state_event)
        await self.event_bus.subscribe("component_error", self._on_component_error_event)
        await self.event_bus.subscribe("model_server_offline", self._on_model_server_event)

        logger.info("[HealthMonitor] Subscribed to EventBus health-relevant events.")

    async def stop(self):
        self._running = False
        logger.info("[HealthMonitor] Stopped.")

    # ── Event Handlers ────────────────────────────────────────────

    async def _on_proactive_event(self, event_type: str, data: Any):
        """Handles events from MonitorRegistry — checks if they indicate component issues."""
        if not isinstance(data, dict):
            return

        payload = data.get("payload", {})
        source = data.get("source", "")

        # ModelServerMonitor reports local_ai status
        if source == "model_server_monitor":
            service_status = payload.get("status", "")
            if service_status == "OFFLINE":
                await self._trigger_check("local_ai", CheckTrigger.EVENT_TRIGGERED)

    async def _on_voice_state_event(self, event_type: str, data: Any):
        """Handles voice state changes that may indicate STT/TTS failure."""
        if not isinstance(data, dict):
            return
        state = data.get("state", "")
        if state in ("ERROR", "STT_ERROR", "TTS_ERROR", "DISCONNECTED"):
            await self._trigger_check("voice_input", CheckTrigger.EVENT_TRIGGERED)
            await self._trigger_check("voice_output", CheckTrigger.EVENT_TRIGGERED)

    async def _on_component_error_event(self, event_type: str, data: Any):
        """Handles explicit component_error events from any subsystem."""
        if not isinstance(data, dict):
            return
        component_id = data.get("component_id", "")
        if component_id and self.registry.exists(component_id):
            await self._trigger_check(component_id, CheckTrigger.EVENT_TRIGGERED)

    async def _on_model_server_event(self, event_type: str, data: Any):
        """Handles direct model server offline events."""
        await self._trigger_check("local_ai", CheckTrigger.EVENT_TRIGGERED)

    # ── Targeted Check ────────────────────────────────────────────

    async def _trigger_check(self, component_id: str, trigger: CheckTrigger) -> Optional[HealthCheckResult]:
        """Runs a targeted health check and updates registry. May emit notification."""
        result = await self.checks.run(component_id, trigger=trigger, timeout=5.0)
        if not result:
            return None

        old_status = self._last_known_status.get(component_id, HealthStatus.UNKNOWN)
        self.registry.update_status(component_id, result.status, result.error_summary)
        self._last_known_status[component_id] = result.status

        # Emit notification only if status worsened and not on cooldown
        if self._status_worsened(old_status, result.status):
            await self._emit_health_notification(component_id, result)

        return result

    # ── Manual / On-Demand Checks ─────────────────────────────────

    async def check_component(
        self,
        component_id: str,
        trigger: CheckTrigger = CheckTrigger.ON_DEMAND
    ) -> Optional[HealthCheckResult]:
        """Runs a targeted health check on demand."""
        result = await self.checks.run(component_id, trigger=trigger, timeout=5.0)
        if result:
            self.registry.update_status(component_id, result.status, result.error_summary)
            self._last_known_status[component_id] = result.status
        return result

    async def check_all(
        self,
        trigger: CheckTrigger = CheckTrigger.ON_DEMAND
    ) -> HealthReport:
        """Runs health checks on all registered components."""
        results = {}
        for cid in self.checks.list_ids():
            result = await self.checks.run(cid, trigger=trigger, timeout=5.0)
            if result:
                results[cid] = result
                self.registry.update_status(cid, result.status, result.error_summary)
                self._last_known_status[cid] = result.status

        overall = self.registry.get_overall_status()
        return HealthReport(results=results, overall_status=overall, trigger=trigger)

    # ── Notification Deduplication ────────────────────────────────

    async def _emit_health_notification(self, component_id: str, result: HealthCheckResult):
        """Publishes a health degradation notification, respecting cooldown."""
        now = time.time()
        last = self._last_notification.get(component_id, 0.0)
        if (now - last) < _NOTIFICATION_COOLDOWN:
            logger.debug(f"[HealthMonitor] Suppressing duplicate notification for '{component_id}'.")
            return

        self._last_notification[component_id] = now
        record = self.registry.get(component_id)
        name = record.name if record else component_id.replace("_", " ").title()

        message = self._format_notification(name, result)
        logger.info(f"[HealthMonitor] Health notification: {message}")

        if self.event_bus:
            await self.event_bus.publish("health_status_changed", {
                "component_id": component_id,
                "component_name": name,
                "status": result.status.value,
                "message": message,
                "recommended_action": result.recommended_action
            })

        if self._notify:
            try:
                await self._notify(component_id, message)
            except Exception as e:
                logger.debug(f"[HealthMonitor] Notify callback error: {e}")

    @staticmethod
    def _format_notification(component_name: str, result: HealthCheckResult) -> str:
        """Formats a concise, user-facing health notification."""
        status_map = {
            HealthStatus.UNAVAILABLE: "is currently unavailable",
            HealthStatus.FAILING: "is repeatedly failing",
            HealthStatus.DEGRADED: "is operating in degraded mode",
        }
        status_text = status_map.get(result.status, f"status changed to {result.status.value.lower()}")
        msg = f"{component_name} {status_text}."
        if result.recommended_action:
            msg += f" {result.recommended_action}"
        return msg

    @staticmethod
    def _status_worsened(old: HealthStatus, new: HealthStatus) -> bool:
        """Returns True if the new status is worse than the old one."""
        severity = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DISABLED: 0,
            HealthStatus.UNKNOWN: 1,
            HealthStatus.RECOVERING: 2,
            HealthStatus.DEGRADED: 3,
            HealthStatus.UNAVAILABLE: 4,
            HealthStatus.FAILING: 5,
        }
        return severity.get(new, 1) > severity.get(old, 1)

    # ── HUD Payload ───────────────────────────────────────────────

    def get_hud_payload(self) -> Dict[str, Any]:
        """Returns a compact, safe payload for the HUD health overlay."""
        statuses = self.registry.get_all_statuses()
        overall = self.registry.get_overall_status()
        return {
            "overall": overall.value,
            "components": statuses
        }
