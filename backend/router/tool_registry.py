import logging
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass, field

from backend.automation.system_controller import SystemController
from backend.automation.app_manager import AppManager
from backend.automation.file_manager import FileManager
from backend.automation.input_controller import InputController
from backend.automation.terminal_executor import TerminalExecutor

logger = logging.getLogger("JARVIS.ToolRegistry")


@dataclass
class ToolDefinition:
    """Metadata for a registered tool."""
    name: str
    description: str
    handler: Callable[..., Any]
    category: str = "automation"
    required_permissions: List[str] = field(default_factory=list)


class ToolRegistry:
    """
    Central discovery and invocation registry for JARVIS automation tools and multi-agent systems.
    Provides tool resolution, permission verification, and safe error-wrapped execution.
    """

    def __init__(
        self,
        system_controller: Optional[SystemController] = None,
        app_manager: Optional[AppManager] = None,
        file_manager: Optional[FileManager] = None,
        input_controller: Optional[InputController] = None,
        terminal_executor: Optional[TerminalExecutor] = None,
        agent_manager: Optional[Any] = None
    ):
        self.system_ctrl = system_controller or SystemController()
        self.app_mgr = app_manager or AppManager()
        self.file_mgr = file_manager or FileManager()
        self.input_ctrl = input_controller or InputController()
        self.term_exec = terminal_executor or TerminalExecutor()
        self.agent_mgr = agent_manager

        self._tools: Dict[str, ToolDefinition] = {}
        self._register_default_tools()
        if self.agent_mgr:
            self.register_agent_tools(self.agent_mgr)

    def _register_default_tools(self):
        """Registers built-in tools across automation categories."""
        # System Hardware & OS Tools
        self.register_tool("system.get_info", "Get OS and hardware status", self.system_ctrl.get_system_info, category="system", permissions=["system:read"])
        self.register_tool("system.get_volume", "Get master audio volume", self.system_ctrl.get_volume, category="system", permissions=["system:read"])
        self.register_tool("system.set_volume", "Set master audio volume", self.system_ctrl.set_volume, category="system", permissions=["system:write"])
        self.register_tool("system.get_battery", "Get battery percentage and status", self.system_ctrl.get_battery, category="system", permissions=["system:read"])
        self.register_tool("system.get_wifi", "Get WiFi adapter connection state", self.system_ctrl.get_wifi_status, category="system", permissions=["system:read"])
        self.register_tool("system.list_processes", "List running processes", self.system_ctrl.list_processes, category="system", permissions=["system:read"])
        self.register_tool("system.kill_process", "Terminate process by PID", self.system_ctrl.kill_process, category="system", permissions=["system:write"])

        # Application Management Tools
        self.register_tool("app.open", "Launch an application", self.app_mgr.open_app, category="application", permissions=["app:launch"])
        self.register_tool("app.close", "Terminate an application", self.app_mgr.close_app, category="application", permissions=["app:kill"])
        self.register_tool("app.minimize", "Minimize current window", self.app_mgr.minimize_window, category="application", permissions=["app:window"])
        self.register_tool("app.maximize", "Maximize current window", self.app_mgr.maximize_window, category="application", permissions=["app:window"])

        # File Management Tools
        self.register_tool("file.read", "Read file text contents", self.file_mgr.read_file, category="file", permissions=["file:read"])
        self.register_tool("file.list", "List directory contents", self.file_mgr.list_files, category="file", permissions=["file:read"])
        self.register_tool("file.create_folder", "Create folder", self.file_mgr.create_folder, category="file", permissions=["file:write"])
        self.register_tool("file.rename", "Rename file or directory", self.file_mgr.rename_file, category="file", permissions=["file:write"])
        self.register_tool("file.delete", "Delete a file", self.file_mgr.delete_file, category="file", permissions=["file:delete"])
        self.register_tool("file.search", "Search files with glob pattern", self.file_mgr.search_files, category="file", permissions=["file:read"])

        # Terminal Tools
        self.register_tool("terminal.powershell", "Execute PowerShell command", self.term_exec.run_powershell, category="terminal", permissions=["terminal:exec"])
        self.register_tool("terminal.cmd", "Execute Windows CMD command", self.term_exec.run_cmd, category="terminal", permissions=["terminal:exec"])

    def register_agent_tools(self, agent_manager: Any):
        """Registers the multi-agent swarm into the Tool/Agent Registry."""
        self.agent_mgr = agent_manager
        self.register_tool("agent.pipeline", "Execute complete multi-agent coding pipeline", self.agent_mgr.run_task, category="agent", permissions=["code:plan", "code:write"])
        self.register_tool("agent.planner", "Decompose coding task into steps", self.agent_mgr.planner.plan, category="agent", permissions=["code:plan"])
        self.register_tool("agent.coder", "Synthesize code from step specification", self.agent_mgr.coder.generate, category="agent", permissions=["code:write"])
        self.register_tool("agent.reviewer", "Audit source code quality and security", self.agent_mgr.reviewer.review, category="agent", permissions=["code:review"])
        self.register_tool("agent.executor", "Run and test code deliverables", self.agent_mgr.executor.run_file, category="agent", permissions=["code:execute"])
        logger.info("Multi-Agent Swarm (Planner, Coder, Reviewer, Executor) registered in Tool Registry.")

    def register_scheduler_tools(self, scheduler: Any):
        """Registers scheduler management tools into the Tool Registry."""
        self.register_tool("schedule.list", "List active scheduled tasks", scheduler.get_active_schedules, category="scheduler", permissions=["scheduler:read"])
        self.register_tool("schedule.history", "Get execution history logs", scheduler.get_history, category="scheduler", permissions=["scheduler:read"])
        self.register_tool("schedule.cancel", "Cancel scheduled task by ID", scheduler.cancel_task, category="scheduler", permissions=["scheduler:write"])
        self.register_tool("schedule.add_daily", "Schedule a daily command at HH:MM", scheduler.schedule_daily, category="scheduler", permissions=["scheduler:write"])
        self.register_tool("schedule.add_interval", "Schedule a recurring interval command", scheduler.schedule_interval, category="scheduler", permissions=["scheduler:write"])
        logger.info("Scheduler management tools registered in Tool Registry.")

    def register_tool(self, name: str, description: str, handler: Callable[..., Any], category: str = "automation", permissions: List[str] = None):
        """Registers a callable tool in the registry."""
        self._tools[name.lower()] = ToolDefinition(
            name=name.lower(),
            description=description,
            handler=handler,
            category=category,
            required_permissions=permissions or []
        )
        logger.debug(f"Registered Tool: '{name}' ({description})")

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Retrieves tool definition by name."""
        return self._tools.get(name.lower())

    def execute_tool(self, name: str, *args, **kwargs) -> Any:
        """
        Executes a tool by name with exception trapping.
        """
        tool = self.get_tool(name)
        if not tool:
            raise KeyError(f"Tool '{name}' is not registered in ToolRegistry.")

        logger.debug(f"Executing Tool '{name}' with args={args}, kwargs={kwargs}")
        try:
            return tool.handler(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error executing Tool '{name}': {e}", exc_info=True)
            raise

    def list_tools(self) -> List[Dict[str, Any]]:
        """Lists metadata for all registered tools."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "permissions": t.required_permissions
            }
            for t in self._tools.values()
        ]
