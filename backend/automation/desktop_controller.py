import abc
import logging
from typing import Dict, Any, Optional, List
from .desktop_models import (
    DesktopAction, DesktopActionResult, ActionType,
    WindowActionType, RiskLevel, ActionStatus
)

logger = logging.getLogger("JARVIS.DesktopController")


class DesktopController(abc.ABC):
    """
    Abstract Operating System Controller for Safe Desktop Automation.
    Defines the standard interface across Windows, Linux, and macOS.
    """

    @abc.abstractmethod
    def get_platform_name(self) -> str:
        """Returns the canonical name of the operating system."""
        pass

    @abc.abstractmethod
    def get_capabilities(self) -> Dict[str, bool]:
        """
        Returns a dictionary of supported capabilities on this platform.
        e.g. {"open_application": True, "window_control": True, ...}
        """
        pass

    # ── Application Operations ─────────────────────────────────────────

    @abc.abstractmethod
    def open_application(self, app_name: str, parameters: Optional[List[str]] = None) -> DesktopActionResult:
        """Opens an application safely using alias resolution or executable path."""
        pass

    @abc.abstractmethod
    def close_application(self, process_or_title: str) -> DesktopActionResult:
        """Closes an application safely."""
        pass

    # ── File System Operations ─────────────────────────────────────────

    @abc.abstractmethod
    def open_file(self, file_path: str) -> DesktopActionResult:
        """Opens a file using the default OS association."""
        pass

    @abc.abstractmethod
    def open_folder(self, folder_path: str) -> DesktopActionResult:
        """Opens a directory in the default file manager."""
        pass

    @abc.abstractmethod
    def create_folder(self, folder_path: str) -> DesktopActionResult:
        """Creates a directory if it does not exist."""
        pass

    @abc.abstractmethod
    def create_file(self, file_path: str, content: str = "") -> DesktopActionResult:
        """Creates or writes a file."""
        pass

    @abc.abstractmethod
    def rename_file(self, src: str, dest: str) -> DesktopActionResult:
        """Renames a file or directory."""
        pass

    @abc.abstractmethod
    def move_file(self, src: str, dest: str) -> DesktopActionResult:
        """Moves a file or folder from src to dest."""
        pass

    @abc.abstractmethod
    def copy_file(self, src: str, dest: str) -> DesktopActionResult:
        """Copies a file or folder from src to dest."""
        pass

    @abc.abstractmethod
    def delete_file(self, file_path: str) -> DesktopActionResult:
        """Deletes a file (protected by confirmation)."""
        pass

    @abc.abstractmethod
    def list_directory(self, folder_path: str) -> DesktopActionResult:
        """Lists files and folders inside folder_path."""
        pass

    @abc.abstractmethod
    def organize_directory(self, folder_path: str, rule_mapping: Optional[Dict[str, List[str]]] = None) -> DesktopActionResult:
        """Organizes files into categories based on file extensions."""
        pass

    # ── Window Control ─────────────────────────────────────────────────

    @abc.abstractmethod
    def window_action(self, action: WindowActionType, target_title: Optional[str] = None) -> DesktopActionResult:
        """Performs window operations (minimize, maximize, restore, focus, close)."""
        pass

    # ── System Information ─────────────────────────────────────────────

    @abc.abstractmethod
    def get_system_info(self) -> DesktopActionResult:
        """Returns safe read-only hardware, OS, and process telemetry."""
        pass

    # ── GUI Interaction ────────────────────────────────────────────────

    @abc.abstractmethod
    def gui_action(self, action_name: str, params: Dict[str, Any]) -> DesktopActionResult:
        """Performs structured, safe GUI interaction (typing, clicking, hotkeys)."""
        pass

    # ── Verification ───────────────────────────────────────────────────

    @abc.abstractmethod
    def verify_action(self, action: DesktopAction) -> bool:
        """Verifies whether a previously executed action actually took effect."""
        pass
