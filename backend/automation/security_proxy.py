import enum
import logging
import os
import re
import json
import time
import datetime
from typing import Dict, Any, List, Optional, Callable, Union

logger = logging.getLogger("JARVIS.Security")


class PermissionLevel(enum.Enum):
    SAFE = "SAFE"
    CONFIRM = "CONFIRM"
    RESTRICTED = "RESTRICTED"


# Secret redaction patterns
SECRET_PATTERNS = [
    (r"(sk-[a-zA-Z0-9_\-]{15,})", "[REDACTED_API_KEY]"),
    (r"(sk-ant-[a-zA-Z0-9_\-]{10,})", "[REDACTED_API_KEY]"),
    (r"(ant-api[a-zA-Z0-9_\-]{10,})", "[REDACTED_API_KEY]"),
    (r"(AIzaSy[a-zA-Z0-9_\-]{20,})", "[REDACTED_API_KEY]"),
    (r"(gsk_[a-zA-Z0-9_\-]{15,})", "[REDACTED_API_KEY]"),
    (r"(ghp_[a-zA-Z0-9]{36})", "[REDACTED_TOKEN]"),
    (r"(github_pat_[a-zA-Z0-9_]{30,})", "[REDACTED_TOKEN]"),
    (r"(xox[baprs]-[0-9a-zA-Z_\-]{10,})", "[REDACTED_TOKEN]"),
    (r"(AKIA[0-9A-Z]{16})", "[REDACTED_KEY]"),
    (r"(Bearer\s+[a-zA-Z0-9_\-\.]{15,})", "Bearer [REDACTED_TOKEN]"),
    (r"(password[\"':\s=]+)([^\s\"',&]+)", r"\1[REDACTED_PASSWORD]"),
    (r"(token[\"':\s=]+)([^\s\"',&]+)", r"\1[REDACTED_TOKEN]"),
    (r"(secret[\"':\s=]+)([^\s\"',&]+)", r"\1[REDACTED_SECRET]"),
    (r"(api[_-]?key[\"':\s=]+)([^\s\"',&]+)", r"\1[REDACTED_KEY]"),
    (r"(access[_-]?key[\"':\s=]+)([^\s\"',&]+)", r"\1[REDACTED_KEY]"),
    (r"(auth[_-]?token[\"':\s=]+)([^\s\"',&]+)", r"\1[REDACTED_TOKEN]"),
    (r"(-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----)", "[REDACTED_PRIVATE_KEY]"),
]

# Legacy & Desktop Action Sets
SAFE_ACTIONS = {
    "screenshot", "get_clipboard", "get_volume", "get_brightness",
    "get_battery", "list_processes", "get_system_info", "get_wifi_status",
    "open_app", "open_application", "minimize_window", "maximize_window", "type_text",
    "press_key", "mouse_move", "mouse_click", "list_files", "list_directory",
    "window_action", "gui_action", "browser_search", "browser_read", 
    "browser_scroll", "browser_open_url", "browser_find_text"
}

DANGEROUS_ACTIONS = {
    "delete_file", "delete_folder", "run_powershell", "run_cmd",
    "kill_process", "rename_file", "set_wifi", "set_bluetooth",
    "empty_recycle_bin", "shutdown", "restart", "close_app", "close_application",
    "organize_files", "organize_directory", "browser_financial", 
    "browser_delete_account", "browser_credential"
}

