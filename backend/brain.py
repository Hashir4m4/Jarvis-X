import logging
from typing import Dict, Any, Generator
from .llm_client import LLMClient
from .memory_manager import MemoryManager
from .automation.security_proxy import SecurityProxy
from .automation.system_controller import SystemController
from .automation.app_manager import AppManager
from .automation.file_manager import FileManager
from .automation.input_controller import InputController
from .automation.terminal_executor import TerminalExecutor
from .automation.terminal_executor import TerminalExecutor

logger = logging.getLogger(__name__)

TOOLS_SYSTEM_PROMPT = """
You also have access to the following PC automation tools. When you decide to use a tool,
respond with EXACTLY this format on its own line:

[TOOL] tool_name | arg1=value1 | arg2=value2

Available tools:
- open_app | app_name=<name>        — Open an application (chrome, vscode, notepad, calculator, etc.)
- close_app | process_name=<name>   — Close an application by process name (e.g. chrome.exe)
- screenshot                        — Take a screenshot
- get_volume                        — Get current volume level
- set_volume | level=<0-100>        — Set volume level
- mute_volume                       — Mute audio
- unmute_volume                     — Unmute audio
- get_brightness                    — Get current brightness
- set_brightness | level=<0-100>    — Set brightness
- get_clipboard                     — Read clipboard contents
- get_system_info                   — Get CPU, RAM, OS details
- list_processes                    — List top running processes
- list_files | path=<dir>           — List files in a directory
- search_files | directory=<dir> | pattern=<glob>  — Search for files
- create_folder | path=<dir>        — Create a new folder
- run_powershell | command=<cmd>    — Execute a PowerShell command (requires confirmation)
- run_cmd | command=<cmd>           — Execute a CMD command (requires confirmation)
- delete_file | path=<file>         — Delete a file (requires confirmation)
- rename_file | src=<old> | dest=<new>  — Rename a file (requires confirmation)
- type_text | text=<string>         — Type text via keyboard
- press_key | key=<key>             — Press a keyboard key
- mouse_click | x=<int> | y=<int>  — Click at screen coordinates

[PLUGIN TOOLS]
"""

