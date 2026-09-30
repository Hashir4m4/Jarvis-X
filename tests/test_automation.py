import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy dependencies
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['pyperclip'] = MagicMock()
sys.modules['pycaw'] = MagicMock()
sys.modules['pycaw.pycaw'] = MagicMock()
sys.modules['comtypes'] = MagicMock()
sys.modules['screen_brightness_control'] = MagicMock()
sys.modules['psutil'] = MagicMock()

from backend.automation.security_proxy import SecurityProxy, SAFE_ACTIONS, DANGEROUS_ACTIONS
from backend.automation.file_manager import FileManager
from backend.automation.terminal_executor import TerminalExecutor
from backend.brain import Brain


class TestSecurityProxy(unittest.TestCase):
    def setUp(self):
        self.proxy = SecurityProxy({})

    def test_safe_actions_pass(self):
        for action in ["screenshot", "get_clipboard", "get_volume", "list_files"]:
            self.assertTrue(self.proxy.is_safe(action), f"{action} should be safe")

    def test_dangerous_actions_flagged(self):
        for action in ["delete_file", "run_powershell", "kill_process"]:
            self.assertTrue(self.proxy.is_dangerous(action), f"{action} should be dangerous")

    def test_unknown_action_blocked(self):
        result = self.proxy.execute("hack_nasa", "lol", lambda: "pwned")
        self.assertEqual(result["status"], "blocked")

    def test_safe_action_executes(self):
        result = self.proxy.execute("screenshot", "take screenshot", lambda: {"status": "ok"})
        self.assertEqual(result["status"], "ok")

    @patch('builtins.input', return_value='n')
    def test_dangerous_action_denied(self, mock_input):
        result = self.proxy.execute("delete_file", "delete important.txt", lambda: {"status": "ok"})
        self.assertEqual(result["status"], "denied")

    @patch('builtins.input', return_value='y')
    def test_dangerous_action_approved(self, mock_input):
        result = self.proxy.execute("delete_file", "delete temp.txt", lambda: {"status": "ok"})
        self.assertEqual(result["status"], "ok")


class TestTerminalExecutor(unittest.TestCase):
    def setUp(self):
        self.executor = TerminalExecutor()

    def test_blacklisted_command_blocked(self):
        result = self.executor.run_powershell("format c:")
        self.assertEqual(result["status"], "blocked")

    def test_blacklisted_cmd_blocked(self):
        result = self.executor.run_cmd("del /s /q c:\\")
        self.assertEqual(result["status"], "blocked")


class TestBrainToolParsing(unittest.TestCase):
    def setUp(self):
        self.config = {
            "llm": {"provider": "test", "system_prompt": "Test"},
            "memory": {},
            "memory_advanced": {
                "sqlite_db_path": ":memory:",
                "chroma_db_path": "mock",
                "retrieval_top_k": 2
            }
        }
        self.brain = Brain(self.config, "test_session")

    def test_parse_tool_call(self):
        text = "Sure, I'll open Chrome for you.\n[TOOL] open_app | app_name=chrome"
        tool, kwargs = self.brain._parse_tool_call(text)
        self.assertEqual(tool, "open_app")
        self.assertEqual(kwargs["app_name"], "chrome")

    def test_no_tool_call(self):
        text = "The weather today is sunny."
        tool, kwargs = self.brain._parse_tool_call(text)
        self.assertIsNone(tool)

    def test_parse_multi_arg_tool(self):
        text = "[TOOL] search_files | directory=C:\\Users | pattern=*.py"
        tool, kwargs = self.brain._parse_tool_call(text)
        self.assertEqual(tool, "search_files")
        self.assertEqual(kwargs["directory"], "C:\\Users")
        self.assertEqual(kwargs["pattern"], "*.py")

    def tearDown(self):
        self.brain.memory.close()


if __name__ == "__main__":
    unittest.main()