# Classification of actions into permission levels
ACTION_PERMISSIONS: Dict[str, PermissionLevel] = {
    # READ Actions (Telemetry, Sensors, Memory Query, Health)
    "screenshot": PermissionLevel.SAFE,
    "get_clipboard": PermissionLevel.SAFE,
    "get_volume": PermissionLevel.SAFE,
    "get_brightness": PermissionLevel.SAFE,
    "get_battery": PermissionLevel.SAFE,
    "list_processes": PermissionLevel.SAFE,
    "get_system_info": PermissionLevel.SAFE,
    "get_wifi_status": PermissionLevel.SAFE,
    "list_files": PermissionLevel.SAFE,
    "list_directory": PermissionLevel.SAFE,
    "read_file": PermissionLevel.SAFE,
    "search_files": PermissionLevel.SAFE,
    "get_time": PermissionLevel.SAFE,
    "search_vault": PermissionLevel.SAFE,
    "read_memory": PermissionLevel.SAFE,
    "get_telemetry": PermissionLevel.SAFE,
    "get_cpu_load": PermissionLevel.SAFE,
    "get_memory_stats": PermissionLevel.SAFE,
    "get_brief": PermissionLevel.SAFE,

    # WRITE Actions (Notes, Plans, System Settings, Folder/File creation)
    "set_volume": PermissionLevel.CONFIRM,
    "set_brightness": PermissionLevel.CONFIRM,
    "mute_volume": PermissionLevel.CONFIRM,
    "unmute_volume": PermissionLevel.CONFIRM,
    "write_file": PermissionLevel.CONFIRM,
    "create_file": PermissionLevel.CONFIRM,
    "create_folder": PermissionLevel.CONFIRM,
    "move_file": PermissionLevel.CONFIRM,
    "copy_file": PermissionLevel.CONFIRM,
    "create_daily_note": PermissionLevel.CONFIRM,
    "create_report": PermissionLevel.CONFIRM,
    "raw_capture": PermissionLevel.CONFIRM,
    "create_wiki_note": PermissionLevel.CONFIRM,
    "set_secret": PermissionLevel.CONFIRM,
    "plan_today": PermissionLevel.CONFIRM,
    "close_the_day": PermissionLevel.CONFIRM,

    # Standard Skills & Conversation
    "chat": PermissionLevel.SAFE,
    "conversation": PermissionLevel.SAFE,
    "plan": PermissionLevel.CONFIRM,
    "metrics": PermissionLevel.SAFE,
    "brief": PermissionLevel.SAFE,
    "close_day": PermissionLevel.CONFIRM,
    "trends": PermissionLevel.SAFE,
    "inbox": PermissionLevel.SAFE,
    "system": PermissionLevel.SAFE,
    "vault": PermissionLevel.SAFE,
    "desktop": PermissionLevel.SAFE,
    "unknown": PermissionLevel.SAFE,

    # EXECUTE Actions (Agent pipelines, Scripts, Process Control)
    "open_app": PermissionLevel.CONFIRM,
    "open_application": PermissionLevel.CONFIRM,
    "open_file": PermissionLevel.CONFIRM,
    "open_folder": PermissionLevel.CONFIRM,
    "minimize_window": PermissionLevel.CONFIRM,
    "maximize_window": PermissionLevel.CONFIRM,
    "window_action": PermissionLevel.CONFIRM,
    "type_text": PermissionLevel.CONFIRM,
    "press_key": PermissionLevel.CONFIRM,
    "mouse_move": PermissionLevel.CONFIRM,
    "mouse_click": PermissionLevel.CONFIRM,
    "gui_action": PermissionLevel.CONFIRM,
    "run_powershell": PermissionLevel.CONFIRM,
    "run_cmd": PermissionLevel.CONFIRM,
    "coding.pipeline": PermissionLevel.CONFIRM,
    "agent.planner": PermissionLevel.CONFIRM,
    "agent.coder": PermissionLevel.CONFIRM,
    "agent.reviewer": PermissionLevel.CONFIRM,
    "agent.executor": PermissionLevel.CONFIRM,

    # DESTRUCTIVE Actions (Deletion, Process Termination, System Shutdown, Bulk changes)
    "delete_file": PermissionLevel.RESTRICTED,
    "delete_folder": PermissionLevel.RESTRICTED,
    "kill_process": PermissionLevel.RESTRICTED,
    "rename_file": PermissionLevel.RESTRICTED,
    "organize_files": PermissionLevel.RESTRICTED,
    "organize_directory": PermissionLevel.RESTRICTED,
    "set_wifi": PermissionLevel.RESTRICTED,
    "set_bluetooth": PermissionLevel.RESTRICTED,
    "empty_recycle_bin": PermissionLevel.RESTRICTED,
    "shutdown": PermissionLevel.RESTRICTED,
    "restart": PermissionLevel.RESTRICTED,
    "close_app": PermissionLevel.RESTRICTED,
    "close_application": PermissionLevel.RESTRICTED,
    
    # Terminal Classifications
    "terminal_read_only": PermissionLevel.SAFE,
    "terminal_safe_write": PermissionLevel.SAFE,
    "terminal_confirm": PermissionLevel.CONFIRM,
    "terminal_restricted": PermissionLevel.RESTRICTED,

    # Browser Classifications
    "browser_search": PermissionLevel.SAFE,
    "browser_read": PermissionLevel.SAFE,
    "browser_scroll": PermissionLevel.SAFE,
    "browser_open_url": PermissionLevel.SAFE,
    "browser_find_text": PermissionLevel.SAFE,
    "browser_submit_form": PermissionLevel.CONFIRM,
    "browser_send_message": PermissionLevel.CONFIRM,
    "browser_upload_file": PermissionLevel.CONFIRM,
    "browser_financial": PermissionLevel.RESTRICTED,
    "browser_delete_account": PermissionLevel.RESTRICTED,
    "browser_credential": PermissionLevel.RESTRICTED,
}

