import asyncio
import logging
import os
import shutil
import time
from typing import Dict, Any, List, Optional, Callable

from .models import (
    JarvisEvent, EventType, EventPriority,
    MonitorDefinition, MonitorStatus
)
import psutil
from backend.automation.system_controller import SystemController

logger = logging.getLogger("JARVIS.MonitorRegistry")


class BaseMonitor:
    """Abstract base class for all safe, non-intrusive event monitors."""

    def __init__(self, definition: MonitorDefinition):
        self.definition = definition

    @property
    def monitor_id(self) -> str:
        return self.definition.monitor_id

    @property
    def name(self) -> str:
        return self.definition.name

    @property
    def enabled(self) -> bool:
        return self.definition.enabled

    def enable(self):
        self.definition.enabled = True
        self.definition.status = MonitorStatus.ACTIVE

    def disable(self):
        self.definition.enabled = False
        self.definition.status = MonitorStatus.DISABLED

    def to_dict(self) -> Dict[str, Any]:
        return self.definition.to_dict()

    async def poll(self) -> Optional[JarvisEvent]:
        """Performs a single safe query. Returns an event if a noteworthy condition occurs."""
        raise NotImplementedError


class BatteryMonitor(BaseMonitor):
    """Monitors battery percentage and charging state."""

    def __init__(
        self,
        system_controller: Optional[SystemController] = None,
        interval_seconds: float = 60.0
    ):
        definition = MonitorDefinition(
            monitor_id="battery_monitor",
            name="Battery Monitor",
            description="Monitors laptop battery level and power connection.",
            event_types=[EventType.SYSTEM_EVENT],
            required_capabilities=["system_info"],
            interval_seconds=interval_seconds,
            enabled=True
        )
        super().__init__(definition)
        self.sys_ctrl = system_controller or SystemController()

    async def poll(self) -> Optional[JarvisEvent]:
        try:
            bat = self.sys_ctrl.get_battery()
            if bat.get("status") != "ok" or "percent" not in bat:
                return None

            percent = bat["percent"]
            plugged_in = bat.get("plugged_in", False)
            self.definition.last_poll_time = time.time()

            return JarvisEvent(
                event_type=EventType.SYSTEM_EVENT,
                source="battery_monitor",
                priority=EventPriority.MEDIUM if percent < 20 and not plugged_in else EventPriority.LOW,
                payload={
                    "metric": "battery",
                    "percent": percent,
                    "plugged_in": plugged_in
                }
            )
        except Exception as e:
            self.definition.status = MonitorStatus.ERROR
            self.definition.error_message = str(e)
            logger.debug(f"[BATTERY_MONITOR] Poll error: {e}")
            return None


class DiskMonitor(BaseMonitor):
    """Monitors available disk space on the primary storage drive."""

    def __init__(
        self,
        path: str = "C:\\",
        interval_seconds: float = 120.0
    ):
        definition = MonitorDefinition(
            monitor_id="disk_monitor",
            name="Disk Monitor",
            description="Monitors available storage space on system drive.",
            event_types=[EventType.SYSTEM_EVENT],
            required_capabilities=["file_system"],
            interval_seconds=interval_seconds,
            enabled=True
        )
        super().__init__(definition)
        self.path = path

    async def poll(self) -> Optional[JarvisEvent]:
        try:
            target = self.path if os.path.exists(self.path) else "."
            usage = shutil.disk_usage(target)
            free_gb = round(usage.free / (1024 ** 3), 2)
            total_gb = round(usage.total / (1024 ** 3), 2)
            pct_free = round((usage.free / usage.total) * 100.0, 1)

            self.definition.last_poll_time = time.time()
            priority = EventPriority.HIGH if pct_free < 10.0 else EventPriority.LOW

            return JarvisEvent(
                event_type=EventType.SYSTEM_EVENT,
                source="disk_monitor",
                priority=priority,
                payload={
                    "metric": "disk_free",
                    "path": self.path,
                    "free_gb": free_gb,
                    "total_gb": total_gb,
                    "pct_free": pct_free
                }
            )
        except Exception as e:
            self.definition.status = MonitorStatus.ERROR
            self.definition.error_message = str(e)
            logger.debug(f"[DISK_MONITOR] Poll error: {e}")
            return None

