import unittest
import sys
import os
from unittest.mock import MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock chromadb/psutil/pycaw/comtypes/pyautogui for isolated testing
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['pycaw'] = MagicMock()
sys.modules['pycaw.pycaw'] = MagicMock()
sys.modules['comtypes'] = MagicMock()

from backend.core.models import Intent, IntentType
from backend.skills.registry import SkillRegistry
from backend.skills.system_skill import SystemSkill
from backend.skills.conversation_skill import ConversationSkill


class TestSkills(unittest.TestCase):
    def setUp(self):
        self.mock_sys_ctrl = MagicMock()
        self.system_skill = SystemSkill(system_controller=self.mock_sys_ctrl)
        
        self.mock_brain = MagicMock()
        self.conversation_skill = ConversationSkill(brain=self.mock_brain)
        
        self.registry = SkillRegistry()
        self.registry.register(self.system_skill)
        self.registry.register(self.conversation_skill)

    def test_registry_lookup(self):
        skill = self.registry.get_skill("system")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "system")
        
        skills_list = self.registry.list_skills()
        self.assertEqual(len(skills_list), 2)

    def test_find_skill_for_intent(self):
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="system", action="get_volume")
        skill = self.registry.find_skill_for_intent(intent)
        self.assertIs(skill, self.system_skill)

    def test_system_skill_get_system_info(self):
        self.mock_sys_ctrl.get_system_info.return_value = {
            "os": "Windows", "cpu_percent": 15, "ram_used_percent": 45, "ram_total_gb": 16.0
        }
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="system", action="get_system_info")
        result = self.system_skill.execute(intent)
        
        self.assertTrue(result.success)
        self.assertIn("CPU usage is 15%", result.output_text)
        self.assertIn("RAM usage is 45%", result.output_text)

    def test_system_skill_set_volume(self):
        self.mock_sys_ctrl.set_volume.return_value = {"status": "ok", "volume": 60}
        intent = Intent(
            intent_type=IntentType.SYSTEM_CONTROL,
            skill_name="system",
            action="set_volume",
            parameters={"level": 60}
        )
        result = self.system_skill.execute(intent)
        
        self.assertTrue(result.success)
        self.assertIn("Volume set to 60%", result.output_text)
        self.mock_sys_ctrl.set_volume.assert_called_once_with(60)

    def test_system_skill_get_battery(self):
        self.mock_sys_ctrl.get_battery.return_value = {"percent": 90, "plugged_in": True}
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="system", action="get_battery")
        result = self.system_skill.execute(intent)
        
        self.assertTrue(result.success)
        self.assertIn("Battery is at 90%", result.output_text)

    def test_conversation_skill_execution(self):
        self.mock_brain.chat_sync.return_value = "Hello! How can I assist you today?"
        intent = Intent(
            intent_type=IntentType.CONVERSATION,
            skill_name="conversation",
            action="chat",
            parameters={"query": "Hello Jarvis"}
        )
        result = self.conversation_skill.execute(intent)
        
        self.assertTrue(result.success)
        self.assertEqual(result.output_text, "Hello! How can I assist you today?")
        self.mock_brain.chat_sync.assert_called_once_with("Hello Jarvis")


if __name__ == "__main__":
    unittest.main()
