import os
import sys
import tempfile
import unittest
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

from backend.automation.desktop_models import (
    DesktopAction, DesktopActionResult, ActionType,
    WindowActionType, RiskLevel, ActionStatus
)
from backend.automation.desktop_controller import DesktopController
from backend.automation.windows_controller import WindowsDesktopController
from backend.automation.unsupported_controller import UnsupportedDesktopController
from backend.automation.action_queue import ActionQueueManager
from backend.automation.security_proxy import SecurityProxy, PermissionLevel
from backend.skills.desktop_skill import DesktopSkill
from backend.router.intent_router import IntentRouter
from backend.core.models import UserInput, InputChannel, IntentType
from backend.orchestrator.orchestrator import JarvisOrchestrator
from backend.skills.registry import SkillRegistry


class TestDesktopAutomation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_path = self.temp_dir.name
        self.security = SecurityProxy({"security": {"enforce_permissions": True}})
        self.controller = WindowsDesktopController(app_aliases={
            "custom_editor": "notepad.exe",
            "browser": "chrome"
        })
        self.queue_mgr = ActionQueueManager(controller=self.controller, security_proxy=self.security)
        self.skill = DesktopSkill(controller=self.controller, security_proxy=self.security)

    def tearDown(self):
        self.temp_dir.cleanup()

    # 1. Open application (with alias resolution)
    @patch('subprocess.Popen')
    def test_01_open_application_alias_resolves(self, mock_popen):
        action = DesktopAction(action_type=ActionType.OPEN_APPLICATION, target="browser")
        res = self.queue_mgr.execute_single(action)
        self.assertTrue(res.success)
        self.assertIn("chrome", res.data.get("resolved_executable", ""))
        self.assertEqual(res.status, ActionStatus.VERIFIED)

    # 2. Application not found
    def test_02_application_not_found(self):
        action = DesktopAction(action_type=ActionType.OPEN_APPLICATION, target="non_existent_fake_app_xyz")
        res = self.queue_mgr.execute_single(action)
        self.assertFalse(res.success)
        self.assertEqual(res.status, ActionStatus.FAILED)
        self.assertIn("Application not found", res.message)

    # 3. Open file
    @patch('os.startfile', create=True)
    def test_03_open_file(self, mock_startfile):
        test_file = os.path.join(self.test_path, "sample.txt")
        with open(test_file, "w") as f:
            f.write("test content")

        action = DesktopAction(action_type=ActionType.OPEN_FILE, target=test_file)
        res = self.queue_mgr.execute_single(action)
        self.assertTrue(res.success)
        mock_startfile.assert_called_once_with(os.path.abspath(test_file))

    # 4. Open folder
    @patch('subprocess.Popen')
    def test_04_open_folder(self, mock_popen):
        action = DesktopAction(action_type=ActionType.OPEN_FOLDER, target=self.test_path)
        res = self.queue_mgr.execute_single(action)
        self.assertTrue(res.success)
        mock_popen.assert_called_once()

    # 5. Create folder and verify existence
    def test_05_create_folder_verified(self):
        folder_to_create = os.path.join(self.test_path, "JARVIS_TEST")
        action = DesktopAction(action_type=ActionType.CREATE_FOLDER, target=folder_to_create)
        res = self.queue_mgr.execute_single(action)
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertTrue(os.path.isdir(folder_to_create))

    # 6. Rename file and verify change
    def test_06_rename_file_verified(self):
        src = os.path.join(self.test_path, "old_name.txt")
        dst = os.path.join(self.test_path, "final_report.txt")
        with open(src, "w") as f:
            f.write("data")

        action = DesktopAction(
            action_type=ActionType.RENAME_FILE,
            target=src,
            parameters={"destination": dst}
        )
        res = self.queue_mgr.execute_single(action)
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertTrue(os.path.exists(dst))
        self.assertFalse(os.path.exists(src))

    # 7. Move file and verify destination
    def test_07_move_file_verified(self):
        src = os.path.join(self.test_path, "move_me.txt")
        subfolder = os.path.join(self.test_path, "subfolder")
        dst = os.path.join(subfolder, "move_me.txt")
        with open(src, "w") as f:
            f.write("content")

        action = DesktopAction(
            action_type=ActionType.MOVE_FILE,
            target=src,
            parameters={"destination": subfolder}
        )
        res = self.queue_mgr.execute_single(action)
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertTrue(os.path.exists(dst))
        self.assertFalse(os.path.exists(src))

    # 8. Delete file requiring confirmation (Approved)
    def test_08_delete_file_requiring_confirmation_approved(self):
        file_to_delete = os.path.join(self.test_path, "delete_me.txt")
        with open(file_to_delete, "w") as f:
            f.write("farewell")

        self.security.confirmation_callback = lambda action, details: True
        action = DesktopAction(action_type=ActionType.DELETE_FILE, target=file_to_delete)
        self.assertTrue(action.requires_confirmation)
        self.assertEqual(action.risk_level, RiskLevel.HIGH)

        res = self.queue_mgr.execute_single(action)
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertFalse(os.path.exists(file_to_delete))

    # 9. Permission denied (Confirmation Rejected)
    def test_09_permission_denied_aborts_deletion(self):
        file_protected = os.path.join(self.test_path, "protected.txt")
        with open(file_protected, "w") as f:
            f.write("keep me")

        self.security.confirmation_callback = lambda action, details: False
        action = DesktopAction(action_type=ActionType.DELETE_FILE, target=file_protected)

        res = self.queue_mgr.execute_single(action)
        self.assertFalse(res.success)
        self.assertEqual(res.status, ActionStatus.DENIED)
        self.assertTrue(os.path.exists(file_protected))

    # 10. Get system information
    def test_10_get_system_info(self):
        res = self.controller.get_system_info()
        self.assertTrue(res.success)
        self.assertEqual(res.risk_level, RiskLevel.LOW)
        self.assertIn("os", res.data)
        self.assertIn("cpu_percent", res.data)
        self.assertIn("ram_used_percent", res.data)

    # 11. Multi-step action workflow
    def test_11_multi_step_workflow(self):
        f1 = os.path.join(self.test_path, "step1_folder")
        f2 = os.path.join(f1, "step2_file.txt")

        actions = [
            DesktopAction(action_type=ActionType.CREATE_FOLDER, target=f1),
            DesktopAction(action_type=ActionType.CREATE_FILE, target=f2, parameters={"content": "workflow"}),
            DesktopAction(action_type=ActionType.LIST_DIRECTORY, target=f1),
        ]

        results = self.queue_mgr.execute_plan(actions)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))
        self.assertTrue(os.path.isfile(f2))

    # 12. Action cancellation mid-flow
    def test_12_action_cancellation_mid_flow(self):
        f1 = os.path.join(self.test_path, "cancel_test_1")
        f2 = os.path.join(self.test_path, "cancel_test_2")

        # Set confirmation callback to deny second action
        def confirm_gate(action_name, details):
            if "cancel_test_2" in details:
                return False
            return True

        self.security.confirmation_callback = confirm_gate

        actions = [
            DesktopAction(action_type=ActionType.CREATE_FOLDER, target=f1),
            DesktopAction(action_type=ActionType.DELETE_FILE, target=f2),
            DesktopAction(action_type=ActionType.CREATE_FOLDER, target=os.path.join(self.test_path, "should_not_run"))
        ]

        results = self.queue_mgr.execute_plan(actions)
        # Should execute first, fail second on confirmation, and stop before third
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].success)
        self.assertFalse(results[1].success)
        self.assertEqual(results[1].status, ActionStatus.DENIED)
        self.assertFalse(os.path.exists(os.path.join(self.test_path, "should_not_run")))

    # 13. Emergency stop halts queue
    def test_13_emergency_stop_halts_active_queue(self):
        f1 = os.path.join(self.test_path, "stop_folder_1")
        f2 = os.path.join(self.test_path, "stop_folder_2")

        # Trigger emergency stop before dispatching
        self.queue_mgr.trigger_emergency_stop()

        actions = [
            DesktopAction(action_type=ActionType.CREATE_FOLDER, target=f1),
            DesktopAction(action_type=ActionType.CREATE_FOLDER, target=f2)
        ]

        results = self.queue_mgr.execute_plan(actions)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)
        self.assertEqual(results[0].status, ActionStatus.CANCELLED)
        self.assertFalse(os.path.exists(f1))
        self.assertFalse(os.path.exists(f2))

    # 14. Unsupported platform capability reporting
    def test_14_unsupported_platform_reporting(self):
        unsupported = UnsupportedDesktopController(platform_name="Solaris")
        self.assertFalse(unsupported.get_capabilities()["open_application"])
        res = unsupported.open_application("browser")
        self.assertFalse(res.success)
        self.assertIn("not supported on platform 'Solaris'", res.message)

    # 15. Ambiguous application / project clarification
    def test_15_ambiguous_project_routing(self):
        router = IntentRouter()
        uinput = UserInput(content="Open the project")
        intent = router.route(uinput)
        self.assertEqual(intent.intent_type, IntentType.UNKNOWN)
        self.assertTrue(intent.parameters.get("is_ambiguous"))
        self.assertIn("Which project do you mean", intent.parameters.get("clarification_prompt", ""))

    # 16. Action verification failure stops pipeline
    def test_16_verification_failure_stops_pipeline(self):
        # We mock verify_action to return False
        mock_ctrl = MagicMock(spec=DesktopController)
        mock_ctrl.create_folder.return_value = DesktopActionResult(
            success=True, action_id="test", action_type=ActionType.CREATE_FOLDER, message="Folder created"
        )
        mock_ctrl.verify_action.return_value = False

        qm = ActionQueueManager(controller=mock_ctrl, security_proxy=self.security)
        actions = [
            DesktopAction(action_type=ActionType.CREATE_FOLDER, target="bogus_dir"),
            DesktopAction(action_type=ActionType.CREATE_FOLDER, target="subsequent_dir")
        ]
        results = qm.execute_plan(actions)
        self.assertEqual(len(results), 1)
        self.assertFalse(results[0].success)
        self.assertEqual(results[0].status, ActionStatus.FAILED)
        self.assertIn("post-verification failed", results[0].message)

    # 17. Offline desktop command (deterministic execution without cloud AI)
    def test_17_offline_deterministic_desktop_execution(self):
        router = IntentRouter()
        # Voice or text input directly parsed into deterministic intent
        uinput = UserInput(content="Create a folder called Offline_Workspace", channel=InputChannel.VOICE)
        intent = router.route(uinput)
        self.assertEqual(intent.skill_name, "desktop")
        self.assertEqual(intent.action, "create_folder")
        target_name = intent.parameters.get("folder_path")
        self.assertEqual(target_name, "Offline_Workspace")

        # Execute deterministically offline via skill
        skill_res = self.skill.execute(intent)
        self.assertTrue(skill_res.success)
        self.assertTrue(os.path.isdir("Offline_Workspace"))
        # Clean up created folder
        if os.path.exists("Offline_Workspace"):
            os.rmdir("Offline_Workspace")


if __name__ == "__main__":
    unittest.main()
