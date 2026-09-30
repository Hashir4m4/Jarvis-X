import unittest
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.models import UserInput, IntentType, InputChannel
from backend.router.intent_router import IntentRouter
from backend.skills.registry import SkillRegistry


class TestIntentRouter(unittest.TestCase):
    def setUp(self):
        self.registry = SkillRegistry()
        self.router = IntentRouter(skill_registry=self.registry)

    def test_route_system_info(self):
        user_input = UserInput(content="What is my system info?", channel=InputChannel.TEXT)
        intent = self.router.route(user_input)
        self.assertEqual(intent.intent_type, IntentType.SYSTEM_CONTROL)
        self.assertEqual(intent.skill_name, "system")
        self.assertEqual(intent.action, "get_system_info")

    def test_route_set_volume(self):
        user_input = UserInput(content="Set volume to 75", channel=InputChannel.VOICE)
        intent = self.router.route(user_input)
        self.assertEqual(intent.intent_type, IntentType.SYSTEM_CONTROL)
        self.assertEqual(intent.skill_name, "system")
        self.assertEqual(intent.action, "set_volume")
        self.assertEqual(intent.parameters.get("level"), 75)

    def test_route_mute_volume(self):
        user_input = UserInput(content="Mute audio please", channel=InputChannel.TEXT)
        intent = self.router.route(user_input)
        self.assertEqual(intent.intent_type, IntentType.SYSTEM_CONTROL)
        self.assertEqual(intent.action, "mute_volume")

    def test_route_get_brightness(self):
        user_input = UserInput(content="Check brightness", channel=InputChannel.TEXT)
        intent = self.router.route(user_input)
        self.assertEqual(intent.intent_type, IntentType.SYSTEM_CONTROL)
        self.assertEqual(intent.action, "get_brightness")

    def test_route_battery(self):
        user_input = UserInput(content="Check battery percentage", channel=InputChannel.UI)
        intent = self.router.route(user_input)
        self.assertEqual(intent.intent_type, IntentType.SYSTEM_CONTROL)
        self.assertEqual(intent.action, "get_battery")

    def test_route_conversation_fallback(self):
        user_input = UserInput(content="Explain quantum computing in simple terms", channel=InputChannel.TEXT)
        intent = self.router.route(user_input)
        self.assertEqual(intent.intent_type, IntentType.CONVERSATION)
        self.assertEqual(intent.skill_name, "conversation")
        self.assertEqual(intent.action, "chat")

    def test_explicit_override_metadata(self):
        user_input = UserInput(
            content="Random text",
            metadata={"explicit_intent": {"type": "system_control", "skill_name": "system", "action": "get_wifi_status"}}
        )
        intent = self.router.route(user_input)
        self.assertEqual(intent.action, "get_wifi_status")


if __name__ == "__main__":
    unittest.main()
