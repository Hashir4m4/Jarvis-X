import unittest
import sys
import os
import tempfile
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock external heavy packages
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['pycaw'] = MagicMock()
sys.modules['pycaw.pycaw'] = MagicMock()
sys.modules['comtypes'] = MagicMock()

from backend.core.models import UserInput, Intent, IntentType, InputChannel
from backend.skills.parser import SkillMetadataParser, SkillValidationError
from backend.skills.registry import SkillRegistry
from backend.skills.system_skill import SystemSkill
from backend.skills.metrics_skill import MetricsSkill
from backend.skills.plan_skill import PlanSkill
from backend.skills.vault_skill import VaultSkill
from backend.skills.inbox_skill import InboxSkill
from backend.skills.trends_skill import TrendsSkill
from backend.skills.conversation_skill import ConversationSkill
from backend.router.intent_router import IntentRouter


class TestSkillArchitecture(unittest.TestCase):
    def setUp(self):
        self.skills_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../skills"))
        self.registry = SkillRegistry(skills_dir=self.skills_dir)

    def test_automatic_skill_discovery(self):
        """Verify automatic discovery of all 6 SKILL.md definitions from disk."""
        discovered = self.registry.discover_skills(self.skills_dir)
        expected_skills = {"system", "metrics", "inbox", "trends", "plan", "vault"}
        
        for skill_name in expected_skills:
            self.assertIn(skill_name, discovered)
            meta = discovered[skill_name]
            self.assertEqual(meta.name, skill_name)
            self.assertTrue(len(meta.description) > 0)
            self.assertTrue(len(meta.actions) > 0)
            self.assertTrue(len(meta.permissions) > 0)

    def test_skill_parser_valid(self):
        sample_md = """---
name: custom_test
description: A test skill for validation.
version: 2.1.0
permissions:
  - test:read
actions:
  - name: do_something
    description: Executes test action
    required_inputs:
      - target
    output_format: json
---
# Custom Test
Documentation body here.
"""
        meta = SkillMetadataParser.parse_content(sample_md)
        self.assertEqual(meta.name, "custom_test")
        self.assertEqual(meta.version, "2.1.0")
        self.assertEqual(meta.permissions, ["test:read"])
        self.assertEqual(len(meta.actions), 1)
        self.assertEqual(meta.actions[0].name, "do_something")
        self.assertEqual(meta.actions[0].required_inputs, ["target"])
        self.assertEqual(meta.actions[0].output_format, "json")
        self.assertIn("Documentation body here", meta.doc_body)

    def test_skill_parser_malformed_errors(self):
        # Missing frontmatter
        with self.assertRaises(SkillValidationError):
            SkillMetadataParser.parse_content("No frontmatter here.")

        # Missing name
        with self.assertRaises(SkillValidationError):
            SkillMetadataParser.parse_content("---\ndescription: Missing name\n---\nBody")

    def test_system_skill_execution(self):
        mock_sys_ctrl = MagicMock()
        mock_sys_ctrl.get_system_info.return_value = {
            "os": "Windows", "cpu_percent": 12, "ram_used_percent": 40, "ram_total_gb": 16.0
        }
        mock_sys_ctrl.set_volume.return_value = {"status": "ok", "volume": 70}

        system_skill = SystemSkill(system_controller=mock_sys_ctrl)
        self.registry.register(system_skill)

        # 1. Execute get_system_info
        intent_info = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="system", action="get_system_info")
        res_info = self.registry.execute_intent(intent_info)
        self.assertTrue(res_info.success)
        self.assertIn("CPU usage is 12%", res_info.output_text)

        # 2. Execute set_volume with input
        intent_vol = Intent(
            intent_type=IntentType.SYSTEM_CONTROL,
            skill_name="system",
            action="set_volume",
            parameters={"level": 70}
        )
        res_vol = self.registry.execute_intent(intent_vol)
        self.assertTrue(res_vol.success)
        self.assertIn("Volume set to 70%", res_vol.output_text)

    def test_metrics_skill_execution(self):
        mock_sys_ctrl = MagicMock()
        mock_sys_ctrl.get_system_info.return_value = {
            "os": "Windows", "cpu_percent": 25, "ram_used_percent": 60, "ram_total_gb": 32.0
        }
        metrics_skill = MetricsSkill(system_controller=mock_sys_ctrl)
        self.registry.register(metrics_skill)

        # 1. Get telemetry
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="metrics", action="get_telemetry")
        res = self.registry.execute_intent(intent)
        self.assertTrue(res.success)
        self.assertIn("Telemetry Snapshot", res.output_text)
        self.assertEqual(res.data["cpu_percent"], 25)

        # 2. Get CPU load
        intent_cpu = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="metrics", action="get_cpu_load")
        res_cpu = self.registry.execute_intent(intent_cpu)
        self.assertTrue(res_cpu.success)
        self.assertIn("25%", res_cpu.output_text)

    def test_plan_and_vault_skills(self):
        # Test Plan Skill
        mock_planner = MagicMock()
        mock_planner.plan.return_value = [
            {"step_num": 1, "action": "CREATE", "file": "main.py", "description": "Create entry"}
        ]
        plan_skill = PlanSkill(planner=mock_planner)
        self.registry.register(plan_skill)

        intent_plan = Intent(
            intent_type=IntentType.PLUGIN,
            skill_name="plan",
            action="create_plan",
            parameters={"task": "Build CLI tool"}
        )
        res_plan = self.registry.execute_intent(intent_plan)
        self.assertTrue(res_plan.success)
        self.assertIn("Implementation Plan (1 steps)", res_plan.output_text)

        # Test Vault Skill
        mock_sqlite = MagicMock()
        mock_sqlite.get_user_pref.return_value = "Dark Mode"
        vault_skill = VaultSkill(sqlite_manager=mock_sqlite)
        self.registry.register(vault_skill)

        intent_vault = Intent(
            intent_type=IntentType.PLUGIN,
            skill_name="vault",
            action="get_secret",
            parameters={"key": "theme"}
        )
        res_vault = self.registry.execute_intent(intent_vault)
        self.assertTrue(res_vault.success)
        self.assertIn("Dark Mode", res_vault.output_text)

    def test_routing_to_skills(self):
        router = IntentRouter(skill_registry=self.registry)

        # 1. Route to metrics
        intent_m = router.route(UserInput(content="Show hardware telemetry", channel=InputChannel.TEXT))
        self.assertEqual(intent_m.skill_name, "metrics")
        self.assertEqual(intent_m.action, "get_telemetry")

        # 2. Route to system
        intent_s = router.route(UserInput(content="Set volume to 50", channel=InputChannel.VOICE))
        self.assertEqual(intent_s.skill_name, "system")
        self.assertEqual(intent_s.action, "set_volume")
        self.assertEqual(intent_s.parameters.get("level"), 50)

        # 3. Route to plan
        intent_p = router.route(UserInput(content="Create a plan to refactor database", channel=InputChannel.TEXT))
        self.assertEqual(intent_p.skill_name, "plan")
        self.assertEqual(intent_p.action, "create_plan")
        self.assertEqual(intent_p.parameters.get("task"), "refactor database")

        # 4. Route to vault
        intent_v = router.route(UserInput(content="get secret api_key", channel=InputChannel.TEXT))
        self.assertEqual(intent_v.skill_name, "vault")
        self.assertEqual(intent_v.action, "get_secret")
        self.assertEqual(intent_v.parameters.get("key"), "api_key")

        # 5. Route to conversation fallback
        intent_c = router.route(UserInput(content="What is the capital of France?", channel=InputChannel.TEXT))
        self.assertEqual(intent_c.skill_name, "conversation")
        self.assertEqual(intent_c.action, "chat")

    def test_invalid_skill_and_missing_inputs(self):
        # 1. Unregistered skill
        intent_bad = Intent(intent_type=IntentType.PLUGIN, skill_name="non_existent_skill", action="foo")
        res_bad = self.registry.execute_intent(intent_bad)
        self.assertFalse(res_bad.success)
        self.assertIn("not registered", res_bad.message)

        # 2. Missing required input validation (system.set_volume requires 'level')
        system_skill = SystemSkill(system_controller=MagicMock())
        self.registry.register(system_skill)

        intent_missing = Intent(
            intent_type=IntentType.SYSTEM_CONTROL,
            skill_name="system",
            action="set_volume",
            parameters={} # Missing 'level'
        )
        res_missing = self.registry.execute_intent(intent_missing)
        self.assertFalse(res_missing.success)
        self.assertIn("Missing required input", res_missing.message)

        # 3. Unknown action for registered skill
        intent_unknown_act = Intent(
            intent_type=IntentType.SYSTEM_CONTROL,
            skill_name="system",
            action="self_destruct",
            parameters={}
        )
        res_unknown_act = self.registry.execute_intent(intent_unknown_act)
        self.assertFalse(res_unknown_act.success)
        self.assertIn("Unknown system action", res_unknown_act.message)


if __name__ == "__main__":
    unittest.main()