class SystemMonitor(BaseMonitor):
    """Monitors CPU and RAM utilization."""

    def __init__(self, interval_seconds: float = 30.0):
        definition = MonitorDefinition(
            monitor_id="system_monitor",
            name="System Health Monitor",
            description="Monitors CPU and RAM usage.",
            event_types=[EventType.SYSTEM_EVENT],
            required_capabilities=["system_info"],
            interval_seconds=interval_seconds,
            enabled=True
        )
        super().__init__(definition)

    async def poll(self) -> Optional[JarvisEvent]:
        try:
            cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()
            ram_pct = mem.percent

            self.definition.last_poll_time = time.time()
            
            # Prioritize highest severity
            priority = EventPriority.LOW
            if cpu_pct > 95 or ram_pct > 95:
                priority = EventPriority.CRITICAL
            elif cpu_pct > 85 or ram_pct > 85:
                priority = EventPriority.HIGH
            elif cpu_pct > 70 or ram_pct > 70:
                priority = EventPriority.MEDIUM

            if priority != EventPriority.LOW:
                return JarvisEvent(
                    event_type=EventType.SYSTEM_EVENT,
                    source="system_monitor",
                    priority=priority,
                    payload={
                        "metric": "system_usage",
                        "cpu_percent": cpu_pct,
                        "ram_percent": ram_pct
                    }
                )
            return None
        except Exception as e:
            self.definition.status = MonitorStatus.ERROR
            self.definition.error_message = str(e)
            logger.debug(f"[SYSTEM_MONITOR] Poll error: {e}")
            return None


class ModelServerMonitor(BaseMonitor):
    """Checks the health of the local AI / Ollama server."""

    def __init__(
        self,
        server_url: str = "http://localhost:11434",
        interval_seconds: float = 30.0
    ):
        definition = MonitorDefinition(
            monitor_id="model_server_monitor",
            name="Local AI Model Server Monitor",
            description="Monitors availability of local Ollama / AI inference server.",
            event_types=[EventType.SYSTEM_EVENT, EventType.NETWORK_EVENT],
            required_capabilities=["local_model"],
            interval_seconds=interval_seconds,
            enabled=True
        )
        super().__init__(definition)
        self.server_url = server_url
        self.last_state = "UNKNOWN"

    async def poll(self) -> Optional[JarvisEvent]:
        current_state = "ONLINE"
        try:
            import urllib.request
            req = urllib.request.Request(self.server_url, method="GET")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status != 200:
                    current_state = "OFFLINE"
        except Exception:
            current_state = "OFFLINE"

        self.definition.last_poll_time = time.time()

        # Only emit when state changes or server is offline
        if current_state != self.last_state or current_state == "OFFLINE":
            self.last_state = current_state
            return JarvisEvent(
                event_type=EventType.SYSTEM_EVENT,
                source="model_server_monitor",
                priority=EventPriority.MEDIUM if current_state == "OFFLINE" else EventPriority.LOW,
                payload={
                    "service": "local_ai_server",
                    "status": current_state,
                    "url": self.server_url
                }
            )
        return None


class TaskMonitor(BaseMonitor):
    """Event-driven listener for Task Execution Engine completion and progress events."""

    def __init__(self):
        definition = MonitorDefinition(
            monitor_id="task_monitor",
            name="Task Execution Monitor",
            description="Listens for task execution progress, completion, or failure.",
            event_types=[EventType.TASK_EVENT],
            required_capabilities=["task_planner"],
            interval_seconds=0.0,  # Pure event-driven, no polling
            enabled=True
        )
        super().__init__(definition)

    def handle_task_event(self, task_payload: Dict[str, Any]) -> JarvisEvent:
        status = task_payload.get("status", "UNKNOWN")
        priority = EventPriority.HIGH if status in ("FAILED", "CANCELLED") else EventPriority.LOW

        return JarvisEvent(
            event_type=EventType.TASK_EVENT,
            source="task_monitor",
            priority=priority,
            related_task_id=task_payload.get("plan_id"),
            payload={
                "task_id": task_payload.get("plan_id"),
                "goal": task_payload.get("goal"),
                "status": status,
                "summary": task_payload.get("summary")
            }
        )


