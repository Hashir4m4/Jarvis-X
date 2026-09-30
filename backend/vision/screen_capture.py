import abc
import os
import time
import uuid
import logging
from typing import Optional, Tuple, Dict, Any, List
from PIL import Image

from .screen_models import CaptureType, WindowMetadata, StoragePolicy

logger = logging.getLogger("JARVIS.ScreenCapture")

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False


class ScreenCaptureProvider(abc.ABC):
    """Abstract provider for on-demand screen capturing."""

    @abc.abstractmethod
    def is_available(self) -> bool:
        """Checks if screen capture capability is present."""
        pass

    @abc.abstractmethod
    def capture_screen(self, display_index: int = 0) -> Optional[Image.Image]:
        """Captures a screenshot of the specified display."""
        pass

    @abc.abstractmethod
    def capture_region(self, x: int, y: int, width: int, height: int) -> Optional[Image.Image]:
        """Captures a specific bounding rectangle of the screen."""
        pass

    @abc.abstractmethod
    def capture_active_window(self) -> Tuple[Optional[Image.Image], WindowMetadata]:
        """Captures the currently focused active window with its metadata."""
        pass

    @abc.abstractmethod
    def list_displays(self) -> List[Dict[str, Any]]:
        """Lists connected monitors/displays."""
        pass

    @abc.abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Returns health diagnostics for screen capture subsystem."""
        pass


class DefaultScreenCaptureProvider(ScreenCaptureProvider):
    """
    Production screen capture provider.
    Captures full screen, active windows, or custom regions using PyAutoGUI, PIL,
    and Win32 APIs when running on Windows.
    Enforces on-demand capture only and temporary screenshot storage.
    """

    def __init__(self, temp_storage_dir: Optional[str] = None):
        self.temp_storage_dir = temp_storage_dir or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../logs/screenshots")
        )
        os.makedirs(self.temp_storage_dir, exist_ok=True)
        self.storage_policy = StoragePolicy.TEMPORARY
        self.max_temp_age_seconds = 300  # 5 minutes expiry for screenshots

    def is_available(self) -> bool:
        return _PYAUTOGUI

    def capture_screen(self, display_index: int = 0) -> Optional[Image.Image]:
        """Captures the primary monitor."""
        if not _PYAUTOGUI:
            logger.warning("PyAutoGUI not available for screen capture.")
            return None
        try:
            return pyautogui.screenshot()
        except Exception as e:
            logger.error(f"Error capturing full screen: {e}")
            return None

    def capture_region(self, x: int, y: int, width: int, height: int) -> Optional[Image.Image]:
        """Captures a region rectangle (x, y, width, height)."""
        if not _PYAUTOGUI:
            return None
        try:
            return pyautogui.screenshot(region=(int(x), int(y), int(width), int(height)))
        except Exception as e:
            logger.error(f"Error capturing screen region ({x}, {y}, {width}, {height}): {e}")
            return None

    def get_active_window_metadata(self) -> WindowMetadata:
        """Extracts title and application name of the active foreground window."""
        meta = WindowMetadata()
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if hwnd:
                # 1. Window Title
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    meta.window_title = buff.value

                # 2. Window Rect
                rect = ctypes.wintypes.RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    meta.bounds = {
                        "x": rect.left,
                        "y": rect.top,
                        "width": max(0, rect.right - rect.left),
                        "height": max(0, rect.bottom - rect.top)
                    }

                # 3. Process ID and App Name via psutil
                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                meta.process_id = pid.value
                if meta.process_id:
                    import psutil
                    proc = psutil.Process(meta.process_id)
                    meta.app_name = proc.name()
        except Exception as e:
            logger.debug(f"Could not retrieve Win32 active window details (non-fatal): {e}")

        if not meta.app_name:
            # Fallback heuristic from window title
            title_lower = meta.window_title.lower()
            if "visual studio code" in title_lower or "code" in title_lower:
                meta.app_name = "Code.exe"
            elif "chrome" in title_lower:
                meta.app_name = "chrome.exe"
            elif "notepad" in title_lower:
                meta.app_name = "notepad.exe"
            elif "terminal" in title_lower or "powershell" in title_lower:
                meta.app_name = "WindowsTerminal.exe"
            else:
                meta.app_name = "Desktop"

        return meta

    def capture_active_window(self) -> Tuple[Optional[Image.Image], WindowMetadata]:
        """Captures only the bounding region of the active foreground window."""
        meta = self.get_active_window_metadata()
        b = meta.bounds
        if b.get("width", 0) > 10 and b.get("height", 0) > 10:
            img = self.capture_region(b["x"], b["y"], b["width"], b["height"])
            if img:
                return img, meta

        # Fallback to full screen if bounds are invalid
        img = self.capture_screen()
        return img, meta

    def list_displays(self) -> List[Dict[str, Any]]:
        """Enumerates connected monitors."""
        try:
            # PyAutoGUI provides size of primary display
            width, height = pyautogui.size()
            return [{"index": 0, "name": "Primary Display", "width": width, "height": height, "primary": True}]
        except Exception:
            return [{"index": 0, "name": "Default Display", "width": 1920, "height": 1080, "primary": True}]

    def save_temporary_screenshot(self, image: Image.Image, prefix: str = "screen") -> Optional[str]:
        """Saves a temporary screenshot on disk honoring the retention policy."""
        if self.storage_policy == StoragePolicy.DO_NOT_STORE:
            return None

        filename = f"{prefix}_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
        path = os.path.join(self.temp_storage_dir, filename)
        try:
            image.save(path, format="PNG")
            return path
        except Exception as e:
            logger.error(f"Failed to save temporary screenshot: {e}")
            return None

    def cleanup_temporary_screenshots(self, max_age_seconds: Optional[int] = None) -> int:
        """Removes expired temporary screenshots."""
        max_age = max_age_seconds or self.max_temp_age_seconds
        now = time.time()
        removed = 0
        if not os.path.isdir(self.temp_storage_dir):
            return 0

        for f in os.listdir(self.temp_storage_dir):
            fpath = os.path.join(self.temp_storage_dir, f)
            if os.path.isfile(fpath) and f.endswith(".png"):
                try:
                    mtime = os.path.getmtime(fpath)
                    if (now - mtime) > max_age:
                        os.remove(fpath)
                        removed += 1
                except Exception as e:
                    logger.debug(f"Failed removing temp screenshot {fpath}: {e}")
        return removed

    def health_check(self) -> Dict[str, Any]:
        return {
            "available": self.is_available(),
            "provider": "DefaultScreenCaptureProvider",
            "displays": len(self.list_displays()),
            "temp_storage_dir": self.temp_storage_dir,
            "storage_policy": self.storage_policy.value,
        }
