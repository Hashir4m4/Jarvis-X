import os

filepath = r'C:\Data\Projects\Jarvis X\backend\automation\windows_controller.py'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Patch open_file
old_open_file = '''    def open_file(self, file_path: str) -> DesktopActionResult:
        action_id = f"openfile_{os.path.basename(file_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(file_path)))
        if not os.path.exists(abs_path):'''
new_open_file = '''    def open_file(self, file_path: str) -> DesktopActionResult:
        action_id = f"openfile_{os.path.basename(file_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(file_path)))
        is_safe, msg = SecurityProxy.validate_safe_path(abs_path, for_destructive=False)
        if not is_safe:
            return DesktopActionResult(success=False, action_id=action_id, action_type=ActionType.OPEN_FILE, message=f"Action blocked by safety guard: {msg}", risk_level=RiskLevel.RESTRICTED, status=ActionStatus.FAILED)
        if not os.path.exists(abs_path):'''
content = content.replace(old_open_file, new_open_file)

# Patch open_folder
old_open_folder = '''    def open_folder(self, folder_path: str) -> DesktopActionResult:
        action_id = f"openfolder_{os.path.basename(folder_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(folder_path)))
        if not os.path.isdir(abs_path):'''
new_open_folder = '''    def open_folder(self, folder_path: str) -> DesktopActionResult:
        action_id = f"openfolder_{os.path.basename(folder_path)[:8]}"
        abs_path = os.path.abspath(os.path.expanduser(os.path.expandvars(folder_path)))
        is_safe, msg = SecurityProxy.validate_safe_path(abs_path, for_destructive=False)
        if not is_safe:
            return DesktopActionResult(success=False, action_id=action_id, action_type=ActionType.OPEN_FOLDER, message=f"Action blocked by safety guard: {msg}", risk_level=RiskLevel.RESTRICTED, status=ActionStatus.FAILED)
        if not os.path.isdir(abs_path):'''
content = content.replace(old_open_folder, new_open_folder)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("windows_controller.py patched successfully.")