class MonitorRegistry:
    """
    Central registry and lifecycle manager for all monitors.
    Coordinates polling intervals, safe execution, and event dispatch to the Kernel EventBus.
    """

    def __init__(
        self,
        event_bus: Optional[Any] = None,
        system_controller: Optional[SystemController] = None
    ):
        self.event_bus = event_bus
        self.sys_ctrl = system_controller or SystemController()
        self._monitors: Dict[str, BaseMonitor] = {}
        self._polling_tasks: Dict[str, asyncio.Task] = {}
        self._running = False

        self._register_default_monitors()

    def _register_default_monitors(self):
        self.register(BatteryMonitor(self.sys_ctrl))
        self.register(DiskMonitor())
        self.register(SystemMonitor())
        self.register(ModelServerMonitor())
        self.register(TaskMonitor())

    def register(self, monitor: BaseMonitor):
        """Registers a monitor into the registry."""
        mid = monitor.monitor_id.lower().strip()
        self._monitors[mid] = monitor
        logger.debug(f"[MONITOR_REGISTRY] Registered monitor: '{monitor.name}' (ID: {mid})")

    def get_monitor(self, monitor_id: str) -> Optional[BaseMonitor]:
        return self._monitors.get(monitor_id.lower().strip())

    def enable_monitor(self, monitor_id: str) -> bool:
        m = self.get_monitor(monitor_id)
        if m:
            m.enable()
            logger.info(f"[MONITOR_REGISTRY] Enabled monitor: '{monitor_id}'")
            return True
        return False

    def disable_monitor(self, monitor_id: str) -> bool:
        m = self.get_monitor(monitor_id)
        if m:
            m.disable()
            logger.info(f"[MONITOR_REGISTRY] Disabled monitor: '{monitor_id}'")
            return True
        return False

    def remove_monitor(self, monitor_id: str) -> bool:
        mid = monitor_id.lower().strip()
        if mid in self._monitors:
            self.disable_monitor(mid)
            del self._monitors[mid]
            logger.info(f"[MONITOR_REGISTRY] Removed monitor: '{mid}'")
            return True
        return False

    def list_monitors(self) -> List[Dict[str, Any]]:
        return [m.definition.to_dict() for m in self._monitors.values()]

    async def start(self):
        """Starts active polling loops for periodic monitors."""
        if self._running:
            return
        self._running = True

        for mid, monitor in self._monitors.items():
            if monitor.definition.interval_seconds > 0:
                self._polling_tasks[mid] = asyncio.create_task(self._monitor_loop(monitor))

        logger.info(f"[MONITOR_REGISTRY] Started {len(self._polling_tasks)} polling monitor(s).")

    async def stop(self):
        """Stops all polling loops gracefully."""
        self._running = False
        for task in self._polling_tasks.values():
            task.cancel()
        self._polling_tasks.clear()
        logger.info("[MONITOR_REGISTRY] Stopped all polling monitors.")

    async def _monitor_loop(self, monitor: BaseMonitor):
        """Safe polling loop for an individual monitor."""
        while self._running:
            try:
                if monitor.enabled:
                    event = await monitor.poll()
                    if event and self.event_bus:
                        await self.event_bus.publish("proactive_event", event.to_dict())
                await asyncio.sleep(monitor.definition.interval_seconds)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[MONITOR_REGISTRY] Unhandled error in monitor '{monitor.monitor_id}': {e}")
                await asyncio.sleep(monitor.definition.interval_seconds)
