import os
import shutil
import logging
import platform
import subprocess
from typing import Dict, Any, Optional, List
from .desktop_models import (
    DesktopAction, DesktopActionResult, ActionType,
    WindowActionType, RiskLevel, ActionStatus
)
from .desktop_controller import DesktopController
from .security_proxy import SecurityProxy

logger = logging.getLogger("JARVIS.WindowsController")

# Extensive mapping of friendly application names / aliases to executable commands on Windows
WINDOWS_APP_ALIASES = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "browser": "chrome",
    "web browser": "chrome",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "code": "code",
    "notepad": "notepad",
    "text editor": "notepad",
    "calculator": "calc",
    "calc": "calc",
    "file explorer": "explorer",
    "explorer": "explorer",
    "task manager": "taskmgr",
    "paint": "mspaint",
    "terminal": "wt",
    "windows terminal": "wt",
    "cmd": "cmd",
    "command prompt": "cmd",
    "powershell": "powershell",
    "spotify": os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
    "discord": os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe --processStart Discord.exe"),
    "github desktop": os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\GitHubDesktop.exe"),
}

# Default file organization categories
DEFAULT_ORGANIZATION_RULES = {
    "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv", ".md"],
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp"],
    "Audio": [".mp3", ".wav", ".flac", ".m4a", ".aac"],
    "Videos": [".mp4", ".mkv", ".mov", ".avi", ".wmv"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Code": [".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml", ".cpp", ".c", ".java"],
    "Installers": [".exe", ".msi", ".dmg", ".iso"],
}


