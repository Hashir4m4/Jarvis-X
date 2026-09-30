import asyncio
import logging
from typing import Dict, Any

from .event_bus import EventBus
from .task_manager import TaskManager
from .agent_coordinator import AgentCoordinator
from .scheduler import Scheduler

logger = logging.getLogger(__name__)

class JarvisKernel:
    """
    The Core Operating System Kernel for Jarvis X.
    Manages the event loop, background tasks, agent coordination, and scheduling.
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.event_bus = EventBus()
        self.task_manager = TaskManager()
        self.agent_coordinator = AgentCoordinator(self.event_bus)
        self.scheduler = Scheduler(self.task_manager)
        
        self._running = False
        logger.info("Jarvis OS Kernel initialized.")

    async def start(self):
        """Boots the Kernel and starts background services."""
        if self._running:
            return
            
        self._running = True
        logger.info("Booting Jarvis OS Kernel...")
        
        # Start the scheduler
        self.scheduler.start()
        
        # Subscribe to essential system events
        await self.event_bus.subscribe("system_shutdown", self._handle_shutdown)
        await self.event_bus.subscribe("user_input", self._handle_user_input)
        
        # We can schedule a telemetry broadcast every 2 seconds
        # This replaces the background task in server.py
        self.scheduler.schedule_interval("broadcast_telemetry", 2, self._broadcast_telemetry)
        
        logger.info("Jarvis OS Kernel is ONLINE.")

    async def _broadcast_telemetry(self):
        """Gather telemetry and publish to the event bus."""
        from backend.automation.system_controller import SystemController
        sys_ctrl = SystemController()
        info = sys_ctrl.get_system_info()
        
        # This will be picked up by the websocket manager in server.py
        await self.event_bus.publish("telemetry_update", {
            "type": "telemetry",
            "cpu": info.get("cpu_percent", 0),
            "ram": info.get("ram_used_percent", 0),
            "ramTotal": info.get("ram_total_gb", 16.0),
            "swap": info.get("swap_percent", 0),
            "temp": info.get("temperature_c"),
            "os": info.get("os", "Unknown OS"),
            "wifi": "Connected" if info.get("wifi_connected") else "Disconnected"
        })

    async def _handle_user_input(self, event_type: str, data: Any):
        """
        Triggered when user input arrives.
        This allows the kernel to orchestrate which agent handles the request.
        """
        user_message = data.get("message", "")
        logger.info(f"Kernel received user input: {user_message}")
        
        # In the future, the Planner Agent will intercept this.
        # For now, we publish a request to the main Brain.
        await self.event_bus.publish("brain_process_request", data)

    async def _handle_shutdown(self, event_type: str, data: Any):
        """Gracefully shuts down the kernel."""
        logger.info("Kernel received shutdown signal.")
        await self.stop()

    async def stop(self):
        """Stops the Kernel."""
        self._running = False
        self.scheduler.stop()
        logger.info("Jarvis OS Kernel offline.")
