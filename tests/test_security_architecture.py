import unittest
import os
import sys
import tempfile
import shutil
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.automation.security_proxy import SecurityProxy, PermissionLevel
from backend.automation.terminal_executor import TerminalExecutor


class TestSecurityArchitecture(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config = {"security": {"log_dir": self.test_dir}}
        self.security = SecurityProxy(self.config)
        # Override paths to test dir
        self.security.audit_log_path = os.path.join(self.test_dir, "automation_audit.log")
        self.security.jsonl_audit_path = os.path.join(self.test_dir, "security_audit.jsonl")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_permission_level_classification(self):
        """Verify actions are classified into READ, WRITE, EXECUTE, DESTRUCTIVE."""
        self.assertEqual(self.security.get_permission_level("get_system_info"), PermissionLevel.SAFE)
        self.assertEqual(self.security.get_permission_level("search_vault"), PermissionLevel.SAFE)
        self.assertEqual(self.security.get_permission_level("create_daily_note"), PermissionLevel.CONFIRM)
        self.assertEqual(self.security.get_permission_level("set_volume"), PermissionLevel.CONFIRM)
        self.assertEqual(self.security.get_permission_level("coding.pipeline"), PermissionLevel.CONFIRM)
        self.assertEqual(self.security.get_permission_level("delete_file"), PermissionLevel.RESTRICTED)
        self.assertEqual(self.security.get_permission_level("kill_process"), PermissionLevel.RESTRICTED)

    def test_read_action_executes_freely(self):
        """Verify READ actions execute without confirmation prompt."""
        executed = False

        def sample_read():
            nonlocal executed
            executed = True
            return "telemetry_data"

        res = self.security.execute("get_telemetry", "querying cpu and ram", sample_read)
        self.assertTrue(executed)
        self.assertEqual(res, "telemetry_data")

    def test_destructive_action_approved_and_denied(self):
        """Verify DESTRUCTIVE actions trigger confirmation callback."""
        executed = False

        def sample_delete():
            nonlocal executed
            executed = True
            return "file_deleted"

        # 1. Denied action
        self.security.confirmation_callback = lambda action, details: False
        res_denied = self.security.execute("delete_file", "delete old_temp.log", sample_delete)
        self.assertFalse(executed)
        self.assertEqual(res_denied.get("status"), "denied")

        # 2. Approved action
        self.security.confirmation_callback = lambda action, details: True
        res_approved = self.security.execute("delete_file", "delete old_temp.log", sample_delete)
        self.assertTrue(executed)
        self.assertEqual(res_approved, "file_deleted")

    def test_blacklisted_dangerous_commands_blocked(self):
        """Verify blacklisted destructive commands are blocked unconditionally."""
        dangerous_cmds = [
            "format c:",
            "del /s /q c:\\",
            "rm -rf /",
            "shutdown /s",
            "reg delete HKLM\\Software",
            ":(){ :|:& };:"
        ]

        def dummy_exec():
            return "should_not_run"

        for cmd in dangerous_cmds:
            self.security.confirmation_callback = lambda a, d: True  # Even if approved!
            res = self.security.execute("run_cmd", cmd, dummy_exec)
            self.assertEqual(res.get("status"), "blocked")
            self.assertIn("blacklisted", res.get("message").lower())

    def test_secret_redaction(self):
        """Verify API keys, Bearer tokens, and secrets are redacted from logs and audits."""
        secret_text = "Connecting with API key sk-abcdef12345678901234567890 and Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 and password=SuperSecretPass123"
        redacted = SecurityProxy.redact_secrets(secret_text)

        self.assertNotIn("sk-abcdef12345678901234567890", redacted)
        self.assertIn("[REDACTED_API_KEY]", redacted)
        self.assertNotIn("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", redacted)
        self.assertIn("[REDACTED_TOKEN]", redacted)
        self.assertNotIn("SuperSecretPass123", redacted)
        self.assertIn("[REDACTED_PASSWORD]", redacted)

    def test_structured_jsonl_audit_trail(self):
        """Verify structured JSONL security audit log entries are generated."""
        def dummy_action():
            return "done"

        self.security.execute("screenshot", "capturing primary monitor with api_key=secret123456", dummy_action)

        self.assertTrue(os.path.isfile(self.security.jsonl_audit_path))
        with open(self.security.jsonl_audit_path, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]

        self.assertTrue(len(lines) >= 1)
        entry = lines[-1]
        self.assertEqual(entry["action"], "screenshot")
        self.assertEqual(entry["permission_level"], "READ")
        self.assertIn("[REDACTED_KEY]", entry["details"])
        self.assertEqual(entry["result"], "EXECUTED (safe)")
        self.assertIn("timestamp", entry)
        self.assertIn("execution_time_ms", entry)

    def test_terminal_executor_timeout_protection(self):
        """Verify terminal executor enforces timeout on long-running processes."""
        self.security.confirmation_callback = lambda action, details: True
        executor = TerminalExecutor(security_proxy=self.security)
        # Run command with 1s timeout
        res = executor.run_powershell("Start-Sleep -Seconds 5", timeout=1)
        self.assertEqual(res.get("status"), "error")
        self.assertIn("timed out", res.get("message").lower())


if __name__ == "__main__":
    unittest.main()
