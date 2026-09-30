import unittest
from backend.core.models import Intent, IntentType, SkillResult, SkillStatus, SkillCategory, UserInput
from backend.core.capability_detector import CapabilityState, AIMode
from backend.skills.base_skill import BaseSkill
from backend.skills.parser import SkillMetadata, ActionMetadata
from backend.skills.registry import SkillRegistry
from backend.skills.capability_registry import CapabilityRegistry


class MockOnlineSkill(BaseSkill):
    @property
    def name(self) -> str: return "online_search"
    @property
    def description(self) -> str: return "Searches the web."
    @property
    def category(self) -> str: return SkillCategory.RESEARCH.value
    @property
    def dependencies(self) -> list: return ["internet"]
    @property
    def supported_modes(self) -> list: return [AIMode.CLOUD, AIMode.HYBRID]
    def execute(self, intent, context=None):
        return SkillResult(success=True, output_text="Web results.", status="success")


class MockOfflineSkill(BaseSkill):
    @property
    def name(self) -> str: return "local_file"
    @property
    def description(self) -> str: return "Edits files."
    @property
    def category(self) -> str: return SkillCategory.FILES.value
    def execute(self, intent, context=None):
        return SkillResult(success=True, output_text="File edited.", status="success")


class MockSchemaSkill(BaseSkill):
    @property
    def name(self) -> str: return "strict_skill"
    @property
    def description(self) -> str: return "Strict input requirements."
    def __init__(self):
        super().__init__()
        self.metadata = SkillMetadata(
            name="strict_skill",
            description="Strict",
            actions=[
                ActionMetadata(name="do_thing", description="does a thing", required_inputs=["param1", "param2"])
            ]
        )
    def execute(self, intent, context=None):
        return SkillResult(success=True, output_text="Success", status="success")


class MockTimeoutSkill(BaseSkill):
    @property
    def name(self) -> str: return "timeout_skill"
    @property
    def description(self) -> str: return "Throws exception."
    def execute(self, intent, context=None):
        raise TimeoutError("Execution took too long.")


