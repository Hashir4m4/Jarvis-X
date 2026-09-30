import logging
import platform
from typing import Dict, Any, List, Optional

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.automation.desktop_models import (
    DesktopAction, DesktopActionResult, ActionType,
    WindowActionType, RiskLevel, ActionStatus
)
from backend.automation.desktop_controller import DesktopController
from backend.automation.windows_controller import WindowsDesktopController
from backend.automation.unsupported_controller import UnsupportedDesktopController
from backend.automation.action_queue import ActionQueueManager
from backend.automation.security_proxy import SecurityProxy

logger = logging.getLogger("JARVIS.DesktopSkill")


class DesktopSkill(BaseSkill):
    """
    Skill for Safe Computer Control & Desktop Automation.
    Bridges Orchestrator and User Intent with the concrete DesktopController,
    enforcing Risk Levels, Confirmation, Verification, and Emergency Stop.
    Works 100% offline for deterministic commands.
    """

    def __init__(
        self,
        controller: Optional[DesktopController] = None,
        security_proxy: Optional[SecurityProxy] = None,
        metadata=None
    ):
        super().__init__(metadata=metadata)
        if controller:
            self.controller = controller
        else:
            # Auto-detect OS platform
            os_name = platform.system()
            if os_name == "Windows":
                self.controller = WindowsDesktopController()
            else:
                self.controller = UnsupportedDesktopController(platform_name=os_name)

        self.security = security_proxy or SecurityProxy()
        self.queue_manager = ActionQueueManager(
            controller=self.controller,
            security_proxy=self.security
        )

    @property
    def name(self) -> str:
        return "desktop"

    @property
    def description(self) -> str:
        return "Controls applications, manages files/folders, window actions, and system information safely."

    @property
    def supported_actions(self) -> List[str]:
        return [
            "open_application",
            "close_application",
            "open_app",
            "close_app",
            "open_file",
            "open_folder",
            "create_folder",
            "create_file",
            "rename_file",
            "move_file",
            "copy_file",
            "delete_file",
            "list_directory",
            "organize_directory",
            "organize_files",
            "get_system_info",
            "window_action",
            "gui_action",
            "emergency_stop",
        ]

    def emergency_stop(self):
        """Immediately aborts all queued and active desktop actions."""
        self.queue_manager.trigger_emergency_stop()

    def reset_emergency_stop(self):
        """Resets the emergency stop state."""
        self.queue_manager.reset_emergency_stop()

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        """Executes desktop actions safely through the ActionQueueManager."""
        action = intent.action.lower()
        params = intent.parameters or {}

        # ── 1. Emergency Stop Check ───────────────────────────────────────
        if action in ("emergency_stop", "stop", "abort", "cancel"):
            self.emergency_stop()
            return SkillResult(
                success=True,
                data={"status": "stopped"},
                message="Emergency stop triggered. Automation aborted.",
                output_text="Desktop automation has been immediately halted."
            )

        # ── 2. Normalize and Map to DesktopAction ─────────────────────────
        act_obj: Optional[DesktopAction] = None

        if action in ("open_application", "open_app"):
            app_name = params.get("app_name") or params.get("target") or ""
            if not app_name:
                return SkillResult(success=False, message="Missing application name.", output_text="Which application should I open?")
            act_obj = DesktopAction(
                action_type=ActionType.OPEN_APPLICATION,
                target=app_name,
                parameters={"parameters": params.get("parameters", [])}
            )

        elif action in ("close_application", "close_app"):
            proc_name = params.get("process_name") or params.get("app_name") or params.get("target") or ""
            if not proc_name:
                return SkillResult(success=False, message="Missing application/process name.", output_text="Which application should I close?")
            act_obj = DesktopAction(
                action_type=ActionType.CLOSE_APPLICATION,
                target=proc_name
            )

        elif action == "open_file":
            file_path = params.get("file_path") or params.get("target") or ""
            if not file_path:
                return SkillResult(success=False, message="Missing file path.", output_text="Which file should I open?")
            act_obj = DesktopAction(action_type=ActionType.OPEN_FILE, target=file_path)

        elif action == "open_folder":
            folder_path = params.get("folder_path") or params.get("target") or ""
            if not folder_path:
                return SkillResult(success=False, message="Missing folder path.", output_text="Which folder should I open?")
            act_obj = DesktopAction(action_type=ActionType.OPEN_FOLDER, target=folder_path)

        elif action == "create_folder":
            folder_path = params.get("folder_path") or params.get("target") or ""
            if not folder_path:
                return SkillResult(success=False, message="Missing folder path.", output_text="What should the new folder be named?")
            act_obj = DesktopAction(action_type=ActionType.CREATE_FOLDER, target=folder_path)

        elif action == "create_file":
            file_path = params.get("file_path") or params.get("target") or ""
            act_obj = DesktopAction(
                action_type=ActionType.CREATE_FILE,
                target=file_path,
                parameters={"content": params.get("content", "")}
            )

        elif action == "rename_file":
            src = params.get("src") or params.get("target") or ""
            dest = params.get("dest") or params.get("destination") or params.get("new_name") or ""
            if not src or not dest:
                return SkillResult(success=False, message="Missing source or destination name.", output_text="Please specify the file to rename and its new name.")
            act_obj = DesktopAction(
                action_type=ActionType.RENAME_FILE,
                target=src,
                parameters={"destination": dest}
            )

        elif action == "move_file":
            src = params.get("src") or params.get("target") or ""
            dest = params.get("dest") or params.get("destination") or ""
            if not src or not dest:
                return SkillResult(success=False, message="Missing source or destination.", output_text="Please specify the file to move and destination folder.")
            act_obj = DesktopAction(
                action_type=ActionType.MOVE_FILE,
                target=src,
                parameters={"destination": dest}
            )

        elif action == "copy_file":
            src = params.get("src") or params.get("target") or ""
            dest = params.get("dest") or params.get("destination") or ""
            act_obj = DesktopAction(
                action_type=ActionType.COPY_FILE,
                target=src,
                parameters={"destination": dest}
            )

        elif action == "delete_file":
            file_path = params.get("file_path") or params.get("target") or ""
            if not file_path:
                return SkillResult(success=False, message="Missing file path to delete.", output_text="Which file should I delete?")
            act_obj = DesktopAction(
                action_type=ActionType.DELETE_FILE,
                target=file_path
            )

        elif action == "list_directory":
            folder_path = params.get("folder_path") or params.get("target") or "."
            act_obj = DesktopAction(action_type=ActionType.LIST_DIRECTORY, target=folder_path)

        elif action in ("organize_directory", "organize_files"):
            folder_path = params.get("folder_path") or params.get("target") or ""
            if not folder_path:
                return SkillResult(success=False, message="Missing folder path to organize.", output_text="Which folder would you like me to organize?")
            act_obj = DesktopAction(
                action_type=ActionType.ORGANIZE_FILES,
                target=folder_path,
                parameters={"rules": params.get("rules")}
            )

        elif action == "get_system_info":
            act_obj = DesktopAction(action_type=ActionType.GET_SYSTEM_INFO)

        elif action == "window_action":
            wact_str = params.get("window_action", "minimize").upper()
            try:
                wact = WindowActionType(wact_str)
            except ValueError:
                wact = WindowActionType.MINIMIZE
            act_obj = DesktopAction(
                action_type=ActionType.WINDOW_ACTION,
                target=params.get("target", ""),
                parameters={"window_action": wact}
            )

        elif action == "gui_action":
            act_obj = DesktopAction(
                action_type=ActionType.GUI_ACTION,
                target=params.get("action_name", "type"),
                parameters=params
            )

        else:
            return SkillResult(
                success=False,
                message=f"Unsupported desktop action '{action}'.",
                output_text=f"I don't know how to perform the desktop action '{action}'."
            )

        # ── 3. Execute via ActionQueueManager ─────────────────────────────
        result = self.queue_manager.execute_single(act_obj)

        return SkillResult(
            success=result.success,
            data=result.to_dict(),
            message=result.message,
            output_text=result.message
        )