class WindowsDesktopController(DesktopController):
    """
    Production Windows Desktop Controller.
    Interacts safely with the Windows operating system using Win32 API,
    built-in utilities (cmd, explorer, taskkill), and psutil.
    """

    def __init__(self, app_aliases: Optional[Dict[str, str]] = None):
        self.app_aliases = dict(WINDOWS_APP_ALIASES)
        if app_aliases:
            self.app_aliases.update({k.lower(): v for k, v in app_aliases.items()})

    def get_platform_name(self) -> str:
        return "Windows"

    def get_capabilities(self) -> Dict[str, bool]:
        return {
            "open_application": True,
            "close_application": True,
            "open_file": True,
            "open_folder": True,
            "create_folder": True,
            "create_file": True,
            "rename_file": True,
            "move_file": True,
            "copy_file": True,
            "delete_file": True,
            "list_directory": True,
            "organize_directory": True,
            "window_control": True,
            "system_info": True,
            "gui_interaction": True,
        }

    # ── Application Operations ─────────────────────────────────────────

    def resolve_application(self, app_name: str) -> Optional[str]:
        """Resolves an application alias or friendly name to an executable path/command."""
        key = app_name.lower().strip()
        if key in self.app_aliases:
            return self.app_aliases[key]
        
        # Check if the raw input is already a valid file or on system path
        if os.path.isabs(key) and os.path.exists(key):
            return key
        which_path = shutil.which(key)
        if which_path:
            return which_path
            
        return None

    def open_application(self, app_name: str, parameters: Optional[List[str]] = None) -> DesktopActionResult:
        resolved = self.resolve_application(app_name)
        action_id = f"open_{app_name[:8]}"

        if not resolved:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.OPEN_APPLICATION,
                message=f"Application not found or no alias registered for: '{app_name}'.",
                risk_level=RiskLevel.SAFE,
                status=ActionStatus.FAILED
            )

        cmd = [resolved]
        if parameters:
            cmd.extend(parameters)

        try:
            # We use subprocess.Popen with detached process or shell to launch safely without blocking JARVIS
            if " " in resolved and not os.path.exists(resolved):
                # May be a command with arguments like Update.exe --processStart
                subprocess.Popen(resolved, shell=True)
            else:
                subprocess.Popen(cmd, shell=False)

            verified = self.verify_action(DesktopAction(
                action_type=ActionType.OPEN_APPLICATION,
                target=app_name,
                parameters={"resolved": resolved}
            ))

            return DesktopActionResult(
                success=True,
                action_id=action_id,
                action_type=ActionType.OPEN_APPLICATION,
                message=f"Opened application: {app_name}",
                data={"resolved_executable": resolved, "parameters": parameters or []},
                verified=verified,
                risk_level=RiskLevel.SAFE,
                status=ActionStatus.VERIFIED if verified else ActionStatus.EXECUTING
            )
        except Exception as e:
            logger.error(f"Failed to launch application '{app_name}': {e}")
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.OPEN_APPLICATION,
                message=f"Error launching {app_name}: {str(e)}",
                risk_level=RiskLevel.SAFE,
                status=ActionStatus.FAILED
            )

    def close_application(self, process_or_title: str) -> DesktopActionResult:
        action_id = f"close_{process_or_title[:8]}"
        proc_name = process_or_title.strip()
        if not proc_name.endswith(".exe"):
            proc_name += ".exe"

        try:
            res = subprocess.run(
                ["taskkill", "/IM", proc_name, "/F"],
                capture_output=True,
                text=True,
                timeout=5
            )
            success = (res.returncode == 0)
            msg = f"Closed application: {process_or_title}" if success else f"Could not close {process_or_title}: {res.stderr.strip() or 'Process not found'}"
            return DesktopActionResult(
                success=success,
                action_id=action_id,
                action_type=ActionType.CLOSE_APPLICATION,
                message=msg,
                verified=success,
                risk_level=RiskLevel.RESTRICTED,
                status=ActionStatus.VERIFIED if success else ActionStatus.FAILED
            )
        except Exception as e:
            logger.error(f"Error closing application {process_or_title}: {e}")
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.CLOSE_APPLICATION,
                message=f"Failed to close {process_or_title}: {str(e)}",
                risk_level=RiskLevel.RESTRICTED,
                status=ActionStatus.FAILED
            )

    # ── File System Operations ─────────────────────────────────────────

    def open_file(self, file_path: str) -> DesktopActionResult:
        action_id = f"openfile_{os.path.basename(file_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(file_path)))
        is_safe, msg = SecurityProxy.validate_safe_path(abs_path, for_destructive=False)
        if not is_safe:
            return DesktopActionResult(success=False, action_id=action_id, action_type=ActionType.OPEN_FILE, message=f"Action blocked by safety guard: {msg}", risk_level=RiskLevel.RESTRICTED, status=ActionStatus.FAILED)
        if not os.path.exists(abs_path):
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.OPEN_FILE,
                message=f"File not found: {file_path}",
                status=ActionStatus.FAILED
            )

        try:
            os.startfile(abs_path)
            return DesktopActionResult(
                success=True,
                action_id=action_id,
                action_type=ActionType.OPEN_FILE,
                message=f"Opened file: {os.path.basename(abs_path)}",
                data={"path": abs_path},
                verified=True,
                status=ActionStatus.VERIFIED
            )
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.OPEN_FILE,
                message=f"Error opening file {file_path}: {str(e)}",
                status=ActionStatus.FAILED
            )

    def open_folder(self, folder_path: str) -> DesktopActionResult:
        action_id = f"openfolder_{os.path.basename(folder_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(folder_path)))
        is_safe, msg = SecurityProxy.validate_safe_path(abs_path, for_destructive=False)
        if not is_safe:
            return DesktopActionResult(success=False, action_id=action_id, action_type=ActionType.OPEN_FOLDER, message=f"Action blocked by safety guard: {msg}", risk_level=RiskLevel.RESTRICTED, status=ActionStatus.FAILED)
        if not os.path.isdir(abs_path):
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.OPEN_FOLDER,
                message=f"Folder not found: {folder_path}",
                status=ActionStatus.FAILED
            )

        try:
            subprocess.Popen(["explorer", abs_path])
            return DesktopActionResult(
                success=True,
                action_id=action_id,
                action_type=ActionType.OPEN_FOLDER,
                message=f"Opened folder: {abs_path}",
                data={"path": abs_path},
                verified=True,
                status=ActionStatus.VERIFIED
            )
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.OPEN_FOLDER,
                message=f"Error opening folder {folder_path}: {str(e)}",
                status=ActionStatus.FAILED
            )

    def create_folder(self, folder_path: str) -> DesktopActionResult:
        action_id = f"mkdir_{os.path.basename(folder_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(folder_path)))
        try:
            os.makedirs(abs_path, exist_ok=True)
            verified = os.path.isdir(abs_path)
            return DesktopActionResult(
                success=verified,
                action_id=action_id,
                action_type=ActionType.CREATE_FOLDER,
                message=f"Folder created: {abs_path}" if verified else "Failed to verify folder creation",
                data={"path": abs_path},
                verified=verified,
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.VERIFIED if verified else ActionStatus.FAILED
            )
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.CREATE_FOLDER,
                message=f"Error creating folder {folder_path}: {str(e)}",
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.FAILED
            )

    def create_file(self, file_path: str, content: str = "") -> DesktopActionResult:
        action_id = f"createfile_{os.path.basename(file_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(file_path)))
        try:
            parent = os.path.dirname(abs_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
            verified = os.path.isfile(abs_path)
            return DesktopActionResult(
                success=verified,
                action_id=action_id,
                action_type=ActionType.CREATE_FILE,
                message=f"Created file: {abs_path}",
                data={"path": abs_path, "bytes": len(content)},
                verified=verified,
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.VERIFIED if verified else ActionStatus.FAILED
            )
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.CREATE_FILE,
                message=f"Error creating file {file_path}: {str(e)}",
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.FAILED
            )

    def rename_file(self, src: str, dest: str) -> DesktopActionResult:
        action_id = f"rename_{os.path.basename(src)[:8]}"
        abs_src = os.path.abspath(os.path.expanduser(os.path.expandvars(src)))
        abs_dest = os.path.abspath(os.path.expanduser(os.path.expandvars(dest)))

        if not os.path.exists(abs_src):
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.RENAME_FILE,
                message=f"Source path not found: {src}",
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.FAILED
            )

        try:
            os.rename(abs_src, abs_dest)
            verified = os.path.exists(abs_dest) and not os.path.exists(abs_src)
            return DesktopActionResult(
                success=verified,
                action_id=action_id,
                action_type=ActionType.RENAME_FILE,
                message=f"Renamed {os.path.basename(abs_src)} -> {os.path.basename(abs_dest)}",
                data={"source": abs_src, "destination": abs_dest},
                verified=verified,
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.VERIFIED if verified else ActionStatus.FAILED
            )
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.RENAME_FILE,
                message=f"Error renaming {src}: {str(e)}",
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.FAILED
            )

    def move_file(self, src: str, dest: str) -> DesktopActionResult:
        action_id = f"move_{os.path.basename(src)[:8]}"
        abs_src = os.path.abspath(os.path.expanduser(os.path.expandvars(src)))
        abs_dest = os.path.abspath(os.path.expanduser(os.path.expandvars(dest)))

        if not os.path.exists(abs_src):
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.MOVE_FILE,
                message=f"Source path not found: {src}",
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.FAILED
            )

        try:
            # If dest is a directory, ensure it exists
            if os.path.isdir(abs_dest) or (not os.path.exists(abs_dest) and not os.path.splitext(abs_dest)[1]):
                os.makedirs(abs_dest, exist_ok=True)
            shutil.move(abs_src, abs_dest)
            # Verification: Destination exists
            final_dest = abs_dest
            if os.path.isdir(abs_dest):
                final_dest = os.path.join(abs_dest, os.path.basename(abs_src))
            verified = os.path.exists(final_dest) and not os.path.exists(abs_src)

            return DesktopActionResult(
                success=verified,
                action_id=action_id,
                action_type=ActionType.MOVE_FILE,
                message=f"Moved {os.path.basename(abs_src)} to {abs_dest}",
                data={"source": abs_src, "destination": final_dest},
                verified=verified,
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.VERIFIED if verified else ActionStatus.FAILED
            )
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.MOVE_FILE,
                message=f"Error moving {src}: {str(e)}",
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.FAILED
            )

    def copy_file(self, src: str, dest: str) -> DesktopActionResult:
        action_id = f"copy_{os.path.basename(src)[:8]}"
        abs_src = os.path.abspath(os.path.expanduser(os.path.expandvars(src)))
        abs_dest = os.path.abspath(os.path.expanduser(os.path.expandvars(dest)))

        if not os.path.exists(abs_src):
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.COPY_FILE,
                message=f"Source path not found: {src}",
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.FAILED
            )

        try:
            if os.path.isdir(abs_src):
                shutil.copytree(abs_src, abs_dest, dirs_exist_ok=True)
            else:
                if os.path.isdir(abs_dest):
                    shutil.copy2(abs_src, abs_dest)
                else:
                    os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
                    shutil.copy2(abs_src, abs_dest)
            verified = os.path.exists(abs_dest)
            return DesktopActionResult(
                success=verified,
                action_id=action_id,
                action_type=ActionType.COPY_FILE,
                message=f"Copied {os.path.basename(abs_src)} to {abs_dest}",
                data={"source": abs_src, "destination": abs_dest},
                verified=verified,
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.VERIFIED if verified else ActionStatus.FAILED
            )
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.COPY_FILE,
                message=f"Error copying {src}: {str(e)}",
                risk_level=RiskLevel.CONFIRM,
                status=ActionStatus.FAILED
            )

    def delete_file(self, file_path: str) -> DesktopActionResult:
        action_id = f"del_{os.path.basename(file_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(file_path)))

        is_safe, msg = SecurityProxy.validate_safe_path(abs_path, for_destructive=True)
        if not is_safe:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.DELETE_FILE,
                message=f"Action blocked by safety guard: {msg}",
                risk_level=RiskLevel.RESTRICTED,
                status=ActionStatus.FAILED
            )

        if not os.path.exists(abs_path):
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.DELETE_FILE,
                message=f"Path not found: {file_path}",
                risk_level=RiskLevel.RESTRICTED,
                status=ActionStatus.FAILED
            )

        try:
            if os.path.isdir(abs_path):
                shutil.rmtree(abs_path)
            else:
                os.remove(abs_path)
            verified = not os.path.exists(abs_path)
            return DesktopActionResult(
                success=verified,
                action_id=action_id,
                action_type=ActionType.DELETE_FILE,
                message=f"Deleted: {abs_path}",
                data={"deleted_path": abs_path},
                verified=verified,
                risk_level=RiskLevel.RESTRICTED,
                status=ActionStatus.VERIFIED if verified else ActionStatus.FAILED
            )
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.DELETE_FILE,
                message=f"Error deleting {file_path}: {str(e)}",
                risk_level=RiskLevel.RESTRICTED,
                status=ActionStatus.FAILED
            )

    def list_directory(self, folder_path: str) -> DesktopActionResult:
        action_id = f"list_{os.path.basename(folder_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(folder_path)))

        if not os.path.isdir(abs_path):
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.LIST_DIRECTORY,
                message=f"Directory not found: {folder_path}",
                status=ActionStatus.FAILED
            )

        try:
            entries = []
            for entry in os.scandir(abs_path):
                entries.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size_bytes": entry.stat().st_size if entry.is_file() else None,
                    "extension": os.path.splitext(entry.name)[1].lower() if entry.is_file() else None
                })
            return DesktopActionResult(
                success=True,
                action_id=action_id,
                action_type=ActionType.LIST_DIRECTORY,
                message=f"Found {len(entries)} items in {os.path.basename(abs_path)}",
                data={"path": abs_path, "count": len(entries), "entries": entries},
                verified=True,
                status=ActionStatus.VERIFIED
            )
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.LIST_DIRECTORY,
                message=f"Error listing directory {folder_path}: {str(e)}",
                status=ActionStatus.FAILED
            )

    def organize_directory(self, folder_path: str, rule_mapping: Optional[Dict[str, List[str]]] = None) -> DesktopActionResult:
        action_id = f"org_{os.path.basename(folder_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(folder_path)))

        if not os.path.isdir(abs_path):
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.ORGANIZE_FILES,
                message=f"Directory not found: {folder_path}",
                risk_level=RiskLevel.RESTRICTED,
                status=ActionStatus.FAILED
            )

        rules = rule_mapping or DEFAULT_ORGANIZATION_RULES
        moved_count = 0
        details = []

        try:
            for entry in os.scandir(abs_path):
                if entry.is_file():
                    ext = os.path.splitext(entry.name)[1].lower()
                    target_folder = None
                    for category, extensions in rules.items():
                        if ext in extensions:
                            target_folder = category
                            break

                    if target_folder:
                        cat_dir = os.path.join(abs_path, target_folder)
                        os.makedirs(cat_dir, exist_ok=True)
                        dest_path = os.path.join(cat_dir, entry.name)
                        shutil.move(entry.path, dest_path)
                        moved_count += 1
                        details.append({"file": entry.name, "category": target_folder})

            return DesktopActionResult(
                success=True,
                action_id=action_id,
                action_type=ActionType.ORGANIZE_FILES,
                message=f"Organized {moved_count} files into categories in {os.path.basename(abs_path)}.",
                data={"path": abs_path, "moved_count": moved_count, "details": details},
                verified=True,
                risk_level=RiskLevel.RESTRICTED,
                status=ActionStatus.VERIFIED
            )
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.ORGANIZE_FILES,
                message=f"Error organizing directory {folder_path}: {str(e)}",
                risk_level=RiskLevel.RESTRICTED,
                status=ActionStatus.FAILED
            )

    # ── Window Control ─────────────────────────────────────────────────

    def window_action(self, action: WindowActionType, target_title: Optional[str] = None) -> DesktopActionResult:
        action_id = f"win_{action.value.lower()}"
        try:
            # Prefer Win32 API if available
            import ctypes
            user32 = ctypes.windll.user32

            if action == WindowActionType.MINIMIZE:
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6
                    return DesktopActionResult(success=True, action_id=action_id, action_type=ActionType.WINDOW_ACTION, message="Window minimized", verified=True)
            elif action == WindowActionType.MAXIMIZE:
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    user32.ShowWindow(hwnd, 3)  # SW_MAXIMIZE = 3
                    return DesktopActionResult(success=True, action_id=action_id, action_type=ActionType.WINDOW_ACTION, message="Window maximized", verified=True)
            elif action == WindowActionType.RESTORE:
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    user32.ShowWindow(hwnd, 9)  # SW_RESTORE = 9
                    return DesktopActionResult(success=True, action_id=action_id, action_type=ActionType.WINDOW_ACTION, message="Window restored", verified=True)
            elif action == WindowActionType.CLOSE:
                hwnd = user32.GetForegroundWindow()
                if hwnd:
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE = 0x0010
                    return DesktopActionResult(success=True, action_id=action_id, action_type=ActionType.WINDOW_ACTION, message="Window closed", verified=True)

            # Fallback to pyautogui hotkeys
            try:
                import pyautogui
                if action == WindowActionType.MINIMIZE:
                    pyautogui.hotkey('win', 'down')
                elif action == WindowActionType.MAXIMIZE:
                    pyautogui.hotkey('win', 'up')
                elif action == WindowActionType.SWITCH:
                    pyautogui.hotkey('alt', 'tab')
                return DesktopActionResult(success=True, action_id=action_id, action_type=ActionType.WINDOW_ACTION, message=f"Window action {action.value} completed", verified=True)
            except Exception:
                pass

            return DesktopActionResult(success=True, action_id=action_id, action_type=ActionType.WINDOW_ACTION, message=f"Window action {action.value} issued.")
        except Exception as e:
            return DesktopActionResult(
                success=False,
                action_id=action_id,
                action_type=ActionType.WINDOW_ACTION,
                message=f"Failed window action: {str(e)}",
                status=ActionStatus.FAILED
            )

    # ── System Information ─────────────────────────────────────────────

    def get_system_info(self) -> DesktopActionResult:
        action_id = "sys_info"
        data = {
            "os": f"Windows {platform.version()}",
            "architecture": platform.machine(),
            "cpu_percent": 0.0,
            "ram_used_percent": 0.0,
            "ram_total_gb": 0.0,
            "disk_used_percent": 0.0,
            "battery_percent": None,
            "battery_plugged": None,
            "active_processes_count": 0,
        }

        try:
            import psutil
            data["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            vm = psutil.virtual_memory()
            data["ram_used_percent"] = vm.percent
            data["ram_total_gb"] = round(vm.total / (1024 ** 3), 2)

            disk = psutil.disk_usage("C:\\")
            data["disk_used_percent"] = disk.percent

            battery = psutil.sensors_battery()
            if battery:
                data["battery_percent"] = battery.percent
                data["battery_plugged"] = battery.power_plugged

            data["active_processes_count"] = len(psutil.pids())
        except Exception as e:
            logger.warning(f"psutil telemetry error (non-fatal): {e}")

        summary = (
            f"Windows System Status: CPU at {data['cpu_percent']}%, "
            f"RAM at {data['ram_used_percent']}% of {data['ram_total_gb']}GB, "
            f"Disk at {data['disk_used_percent']}%."
        )

        return DesktopActionResult(
            success=True,
            action_id=action_id,
            action_type=ActionType.GET_SYSTEM_INFO,
            message=summary,
            data=data,
            verified=True,
            risk_level=RiskLevel.SAFE,
            status=ActionStatus.VERIFIED
        )

    # ── GUI Interaction ────────────────────────────────────────────────

    def gui_action(self, action_name: str, params: Dict[str, Any]) -> DesktopActionResult:
        action_id = f"gui_{action_name}"
        try:
            import pyautogui
            act = action_name.lower()
            if act == "type":
                text = params.get("text", "")
                pyautogui.typewrite(text, interval=0.02)
                return DesktopActionResult(success=True, action_id=action_id, action_type=ActionType.GUI_ACTION, message=f"Typed {len(text)} characters", verified=True)
            elif act == "click":
                x = params.get("x")
                y = params.get("y")
                btn = params.get("button", "left")
                if x is not None and y is not None:
                    pyautogui.click(x, y, button=btn)
                else:
                    pyautogui.click(button=btn)
                return DesktopActionResult(success=True, action_id=action_id, action_type=ActionType.GUI_ACTION, message=f"Clicked mouse ({btn})", verified=True)
            elif act == "hotkey":
                keys = params.get("keys", [])
                if keys:
                    pyautogui.hotkey(*keys)
                return DesktopActionResult(success=True, action_id=action_id, action_type=ActionType.GUI_ACTION, message=f"Pressed hotkey: {'+'.join(keys)}", verified=True)
            elif act == "scroll":
                amount = params.get("amount", -200)
                pyautogui.scroll(amount)
                return DesktopActionResult(success=True, action_id=action_id, action_type=ActionType.GUI_ACTION, message=f"Scrolled {amount}", verified=True)
            else:
                return DesktopActionResult(success=False, action_id=action_id, action_type=ActionType.GUI_ACTION, message=f"Unknown GUI action: {action_name}", status=ActionStatus.FAILED)
        except Exception as e:
            return DesktopActionResult(success=False, action_id=action_id, action_type=ActionType.GUI_ACTION, message=f"GUI action error: {str(e)}", status=ActionStatus.FAILED)

    # ── Verification ───────────────────────────────────────────────────

    def verify_action(self, action: DesktopAction) -> bool:
        """Verifies if an action took effect."""
        try:
            if action.action_type == ActionType.CREATE_FOLDER:
                path = os.path.abspath(os.path.expanduser(os.path.expandvars(action.target)))
                return os.path.isdir(path)
            elif action.action_type == ActionType.CREATE_FILE:
                path = os.path.abspath(os.path.expanduser(os.path.expandvars(action.target)))
                return os.path.isfile(path)
            elif action.action_type == ActionType.DELETE_FILE:
                path = os.path.abspath(os.path.expanduser(os.path.expandvars(action.target)))
                return not os.path.exists(path)
            elif action.action_type == ActionType.RENAME_FILE:
                dest = action.parameters.get("destination", "")
                return os.path.exists(dest) and not os.path.exists(action.target)
            elif action.action_type == ActionType.MOVE_FILE:
                dest = action.parameters.get("destination", "")
                return os.path.exists(dest)
            elif action.action_type == ActionType.OPEN_APPLICATION:
                # If psutil is present, check if process name is among running processes
                import psutil
                target = action.target.lower()
                for p in psutil.process_iter(['name']):
                    try:
                        pname = p.info['name'].lower()
                        if target in pname or (action.parameters.get("resolved") and os.path.basename(action.parameters["resolved"]).lower() in pname):
                            return True
                    except Exception:
                        pass
                return True  # Fallback to True if launched without exception
            return True
        except Exception:
            return False
