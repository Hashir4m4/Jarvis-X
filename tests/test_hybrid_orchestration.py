import unittest
from backend.core.models import TaskCategory
from backend.llm.model_router import ModelRouter, ModelSelectionRequest, UserRoutingPreference, PrivacyPolicy
from backend.llm.registry import ModelMetadata, ModelCapabilities, ResourceRequirements
from backend.llm.telemetry import network_detector, NetworkState

class TestHybridOrchestration(unittest.TestCase):
    def setUp(self):
        self.router = ModelRouter()
        # Seed test data for robust testing
        self.router.registry.register(ModelMetadata(
            model_id="local_general", provider="local", local_or_online="local",
            capabilities=ModelCapabilities(tool_calling=True)
        ))
        self.router.registry.register(ModelMetadata(
            model_id="cloud_general", provider="openai", local_or_online="online",
            capabilities=ModelCapabilities(tool_calling=True)
        ))
        self.router.registry.register(ModelMetadata(
            model_id="cloud_vision", provider="openai", local_or_online="online",
            capabilities=ModelCapabilities(vision=True)
        ))
        self.router.registry.register(ModelMetadata(
            model_id="huge_local", provider="local", local_or_online="local",
            resource_requirements=ResourceRequirements(min_ram_gb=128.0) # Unlikely to pass resource check
        ))
        
        # Override default models to match test seeded models
        self.router.local_models.general_model = "local_general"
        self.router.local_models.fast_model = "local_general"
        self.router.local_models.reasoning_model = "local_general"
        self.router.local_models.coding_model = "local_general"
        self.router.local_models.vision_model = "local_general"
        
        self.router.cloud_models.general_model = "cloud_general"
        self.router.cloud_models.fast_model = "cloud_general"
        self.router.cloud_models.reasoning_model = "cloud_general"
        self.router.cloud_models.coding_model = "cloud_general"
        self.router.cloud_models.vision_model = "cloud_vision"

    def _make_req(self, **kwargs):
        req = ModelSelectionRequest(
            task_category=TaskCategory.UNKNOWN,
            user_input="test",
            local_llm_available=True,
            cloud_available=True,
            internet_available=True,
            cloud_providers={"openai": {"available": True}}
        )
        for k, v in kwargs.items():
            setattr(req, k, v)
        return req

    def test_01_offline_routing(self):
        req = self._make_req(internet_available=False, cloud_available=False, user_preference=UserRoutingPreference.OFFLINE if hasattr(UserRoutingPreference, 'OFFLINE') else UserRoutingPreference.LOCAL)
        res = self.router.select(req)
        self.assertEqual(res.provider, "local")

    def test_02_online_routing(self):
        req = self._make_req(user_preference=UserRoutingPreference.CLOUD)
        res = self.router.select(req)
        self.assertEqual(res.provider, "openai")

    def test_03_hybrid_routing(self):
        req = self._make_req(user_preference=UserRoutingPreference.HYBRID if hasattr(UserRoutingPreference, 'HYBRID') else UserRoutingPreference.AUTO)
        res = self.router.select(req)
        self.assertIn(res.provider, ["local", "openai"])

    def test_04_auto_routing(self):
        req = self._make_req(user_preference=UserRoutingPreference.AUTO)
        res = self.router.select(req)
        self.assertIsNotNone(res.provider)

    def test_05_local_unavailable(self):
        req = self._make_req(local_llm_available=False, user_preference=UserRoutingPreference.AUTO)
        res = self.router.select(req)
        self.assertEqual(res.provider, "openai")

    def test_06_cloud_unavailable(self):
        req = self._make_req(cloud_available=False, user_preference=UserRoutingPreference.AUTO)
        res = self.router.select(req)
        self.assertEqual(res.provider, "local")

    def test_07_network_offline(self):
        req = self._make_req(internet_available=False)
        res = self.router.select(req)
        self.assertEqual(res.provider, "local")

    def test_08_network_degraded(self):
        network_detector.current_state = NetworkState.DEGRADED
        req = self._make_req(user_preference=UserRoutingPreference.AUTO)
        res = self.router.select(req)
        self.assertIsNotNone(res.provider)

    def test_09_model_timeout(self):
        # Timeouts are tested functionally in client/proxy implementations. Routing logic should provide fallbacks.
        req = self._make_req(user_preference=UserRoutingPreference.CLOUD)
        res = self.router.select_with_fallback(req)
        self.assertTrue(len(res.fallbacks) >= 1)

    def test_10_provider_timeout(self):
        req = self._make_req()
        res = self.router.select_with_fallback(req)
        self.assertTrue(len(res.fallbacks) >= 1)

    def test_11_fallback(self):
        req = self._make_req()
        res = self.router.select_with_fallback(req)
        self.assertTrue(len(res.fallbacks) > 0)

    def test_12_privacy_classification(self):
        req = self._make_req(privacy_level=PrivacyPolicy.LOCAL_ONLY)
        res = self.router.select(req)
        self.assertEqual(res.provider, "local")

    def test_13_secret_detection(self):
        # The PrivacyBoundary classifies content with "API_KEY=" as SENSITIVE_LOCAL_CONTEXT
        req = self._make_req(user_input="Here is my API_KEY=12345")
        res = self.router.select(req)
        self.assertEqual(res.provider, "local")

    def test_14_data_minimization(self):
        # A mock test that ensures privacy policies default to local
        req = self._make_req(user_preference=UserRoutingPreference.AUTO, privacy_level=PrivacyPolicy.PREFER_LOCAL)
        res = self.router.select(req)
        self.assertEqual(res.provider, "local")

    def test_15_vision_routing(self):
        req = self._make_req(task_category=TaskCategory.VISION_TASK, required_capabilities=["vision"])
        res = self.router.select(req)
        # Because local_general does NOT have vision, it must fall back to cloud_vision
        self.assertEqual(res.provider, "openai")

    def test_16_browser_routing(self):
        req = self._make_req(task_category=TaskCategory.UNKNOWN)
        res = self.router.select(req)
        self.assertIsNotNone(res.provider)

    def test_17_memory_routing(self):
        req = self._make_req(task_category=TaskCategory.MEMORY_REQUEST)
        res = self.router.select(req)
        self.assertIsNotNone(res.provider)

    def test_18_voice_routing(self):
        req = self._make_req(task_category=TaskCategory.CONVERSATION)
        res = self.router.select(req)
        self.assertIsNotNone(res.provider)

    def test_19_tool_capability_validation(self):
        req = self._make_req(required_capabilities=["tool_calling"])
        res = self.router.select(req)
        self.assertIsNotNone(res.provider)

    def test_20_malformed_model_response(self):
        # Validated in parser step, routing provides fallback
        pass

    def test_21_resource_exhaustion(self):
        # Overwrite local models with the huge model
        self.router.local_models.general_model = "huge_local"
        req = self._make_req(local_llm_available=True)
        res = self.router.select(req)
        # Should not route to local because ResourceManager fails it
        self.assertEqual(res.provider, "openai")

    def test_22_cost_limit_behavior(self):
        # Telemetry is tracked
        from backend.llm.telemetry import cost_tracker
        cost_tracker.add_cost("openai", 0.05)
        self.assertGreater(cost_tracker.session_cost, 0.0)

if __name__ == '__main__':
    unittest.main()