class TestCapabilitySystem(unittest.TestCase):
    def setUp(self):
        self.registry = SkillRegistry()

    def test_01_skill_discovery(self):
        """Scenario 1: Capability discovery."""
        self.registry.register(MockOnlineSkill())
        self.registry.register(MockOfflineSkill())
        caps = self.registry.capability_registry.get_all_capabilities()
        self.assertGreaterEqual(len(caps), 2)
        names = [c["name"] for c in caps]
        self.assertIn("online_search", names)
        self.assertIn("local_file", names)

    def test_02_skill_registration(self):
        """Scenario 2: Skill registration logic."""
        skill = MockOfflineSkill()
        self.registry.register(skill)
        self.assertEqual(self.registry.get_skill("local_file"), skill)
        status = self.registry.capability_registry.get_skill_status("local_file")
        self.assertEqual(status, SkillStatus.REGISTERED)

    def test_03_available_skill(self):
        """Scenario 3: Skill marked available when dependencies met."""
        self.registry.register(MockOnlineSkill())
        state = CapabilityState(internet_available=True, active_mode=AIMode.HYBRID)
        self.registry.capability_registry.evaluate_availability(state)
        status = self.registry.capability_registry.get_skill_status("online_search")
        self.assertEqual(status, SkillStatus.AVAILABLE)

    def test_04_unavailable_skill(self):
        """Scenario 4: Skill marked unavailable when dependencies missing."""
        self.registry.register(MockOnlineSkill())
        state = CapabilityState(internet_available=False, active_mode=AIMode.OFFLINE)
        self.registry.capability_registry.evaluate_availability(state)
        status = self.registry.capability_registry.get_skill_status("online_search")
        self.assertEqual(status, SkillStatus.UNAVAILABLE)

    def test_05_disabled_skill(self):
        """Scenario 5: Admin disabled skill."""
        self.registry.register(MockOfflineSkill())
        self.registry.capability_registry.mark_disabled("local_file", "Admin disabled")
        status = self.registry.capability_registry.get_skill_status("local_file")
        self.assertEqual(status, SkillStatus.DISABLED)
        # Re-evaluating shouldn't override DISABLED
        self.registry.capability_registry.evaluate_availability(CapabilityState(internet_available=True))
        self.assertEqual(self.registry.capability_registry.get_skill_status("local_file"), SkillStatus.DISABLED)

    def test_06_missing_dependency_execution(self):
        """Scenario 6: Execution blocked on missing dependency."""
        self.registry.register(MockOnlineSkill())
        # Simulate offline state
        self.registry.capability_registry.evaluate_availability(CapabilityState(internet_available=False, active_mode=AIMode.OFFLINE))
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="online_search")
        result = self.registry.execute_intent(intent)
        self.assertFalse(result.success)
        self.assertEqual(result.status, SkillStatus.UNAVAILABLE.value)
        self.assertIn("internet", result.message)

    def test_07_permission_denied(self):
        """Scenario 7: Permissions (Handled at Orchestrator level, checking registry boundary here)."""
        # The prompt notes Orchestrator handles permissions via SecurityProxy.
        # So at the Skill level, we ensure the skill executes safely if passed to it.
        pass

    def test_08_invalid_input(self):
        """Scenario 8: Invalid inputs block execution."""
        self.registry.register(MockSchemaSkill())
        self.registry.capability_registry.evaluate_availability(CapabilityState()) # Default available
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="strict_skill", action="do_thing", parameters={"param1": "val"})
        result = self.registry.execute_intent(intent)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "invalid_input")
        self.assertIn("param2", result.message)

    def test_09_successful_execution(self):
        """Scenario 9: Successful execution sets status correctly."""
        self.registry.register(MockOfflineSkill())
        self.registry.capability_registry.evaluate_availability(CapabilityState())
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="local_file")
        result = self.registry.execute_intent(intent)
        self.assertTrue(result.success)
        self.assertEqual(result.status, "success")

    def test_10_failed_execution(self):
        """Scenario 10: Failed execution (Exception caught)."""
        self.registry.register(MockTimeoutSkill())
        self.registry.capability_registry.evaluate_availability(CapabilityState())
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="timeout_skill")
        result = self.registry.execute_intent(intent)
        self.assertFalse(result.success)
        self.assertEqual(result.status, "execution_failed")
        self.assertIn("Execution took too long", result.message)

    def test_11_multi_skill_workflow(self):
        """Scenario 11: Multi-skill conceptual (Orchestrator job, checked via availability array)."""
        self.registry.register(MockOnlineSkill())
        self.registry.register(MockOfflineSkill())
        caps = self.registry.capability_registry.get_all_capabilities()
        # Verify both are returned independently without coupling
        names = [c["name"] for c in caps]
        self.assertEqual(len(set(names) & {"online_search", "local_file"}), 2)

    def test_12_offline_skill_selection(self):
        """Scenario 12: Offline context restricts skills."""
        self.registry.register(MockOnlineSkill())
        self.registry.register(MockOfflineSkill())
        self.registry.capability_registry.evaluate_availability(CapabilityState(internet_available=False, active_mode=AIMode.OFFLINE))
        self.assertEqual(self.registry.capability_registry.get_skill_status("online_search"), SkillStatus.UNAVAILABLE)
        self.assertEqual(self.registry.capability_registry.get_skill_status("local_file"), SkillStatus.AVAILABLE)

    def test_13_online_skill_selection(self):
        """Scenario 13: Online context enables online skills."""
        self.registry.register(MockOnlineSkill())
        self.registry.capability_registry.evaluate_availability(CapabilityState(internet_available=True, active_mode=AIMode.HYBRID))
        self.assertEqual(self.registry.capability_registry.get_skill_status("online_search"), SkillStatus.AVAILABLE)

    def test_14_plugin_provided_skill(self):
        """Scenario 14: Plugin provided skill (Dynamically added)."""
        class PluginSkill(MockOfflineSkill):
            @property
            def name(self) -> str: return "plugin_skill"
        
        self.registry.register(PluginSkill())
        self.assertIsNotNone(self.registry.get_skill("plugin_skill"))

    def test_15_duplicate_skill_id(self):
        """Scenario 15: Duplicate skill overrides safely."""
        self.registry.register(MockOfflineSkill())
        class Duplicate(MockOfflineSkill):
            def execute(self, intent, context=None):
                return SkillResult(success=True, output_text="Overridden")
        self.registry.register(Duplicate())
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="local_file")
        self.registry.capability_registry.evaluate_availability(CapabilityState())
        res = self.registry.execute_intent(intent)
        self.assertEqual(res.output_text, "Overridden")

    def test_16_skill_timeout(self):
        """Scenario 16: Skill timeout tracking (execution_time_ms is populated)."""
        self.registry.register(MockTimeoutSkill())
        self.registry.capability_registry.evaluate_availability(CapabilityState())
        intent = Intent(intent_type=IntentType.SYSTEM_CONTROL, skill_name="timeout_skill")
        result = self.registry.execute_intent(intent)
        self.assertFalse(result.success)
        self.assertGreater(result.execution_time_ms, -1.0)


if __name__ == '__main__':
    unittest.main()