class Brain:
    def __init__(self, config: Dict[str, Any], session_id: str = "default"):
        self.config = config
        
        # System prompt initialization
        self.system_prompt = config.get("llm", {}).get("system_prompt", "You are a helpful AI assistant.")
        self.system_prompt += TOOLS_SYSTEM_PROMPT

        # Initialize components
        self.llm = LLMClient(config.get("llm", {}))
        self.memory = MemoryManager(config, session_id)

        # Automation components
        self.security = SecurityProxy(config)
        self.system_ctrl = SystemController()
        self.app_mgr = AppManager()
        self.file_mgr = FileManager()
        self.input_ctrl = InputController()
        self.terminal = TerminalExecutor()

        logger.info(f"Jarvis Brain initialized. Session: {session_id}, Model: {self.llm.model}")

    def _parse_tool_call(self, text: str) -> tuple:
        """
        Parses a [TOOL] line from the LLM response.
        Returns (tool_name, kwargs_dict) or (None, None).
        """
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith("[TOOL]"):
                parts = [p.strip() for p in line[6:].split("|")]
                tool_name = parts[0].strip()
                kwargs = {}
                for part in parts[1:]:
                    if "=" in part:
                        k, v = part.split("=", 1)
                        kwargs[k.strip()] = v.strip()
                return tool_name, kwargs
        return None, None

    def _execute_tool(self, tool_name: str, kwargs: dict) -> str:
        """Routes a parsed tool call to the correct handler via the security proxy."""

        dispatch = {
            # Safe actions
            "open_app":       ("open_app",       lambda: self.app_mgr.open_app(kwargs.get("app_name", ""))),
            "screenshot":     ("screenshot",     lambda: self.input_ctrl.screenshot()),
            "get_volume":     ("get_volume",     lambda: self.system_ctrl.get_volume()),
            "get_brightness": ("get_brightness", lambda: self.system_ctrl.get_brightness()),
            "get_clipboard":  ("get_clipboard",  lambda: self.input_ctrl.get_clipboard()),
            "get_system_info":("get_system_info",lambda: self.system_ctrl.get_system_info()),
            "list_processes": ("list_processes",  lambda: self.system_ctrl.list_processes()),
            "list_files":     ("list_files",     lambda: self.file_mgr.list_files(kwargs.get("path", "."))),
            "search_files":   ("search_files",   lambda: self.file_mgr.search_files(kwargs.get("directory", "."), kwargs.get("pattern", "*"))),
            "type_text":      ("type_text",      lambda: self.input_ctrl.type_text(kwargs.get("text", ""))),
            "press_key":      ("press_key",      lambda: self.input_ctrl.press_key(kwargs.get("key", ""))),
            "mouse_move":     ("mouse_move",     lambda: self.input_ctrl.mouse_move(int(kwargs.get("x", 0)), int(kwargs.get("y", 0)))),
            "mouse_click":    ("mouse_click",    lambda: self.input_ctrl.mouse_click(int(kwargs.get("x", 0)), int(kwargs.get("y", 0)))),
            "minimize_window":("minimize_window",lambda: self.app_mgr.minimize_window()),
            "maximize_window":("maximize_window",lambda: self.app_mgr.maximize_window()),
            "set_volume":     ("get_volume",     lambda: self.system_ctrl.set_volume(int(kwargs.get("level", 50)))),
            "mute_volume":    ("get_volume",     lambda: self.system_ctrl.mute_volume()),
            "unmute_volume":  ("get_volume",     lambda: self.system_ctrl.unmute_volume()),
            "get_battery":    ("get_battery",    lambda: self.system_ctrl.get_battery()),
            "get_wifi_status":("get_wifi_status",lambda: self.system_ctrl.get_wifi_status()),
            "create_folder":  ("list_files",     lambda: self.file_mgr.create_folder(kwargs.get("path", ""))),
            # Dangerous actions
            "close_app":      ("close_app",      lambda: self.app_mgr.close_app(kwargs.get("process_name", ""))),
            "delete_file":    ("delete_file",    lambda: self.file_mgr.delete_file(kwargs.get("path", ""))),
            "delete_folder":  ("delete_folder",  lambda: self.file_mgr.delete_folder(kwargs.get("path", ""))),
            "rename_file":    ("rename_file",    lambda: self.file_mgr.rename_file(kwargs.get("src", ""), kwargs.get("dest", ""))),
            "run_powershell": ("run_powershell", lambda: self.terminal.run_powershell(kwargs.get("command", ""))),
            "run_cmd":        ("run_cmd",        lambda: self.terminal.run_cmd(kwargs.get("command", ""))),
            "kill_process":   ("kill_process",   lambda: self.system_ctrl.kill_process(int(kwargs.get("pid", 0)))),
        }

        entry = dispatch.get(tool_name)
        if not entry:
            return f"Unknown tool: {tool_name}"

        action_tag, func = entry
        detail_str = f"{tool_name}({kwargs})"
        result = self.security.execute(action_tag, detail_str, func)
        return str(result)

    def chat_stream(self, user_input: str) -> Generator[str, None, None]:
        """
        Processes a user input, updates memory, and yields the LLM response as a stream.
        """
        self.memory.add_message("user", user_input)

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.memory.get_context(user_input))

        full_response = ""
        try:
            for chunk in self.llm.chat_stream(messages):
                full_response += chunk
                yield chunk
        finally:
            if full_response:
                self.memory.add_message("assistant", full_response)

                # Check if the LLM wants to use a tool
                tool_name, kwargs = self._parse_tool_call(full_response)
                if tool_name:
                    tool_result = self._execute_tool(tool_name, kwargs)
                    yield f"\n\n🔧 Tool Result: {tool_result}"

    def chat_sync(self, user_input: str) -> str:
        """Synchronous version of chat."""
        self.memory.add_message("user", user_input)

        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.memory.get_context(user_input))

        response = self.llm.chat_sync(messages)
        if response:
            self.memory.add_message("assistant", response)

            # Check if the LLM wants to use a tool
            tool_name, kwargs = self._parse_tool_call(response)
            if tool_name:
                tool_result = self._execute_tool(tool_name, kwargs)
                return f"{response}\n\n🔧 Tool Result: {tool_result}"

        return response

    def reset_memory(self):
        self.memory.clear_memory()
        logger.info("Memory cleared.")
