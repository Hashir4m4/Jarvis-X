import logging
import subprocess
import os

logger = logging.getLogger(__name__)

# Map of common app names to their executable paths / start commands on Windows
APP_REGISTRY = {
    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
    "vscode": "code",
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "paint": "mspaint.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "word": r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    "excel": r"C:\Program Files\Microsoft Office\root\Office16\EXCEL.EXE",
    "spotify": os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
    "discord": os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe --processStart Discord.exe"),
    "github desktop": os.path.expandvars(r"%LOCALAPPDATA%\GitHubDesktop\GitHubDesktop.exe"),
}


class AppManager:
    """Opens, closes, and manages Windows applications."""

    def open_app(self, app_name: str) -> dict:
        """Opens an application by its friendly name or full path."""
        app_key = app_name.lower().strip()

        # Check the registry first
        exe_path = APP_REGISTRY.get(app_key)
        if exe_path:
            return self._launch(exe_path, app_name)

        # Try launching it as a raw command (might be on PATH)
        return self._launch(app_name, app_name)

    def _launch(self, command: str, display_name: str) -> dict:
        try:
            # Use subprocess.Popen so it doesn't block
            subprocess.Popen(command, shell=True)
            logger.info(f"Launched: {display_name}")
            return {"status": "ok", "message": f"Opened {display_name}."}
        except FileNotFoundError:
            logger.error(f"Application not found: {command}")
            return {"status": "error", "message": f"Could not find application: {display_name}."}
        except Exception as e:
            logger.error(f"Error opening {display_name}: {e}")
            return {"status": "error", "message": str(e)}

    def close_app(self, process_name: str) -> dict:
        """Closes an application by its process name (e.g. 'chrome.exe')."""
        try:
            # taskkill is the standard Windows way
            result = subprocess.run(
                ["taskkill", "/IM", process_name, "/F"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return {"status": "ok", "message": f"Closed {process_name}."}
            else:
                return {"status": "error", "message": result.stderr.strip()}
        except Exception as e:
            logger.error(f"Error closing {process_name}: {e}")
            return {"status": "error", "message": str(e)}

    def minimize_window(self) -> dict:
        """Minimizes the currently active window."""
        try:
            import pyautogui
            pyautogui.hotkey('win', 'down')
            return {"status": "ok", "message": "Window minimized."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def maximize_window(self) -> dict:
        """Maximizes the currently active window."""
        try:
            import pyautogui
            pyautogui.hotkey('win', 'up')
            return {"status": "ok", "message": "Window maximized."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
