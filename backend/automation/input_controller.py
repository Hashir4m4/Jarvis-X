import logging

logger = logging.getLogger(__name__)

try:
    import pyautogui
    pyautogui.FAILSAFE = True  # Move mouse to top-left corner to abort
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import pyperclip
    _PYPERCLIP = True
except ImportError:
    _PYPERCLIP = False


class InputController:
    """Controls keyboard, mouse, and clipboard via pyautogui."""

    # ── Keyboard ──────────────────────────────────────────────────
    def type_text(self, text: str, interval: float = 0.02) -> dict:
        if not _PYAUTOGUI:
            return {"status": "error", "message": "pyautogui not installed"}
        try:
            pyautogui.typewrite(text, interval=interval)
            return {"status": "ok", "message": f"Typed: {text[:50]}..."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def press_key(self, key: str) -> dict:
        if not _PYAUTOGUI:
            return {"status": "error", "message": "pyautogui not installed"}
        try:
            pyautogui.press(key)
            return {"status": "ok", "message": f"Pressed: {key}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def hotkey(self, *keys) -> dict:
        if not _PYAUTOGUI:
            return {"status": "error", "message": "pyautogui not installed"}
        try:
            pyautogui.hotkey(*keys)
            return {"status": "ok", "message": f"Hotkey: {'+'.join(keys)}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Mouse ─────────────────────────────────────────────────────
    def mouse_move(self, x: int, y: int) -> dict:
        if not _PYAUTOGUI:
            return {"status": "error", "message": "pyautogui not installed"}
        try:
            pyautogui.moveTo(x, y, duration=0.3)
            return {"status": "ok", "message": f"Mouse moved to ({x}, {y})."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def mouse_click(self, x: int = None, y: int = None, button: str = "left") -> dict:
        if not _PYAUTOGUI:
            return {"status": "error", "message": "pyautogui not installed"}
        try:
            if x is not None and y is not None:
                pyautogui.click(x, y, button=button)
            else:
                pyautogui.click(button=button)
            return {"status": "ok", "message": f"Clicked ({x}, {y}) with {button} button."}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Screenshot ────────────────────────────────────────────────
    def screenshot(self, save_path: str = "logs/screenshot.png") -> dict:
        if not _PYAUTOGUI:
            return {"status": "error", "message": "pyautogui not installed"}
        try:
            import os
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            img = pyautogui.screenshot()
            img.save(save_path)
            return {"status": "ok", "message": f"Screenshot saved to {save_path}", "path": save_path}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ── Clipboard ─────────────────────────────────────────────────
    def get_clipboard(self) -> dict:
        if not _PYPERCLIP:
            return {"status": "error", "message": "pyperclip not installed"}
        try:
            content = pyperclip.paste()
            return {"status": "ok", "clipboard": content[:2000]}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def set_clipboard(self, text: str) -> dict:
        if not _PYPERCLIP:
            return {"status": "error", "message": "pyperclip not installed"}
        try:
            pyperclip.copy(text)
            return {"status": "ok", "message": "Clipboard updated."}
        except Exception as e:
            return {"status": "error", "message": str(e)}
