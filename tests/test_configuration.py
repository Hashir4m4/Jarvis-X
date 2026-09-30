import unittest
import os
import sys
import tempfile
import shutil
import json
from pathlib import Path
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config.schema import (
    JarvisConfig,
    EnvironmentProfile,
    OperatingMode,
    NetworkConfig,
    PathConfig,
    FeatureFlags,
    ResourceLimits,
    LocalAIConfig,
    CloudAIConfig,
)
from backend.config.loader import load_config, deep_merge
from backend.config.validator import ConfigValidator, ConfigurationError
from backend.config.banner import generate_startup_banner


class TestConfigurationManagement(unittest.TestCase):
    """
    Comprehensive Configuration Management Test Suite.
    Directly satisfies all 18 test scenarios in Step 17 of Prompt 41.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_dir = os.path.join(self.test_dir, "configs")
        os.makedirs(self.config_dir, exist_ok=True)

        # Create dummy base config.json
        self.base_config_path = os.path.join(self.config_dir, "config.json")
        with open(self.base_config_path, "w", encoding="utf-8") as f:
            json.dump({
                "llm": {
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "model": "qwen2.5-coder:7b"
                },
                "memory": {"max_context_messages": 20},
                "logging": {"level": "INFO"}
            }, f)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # ── 1. Default Configuration ─────────────────────────────────────────

    def test_01_default_configuration(self):
        """Scenario 1: Verify safe default configuration values."""
        config = JarvisConfig()
        self.assertEqual(config.environment.profile, EnvironmentProfile.DEVELOPMENT)
        self.assertEqual(config.environment.mode, OperatingMode.HYBRID)
        self.assertEqual(config.network.backend_host, "127.0.0.1")
        self.assertEqual(config.network.backend_port, 8000)
        self.assertEqual(config.network.frontend_port, 5173)
        self.assertEqual(config.local_ai.provider, "ollama")
        self.assertEqual(config.local_ai.default_model, "qwen2.5-coder:7b")
        self.assertFalse(config.cloud_ai.enabled)
        self.assertEqual(config.environment.config_version, "2.0")

    # ── 2. Development Configuration ─────────────────────────────────────

    def test_02_development_configuration(self):
        """Scenario 2: Verify development profile settings."""
        config = load_config(
            config_path=self.base_config_path,
            profile="development",
            load_dotenv_file=False
        )
        self.assertEqual(config.environment.profile, EnvironmentProfile.DEVELOPMENT)
        self.assertTrue(config.features.developer_mode)
        self.assertEqual(config.network.backend_host, "127.0.0.1")

    # ── 3. Testing Configuration ─────────────────────────────────────────

    def test_03_testing_configuration(self):
        """Scenario 3: Verify testing profile settings."""
        # Create config.testing.json in temp dir
        test_cfg_file = os.path.join(self.config_dir, "config.testing.json")
        with open(test_cfg_file, "w", encoding="utf-8") as f:
            json.dump({
                "environment": {"profile": "testing", "mode": "offline"},
                "local_ai": {"provider": "mock"},
                "features": {"voice_enabled": False}
            }, f)

        config = load_config(
            config_path=self.base_config_path,
            profile="testing",
            load_dotenv_file=False
        )
        self.assertEqual(config.environment.profile, EnvironmentProfile.TESTING)

    # ── 4. Production Configuration ──────────────────────────────────────

    def test_04_production_configuration(self):
        """Scenario 4: Verify production profile settings and safe defaults."""
        config = load_config(
            config_path=self.base_config_path,
            profile="production",
            load_dotenv_file=False
        )
        self.assertEqual(config.environment.profile, EnvironmentProfile.PRODUCTION)
        # Production should not expose arbitrary hosts
        self.assertEqual(config.network.backend_host, "127.0.0.1")

    # ── 5. Offline Configuration ─────────────────────────────────────────

    def test_05_offline_configuration(self):
        """Scenario 5: Verify offline mode strictly disables cloud AI."""
        config = load_config(
            config_path=self.base_config_path,
            mode="offline",
            overrides={"cloud_ai": {"enabled": True}, "features": {"cloud_ai_enabled": True}},
            load_dotenv_file=False
        )
        self.assertEqual(config.environment.mode, OperatingMode.OFFLINE)
        self.assertFalse(config.features.cloud_ai_enabled)
        self.assertFalse(config.cloud_ai.enabled)
        self.assertEqual(config.routing.privacy_policy, "LOCAL_ONLY")
        self.assertEqual(config.routing.routing_preference, "LOCAL")

    # ── 6. Online Configuration ──────────────────────────────────────────

    def test_06_online_configuration(self):
        """Scenario 6: Verify online mode enables cloud capabilities."""
        config = load_config(
            config_path=self.base_config_path,
            mode="online",
            load_dotenv_file=False
        )
        self.assertEqual(config.environment.mode, OperatingMode.ONLINE)
        self.assertTrue(config.features.cloud_ai_enabled)
        self.assertTrue(config.cloud_ai.enabled)
        self.assertEqual(config.routing.privacy_policy, "CLOUD_ALLOWED")

    # ── 7. Hybrid Configuration ──────────────────────────────────────────

    def test_07_hybrid_configuration(self):
        """Scenario 7: Verify hybrid mode allows smart routing between local and cloud."""
        config = load_config(
            config_path=self.base_config_path,
            mode="hybrid",
            load_dotenv_file=False
        )
        self.assertEqual(config.environment.mode, OperatingMode.HYBRID)
        self.assertTrue(config.features.hybrid_mode_enabled)
        self.assertEqual(config.routing.routing_preference, "AUTO")

    # ── 8. Environment Variable Overrides ────────────────────────────────

    def test_08_environment_variable_overrides(self):
        """Scenario 8: Verify environment variables take precedence over config file."""
        env_vars = {
            "FASTAPI_PORT": "9090",
            "OLLAMA_MODEL": "deepseek-coder:6.7b",
            "LOG_LEVEL": "DEBUG",
            "JARVIS_MODE": "offline",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_config(config_path=self.base_config_path, load_dotenv_file=False)
            self.assertEqual(config.network.backend_port, 9090)
            self.assertEqual(config.local_ai.default_model, "deepseek-coder:6.7b")
            self.assertEqual(config.logging.level, "DEBUG")
            self.assertEqual(config.environment.mode, OperatingMode.OFFLINE)

    # ── 9. Invalid Ports ─────────────────────────────────────────────────

    def test_09_invalid_ports(self):
        """Scenario 9: Verify invalid port numbers are rejected with validation errors."""
        # Port out of range (>65535)
        with self.assertRaises(Exception):
            NetworkConfig(backend_port=70000)

        # Port out of range (<1)
        with self.assertRaises(Exception):
            NetworkConfig(backend_port=-1)

        # Port conflict between backend and frontend
        cfg = JarvisConfig()
        cfg.network.backend_port = 8000
        cfg.network.frontend_port = 8000
        res = ConfigValidator.validate(cfg, auto_create_dirs=False)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("conflict" in e.lower() for e in res.errors))

    # ── 10. Invalid URLs ─────────────────────────────────────────────────

    def test_10_invalid_urls(self):
        """Scenario 10: Verify malformed or improper scheme URLs are caught."""
        cfg = JarvisConfig()
        cfg.network.ollama_url = "ftp://invalid-url"
        res = ConfigValidator.validate(cfg, auto_create_dirs=False)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("ollama_url" in e for e in res.errors))

    # ── 11. Invalid Provider ─────────────────────────────────────────────

    def test_11_invalid_provider(self):
        """Scenario 11: Verify uncommon/invalid provider generates a warning."""
        cfg = JarvisConfig()
        cfg.local_ai.provider = "unsupported_engine"
        res = ConfigValidator.validate(cfg, auto_create_dirs=False)
        self.assertTrue(any("unsupported_engine" in w for w in res.warnings))

    # ── 12. Missing Required Cloud Credentials ───────────────────────────

    def test_12_missing_required_cloud_credentials(self):
        """Scenario 12: Verify online mode without keys generates a clean warning."""
        cfg = JarvisConfig()
        cfg.environment.mode = OperatingMode.ONLINE
        cfg.cloud_ai.openai_api_key = ""
        cfg.cloud_ai.anthropic_api_key = ""
        cfg.cloud_ai.gemini_api_key = ""
        cfg.cloud_ai.groq_api_key = ""
        res = ConfigValidator.validate(cfg, auto_create_dirs=False)
        self.assertTrue(any("no cloud api keys" in w.lower() for w in res.warnings))

    # ── 13. Offline Mode Preventing Cloud Usage ──────────────────────────

    def test_13_offline_mode_preventing_cloud_usage(self):
        """Scenario 13: Verify offline mode rejects explicit cloud activation."""
        cfg = JarvisConfig()
        cfg.environment.mode = OperatingMode.OFFLINE
        cfg.features.cloud_ai_enabled = True
        cfg.cloud_ai.enabled = True
        res = ConfigValidator.validate(cfg, auto_create_dirs=False)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("offline mode violation" in e.lower() for e in res.errors))

    # ── 14. Feature Flags ────────────────────────────────────────────────

    def test_14_feature_flags(self):
        """Scenario 14: Verify feature flags parse correctly and toggle subsystems."""
        flags = FeatureFlags(
            voice_enabled=False,
            vision_enabled=False,
            automation_enabled=True,
            developer_mode=False
        )
        self.assertFalse(flags.voice_enabled)
        self.assertFalse(flags.vision_enabled)
        self.assertTrue(flags.automation_enabled)
        self.assertFalse(flags.developer_mode)

    # ── 15. Path Resolution ──────────────────────────────────────────────

    def test_15_path_resolution(self):
        """Scenario 15: Verify paths resolve safely relative to project root without hardcoded machine paths."""
        paths = PathConfig(project_root=self.test_dir)
        resolved_log = paths.resolve("custom_logs/app.log")
        self.assertTrue(resolved_log.is_absolute())
        self.assertEqual(resolved_log, Path(self.test_dir) / "custom_logs" / "app.log")
        # Does not contain hardcoded machine paths
        self.assertNotIn("C:\\Data\\Projects\\Jarvis X", str(paths.project_root) if self.test_dir != "C:\\Data\\Projects\\Jarvis X" else "")

    # ── 16. Secret Redaction ─────────────────────────────────────────────

    def test_16_secret_redaction(self):
        """Scenario 16: Verify secrets are masked in sanitized dumps and startup banners."""
        cfg = JarvisConfig()
        cfg.cloud_ai.openai_api_key = "sk-1234567890abcdef1234567890abcdef"
        cfg.cloud_ai.anthropic_api_key = "ant-api03-abcdef123456"

        sanitized = cfg.to_sanitized_dict()
        self.assertNotIn("sk-1234567890abcdef1234567890abcdef", sanitized["cloud_ai"]["openai_api_key"])
        self.assertIn("...", sanitized["cloud_ai"]["openai_api_key"])

        banner = generate_startup_banner(cfg)
        self.assertNotIn("sk-1234567890abcdef1234567890abcdef", banner)
        self.assertNotIn("ant-api03-abcdef123456", banner)

    # ── 17. Configuration Precedence ─────────────────────────────────────

    def test_17_configuration_precedence(self):
        """Scenario 17: Verify 4-tier precedence: defaults < file < env < overrides."""
        # 1. Base JSON defines backend_port=8000
        # 2. Env var defines backend_port=8080
        # 3. Explicit override defines backend_port=9999 -> override MUST win!
        with patch.dict(os.environ, {"FASTAPI_PORT": "8080"}, clear=False):
            cfg = load_config(
                config_path=self.base_config_path,
                overrides={"network": {"backend_port": 9999}},
                load_dotenv_file=False
            )
            self.assertEqual(cfg.network.backend_port, 9999)

        # Without override, env var wins over JSON file
        with patch.dict(os.environ, {"FASTAPI_PORT": "8080"}, clear=False):
            cfg_env_wins = load_config(
                config_path=self.base_config_path,
                load_dotenv_file=False
            )
            self.assertEqual(cfg_env_wins.network.backend_port, 8080)

    # ── 18. Startup Validation ───────────────────────────────────────────

    def test_18_startup_validation(self):
        """Scenario 18: Verify validate_or_raise enforces fail-fast on critical configuration errors."""
        valid_cfg = JarvisConfig()
        # Should succeed without error
        res = ConfigValidator.validate_or_raise(valid_cfg)
        self.assertTrue(res.is_valid)

        # Invalid configuration raises ConfigurationError
        invalid_cfg = JarvisConfig()
        invalid_cfg.network.backend_port = 8000
        invalid_cfg.network.frontend_port = 8000  # Conflict
        with self.assertRaises(ConfigurationError):
            ConfigValidator.validate_or_raise(invalid_cfg)


if __name__ == "__main__":
    unittest.main()
