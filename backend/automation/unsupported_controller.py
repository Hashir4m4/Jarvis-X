import logging
from typing import Dict, Any, Optional, List
from .desktop_models import (
    DesktopAction, DesktopActionResult, ActionType,
    WindowActionType, RiskLevel, ActionStatus
)
from .desktop_controller import DesktopController

logger = logging.getLogger("JARVIS.UnsupportedController")


class UnsupportedDesktopController(DesktopController):
    """
    Controller stub for unsupported operating systems (e.g. Linux/macOS when not implemented).
    Never pretends unsupported features work; always reports explicit capability status.
    """

    def __init__(self, platform_name: str = "Unsupported"):
        self.platform_name = platform_name

    def get_platform_name(self) -> str:
        return self.platform_name

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "open_application": False,
            "close_application": False,
            "open_file": False,
            "open_folder": False,
            "create_folder": False,
            "create_file": False,
            "rename_file": False,
            "move_file": False,
            "copy_file": False,
            "delete_file": False,
            "list_directory": False,
            "organize_directory": False,
            "window_control": False,
            "system_info": False,
            "gui_interaction": False,
        }

    def _unsupported_result(self, action_type: ActionType, action_name: str) -> DesktopActionResult:
        return DesktopActionResult(
            success=False,
            action_id="unsupported",
            action_type=action_type,
            message=f"Action '{action_name}' is not supported on platform '{self.platform_name}'.",
            risk_level=RiskLevel.SAFE,
            status=ActionStatus.FAILED,
            verified=False
        )

    def open_application(self, app_name: str, parameters: Optional[List[str]] = None) -> DesktopActionResult:
        return self._unsupported_result(ActionType.OPEN_APPLICATION, "open_application")

    def close_application(self, process_or_title: str) -> DesktopActionResult:
        return self._unsupported_result(ActionType.CLOSE_APPLICATION, "close_application")

    def open_file(self, file_path: str) -> DesktopActionResult:
        return self._unsupported_result(ActionType.OPEN_FILE, "open_file")

    def open_folder(self, folder_path: str) -> DesktopActionResult:
        return self._unsupported_result(ActionType.OPEN_FOLDER, "open_folder")

    def create_folder(self, folder_path: str) -> DesktopActionResult:
        return self._unsupported_result(ActionType.CREATE_FOLDER, "create_folder")

    def create_file(self, file_path: str, content: str = "") -> DesktopActionResult:
        return self._unsupported_result(ActionType.CREATE_FILE, "create_file")

    def rename_file(self, src: str, dest: str) -> DesktopActionResult:
        return self._unsupported_result(ActionType.RENAME_FILE, "rename_file")

    def move_file(self, src: str, dest: str) -> DesktopActionResult:
        return self._unsupported_result(ActionType.MOVE_FILE, "move_file")

    def copy_file(self, src: str, dest: str) -> DesktopActionResult:
        return self._unsupported_result(ActionType.COPY_FILE, "copy_file")

    def delete_file(self, file_path: str) -> DesktopActionResult:
        return self._unsupported_result(ActionType.DELETE_FILE, "delete_file")

    def list_directory(self, folder_path: str) -> DesktopActionResult:
        return self._unsupported_result(ActionType.LIST_DIRECTORY, "list_directory")

    def organize_directory(self, folder_path: str, rule_mapping: Optional[Dict[str, List[str]]] = None) -> DesktopActionResult:
        return self._unsupported_result(ActionType.ORGANIZE_FILES, "organize_directory")

    def window_action(self, action: WindowActionType, target_title: Optional[str] = None) -> DesktopActionResult:
        return self._unsupported_result(ActionType.WINDOW_ACTION, f"window_{action.value}")

    def get_system_info(self) -> DesktopActionResult:
        return self._unsupported_result(ActionType.GET_SYSTEM_INFO, "get_system_info")

    def gui_action(self, action_name: str, params: Dict[str, Any]) -> DesktopActionResult:
        return self._unsupported_result(ActionType.GUI_ACTION, f"gui_{action_name}")

    def verify_action(self, action: DesktopAction) -> bool:
        return False
