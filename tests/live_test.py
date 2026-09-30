import time
from backend.automation.windows_controller import WindowsDesktopController
from backend.automation.desktop_models import WindowActionType

print("--- SAFE LIVE TEST START ---")
controller = WindowsDesktopController()

print("1. Opening Notepad...")
res = controller.open_application("notepad")
print(res)
time.sleep(2)

print("2. Focus Notepad...")
res2 = controller.window_action(WindowActionType.FOCUS, target_title="notepad")
print(res2)
time.sleep(1)

print("3. Closing Notepad...")
res3 = controller.close_application("notepad")
print(res3)

print("4. Read System Info...")
res4 = controller.get_system_info()
print(f"System Info Success: {res4.success}")

print("--- SAFE LIVE TEST END ---")