# Absolute blacklist patterns
BLACKLISTED_PATTERNS = [
    "format c:", "format d:", "del /s /q c:\\", "del /f /s /q c:\\",
    "rm -rf /", "rm -rf /*", "shutdown /s", "shutdown /r",
    "reg delete", "bcdedit", "diskpart", ":(){ :|:& };:"
]


class SecurityProxy:
    """
    Enterprise-Grade Security Proxy & Execution Gatekeeper.
    Enforces 4-tier permission matrix (READ, WRITE, EXECUTE, DESTRUCTIVE),
    dangerous command blacklists, regex secret redaction, and audit logging.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.confirmation_callback: Optional[Callable[[str, str], bool]] = None
        self.enforce_permissions: bool = self.config.get("security", {}).get("enforce_permissions", True)
        
        # Log paths
        base_log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../logs"))
        os.makedirs(base_log_dir, exist_ok=True)
        self.audit_log_path = os.path.join(base_log_dir, "automation_audit.log")
        self.jsonl_audit_path = os.path.join(base_log_dir, "security_audit.jsonl")

    def get_permission_level(self, action_name: str) -> PermissionLevel:
        """Determines permission level of an action."""
        if not action_name:
            return PermissionLevel.SAFE
        if action_name in DANGEROUS_ACTIONS:
            return PermissionLevel.RESTRICTED
        if action_name.startswith("plugin."):
            return PermissionLevel.CONFIRM
        if action_name in SAFE_ACTIONS:
            return PermissionLevel.SAFE
        return ACTION_PERMISSIONS.get(action_name, PermissionLevel.SAFE)

    def is_safe(self, action_name: str) -> bool:
        """Checks if action is safe to run without confirmation."""
        return action_name in SAFE_ACTIONS or (action_name in ACTION_PERMISSIONS and ACTION_PERMISSIONS[action_name] == PermissionLevel.SAFE)

    def is_dangerous(self, action_name: str) -> bool:
        """Checks if action requires elevated user confirmation."""
        return action_name in DANGEROUS_ACTIONS or (action_name in ACTION_PERMISSIONS and ACTION_PERMISSIONS[action_name] in (PermissionLevel.RESTRICTED, PermissionLevel.CONFIRM))

    def is_known(self, action_name: str) -> bool:
        """Checks if action is known in permissions or action sets."""
        return (
            action_name in SAFE_ACTIONS
            or action_name in DANGEROUS_ACTIONS
            or action_name in ACTION_PERMISSIONS
            or action_name.startswith("plugin.")
        )

    def is_blacklisted(self, command_or_details: str) -> bool:
        """Checks if command contains dangerous or system-destroying sequences."""
        lower = str(command_or_details).lower()
        for pattern in BLACKLISTED_PATTERNS:
            if pattern in lower:
                logger.critical(f"[SECURITY] Blacklisted command detected: {command_or_details}")
                return True
        return False

    @staticmethod
    def validate_safe_path(file_or_dir_path: str, for_destructive: bool = False) -> tuple[bool, str]:
        """
        Validates file system paths to prevent path traversal, drive-root deletion,
        and destructive operations against critical operating system or credential stores.
        """
        if not file_or_dir_path or not str(file_or_dir_path).strip():
            return False, "Empty path provided."

        try:
            norm_path = os.path.abspath(os.path.expanduser(os.path.expandvars(str(file_or_dir_path))))
        except Exception as e:
            return False, f"Invalid path resolution: {e}"

        # Disallow root drive deletion or tampering
        root_drives = [f"{chr(d)}:\\" for d in range(ord('a'), ord('z') + 1)] + [
            f"{chr(d)}:" for d in range(ord('a'), ord('z') + 1)
        ] + ["/", "\\"]
        if norm_path.lower() in [d.lower() for d in root_drives]:
            return False, f"Targeting filesystem root drive '{norm_path}' is strictly prohibited."

        # Protected system directories
        protected_prefixes = [
            os.environ.get("SystemRoot", "C:\\Windows"),
            os.environ.get("ProgramFiles", "C:\\Program Files"),
            os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
            "/bin", "/sbin", "/etc", "/usr", "/boot", "/sys", "/dev"
        ]
        
        for prefix in protected_prefixes:
            if prefix and norm_path.lower().startswith(os.path.abspath(prefix).lower()):
                if for_destructive:
                    return False, f"Destructive operations against protected system path '{norm_path}' are blocked."

        # Protected credential folders
        user_home = os.path.expanduser("~")
        protected_credential_dirs = [
            os.path.join(user_home, ".ssh"),
            os.path.join(user_home, ".gnupg"),
            os.path.join(user_home, ".aws"),
            os.path.join(user_home, ".azure"),
            os.path.join(user_home, ".kube"),
        ]
        for cred_dir in protected_credential_dirs:
            if norm_path.lower().startswith(os.path.abspath(cred_dir).lower()):
                if for_destructive:
                    return False, f"Destructive operations against user credential directory '{norm_path}' are blocked."

        return True, "Path is valid."

    @staticmethod
    def redact_secrets(text: str) -> str:
        """Redacts sensitive credentials, tokens, and API keys from text."""
        if not isinstance(text, str):
            text = str(text)
        redacted = text
        for pattern, replacement in SECRET_PATTERNS:
            redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
        return redacted

    def request_confirmation(self, action_name: str, details: str) -> bool:
        """
        Prompts for confirmation before executing DESTRUCTIVE or elevated operations.
        Uses custom callback if registered, or terminal prompt fallback.
        """
        sanitized_details = self.redact_secrets(details)

        if self.confirmation_callback:
            try:
                allowed = bool(self.confirmation_callback(action_name, sanitized_details))
                self._audit(action_name, sanitized_details, "APPROVED" if allowed else "DENIED", PermissionLevel.RESTRICTED)
                return allowed
            except Exception as e:
                logger.error(f"Confirmation callback error: {e}")
                return False

        print(f"\n[!] SECURITY CONFIRMATION REQUIRED")
        print(f"   Action : {action_name}")
        print(f"   Details: {sanitized_details}")

        try:
            response = input("   Allow this action? [Y/N]: ").strip().lower()
            allowed = response in ("y", "yes")
            self._audit(action_name, sanitized_details, "APPROVED" if allowed else "DENIED", PermissionLevel.RESTRICTED)
            return allowed
        except (EOFError, KeyboardInterrupt):
            self._audit(action_name, sanitized_details, "DENIED (interrupted)", PermissionLevel.RESTRICTED)
            return False

    def execute(self, action_name: str, details: str, func: Callable, *args, **kwargs):
        """
        Central gate for executing any automation action or agent command.
        1. Checks blacklist.
        2. Blocks unknown actions.
        3. Validates permission level (READ, WRITE, EXECUTE, DESTRUCTIVE).
        4. Enforces confirmation for destructive actions.
        5. Logs structured audit record.
        """
        start_time = time.time()
        redacted_details = self.redact_secrets(details)
        perm_level = self.get_permission_level(action_name)

        # 1. Blacklist check
        if self.is_blacklisted(details):
            self._audit(action_name, redacted_details, "BLOCKED (blacklisted)", perm_level)
            return {"status": "blocked", "message": f"Action '{action_name}' contains blacklisted command."}

        # 2. Block unknown actions immediately
        if not self.is_known(action_name):
            self._audit(action_name, redacted_details, "BLOCKED (unknown)", PermissionLevel.RESTRICTED)
            logger.warning(f"Unknown action '{action_name}' blocked.")
            return {"status": "blocked", "message": f"Unknown action '{action_name}' is not permitted."}

        # 3. Known Safe actions (READ / safe WRITE)
        if self.is_safe(action_name):
            try:
                result = func(*args, **kwargs)
                elapsed = round((time.time() - start_time) * 1000, 2)
                self._audit(action_name, redacted_details, "EXECUTED (safe)", perm_level, elapsed_ms=elapsed)
                return result
            except Exception as e:
                self._audit(action_name, redacted_details, f"ERROR: {e}", perm_level)
                raise e

        # 4. Known Dangerous / Destructive actions (require confirmation)
        if self.is_dangerous(action_name):
            if self.request_confirmation(action_name, details):
                try:
                    result = func(*args, **kwargs)
                    elapsed = round((time.time() - start_time) * 1000, 2)
                    self._audit(action_name, redacted_details, "EXECUTED (confirmed)", perm_level, elapsed_ms=elapsed)
                    return result
                except Exception as e:
                    self._audit(action_name, redacted_details, f"ERROR: {e}", perm_level)
                    raise e
            else:
                logger.info(f"Action '{action_name}' was denied by user.")
                self._audit(action_name, redacted_details, "DENIED", perm_level)
                return {"status": "denied", "message": "Action was denied by the user."}

        # 5. Other Execute actions
        try:
            result = func(*args, **kwargs)
            elapsed = round((time.time() - start_time) * 1000, 2)
            self._audit(action_name, redacted_details, "EXECUTED", perm_level, elapsed_ms=elapsed)
            return result
        except Exception as e:
            self._audit(action_name, redacted_details, f"ERROR: {e}", perm_level)
            raise e

    def _audit(
        self,
        action: str,
        details: str,
        result: str,
        permission_level: PermissionLevel = PermissionLevel.SAFE,
        elapsed_ms: float = 0.0
    ):
        """Appends human-readable and structured JSONL audit entries with redacted secrets."""
        now = datetime.datetime.now()
        timestamp_iso = now.isoformat()
        redacted = self.redact_secrets(details)

        # 1. Plain text audit log (backward compatible)
        entry_text = f"[{timestamp_iso}] LEVEL={permission_level.value} | ACTION={action} | DETAILS={redacted} | RESULT={result}\n"
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                f.write(entry_text)
        except Exception as e:
            logger.error(f"Failed writing audit log: {e}")

        # 2. Structured JSONL audit log
        json_entry = {
            "timestamp": timestamp_iso,
            "action": action,
            "permission_level": permission_level.value,
            "details": redacted,
            "result": result,
            "execution_time_ms": elapsed_ms
        }
        try:
            with open(self.jsonl_audit_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(json_entry) + "\n")
        except Exception as e:
            logger.error(f"Failed writing JSONL security audit: {e}")
