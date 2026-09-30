import logging
from urllib.parse import urlparse
from typing import List, Dict, Any, Tuple
from pathlib import Path

from .schema import JarvisConfig, OperatingMode, EnvironmentProfile

logger = logging.getLogger("JARVIS.ConfigValidator")


class ConfigurationError(ValueError):
    """Raised when critical configuration validation fails."""
    pass


class ValidationResult:
    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings

    def __repr__(self) -> str:
        return f"<ValidationResult valid={self.is_valid} errors={len(self.errors)} warnings={len(self.warnings)}>"


class ConfigValidator:
    """
    Validates JARVIS X configuration for security, network correctness,
    directory availability, and operating mode consistency.
    """

    @staticmethod
    def validate(config: JarvisConfig, auto_create_dirs: bool = True) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Network Validation
        # Backend port
        if not (1 <= config.network.backend_port <= 65535):
            errors.append(f"Invalid backend_port: {config.network.backend_port}. Must be between 1 and 65535.")

        # Frontend port
        if not (1 <= config.network.frontend_port <= 65535):
            errors.append(f"Invalid frontend_port: {config.network.frontend_port}. Must be between 1 and 65535.")

        # Port collision
        if config.network.backend_port == config.network.frontend_port:
            errors.append(
                f"Port conflict: backend_port and frontend_port cannot both be {config.network.backend_port}."
            )

        # URLs
        for url_name, url_val, valid_schemes in [
            ("ollama_url", config.network.ollama_url, ("http", "https")),
            ("websocket_url", config.network.websocket_url, ("ws", "wss")),
            ("frontend_url", config.network.frontend_url, ("http", "https")),
        ]:
            parsed = urlparse(url_val)
            if not parsed.scheme or parsed.scheme not in valid_schemes or not parsed.netloc:
                errors.append(
                    f"Invalid {url_name}: '{url_val}'. Scheme must be one of {valid_schemes} with a valid host."
                )

        # 2. Local AI & Model Names
        if not config.local_ai.default_model.strip():
            errors.append("local_ai.default_model cannot be empty.")

        if config.local_ai.provider not in ("ollama", "mock"):
            warnings.append(f"Uncommon local_ai.provider '{config.local_ai.provider}'. Expected 'ollama' or 'mock'.")

        # 3. Mode & Offline Boundary Enforcement
        if config.environment.mode == OperatingMode.OFFLINE:
            if config.features.cloud_ai_enabled or config.cloud_ai.enabled:
                errors.append("Offline Mode Violation: Cloud AI cannot be enabled when operating_mode is OFFLINE.")
            if config.routing.privacy_policy != "LOCAL_ONLY":
                warnings.append("Offline Mode Warning: privacy_policy should be LOCAL_ONLY in OFFLINE mode.")

        elif config.environment.mode == OperatingMode.ONLINE:
            if not config.cloud_ai.has_any_credentials():
                warnings.append(
                    "Online mode configured, but no cloud API keys (OpenAI, Anthropic, Gemini, Groq) were detected."
                )

        # 4. Resource Limits Validation
        if config.limits.llm_timeout <= 0:
            errors.append(f"Invalid llm_timeout: {config.limits.llm_timeout}. Must be > 0.")

        if config.limits.max_task_depth <= 0 or config.limits.max_task_depth > 10:
            errors.append(f"Invalid max_task_depth: {config.limits.max_task_depth}. Must be 1..10.")

        if config.limits.max_concurrent_agents <= 0 or config.limits.max_concurrent_agents > 16:
            errors.append(f"Invalid max_concurrent_agents: {config.limits.max_concurrent_agents}. Must be 1..16.")

        # 5. Directory Creation / Validation
        if auto_create_dirs:
            resolved = config.paths.get_resolved_paths()
            for dir_key in ("logs_dir", "data_dir", "temp_dir"):
                p = resolved.get(dir_key)
                if p:
                    try:
                        p.mkdir(parents=True, exist_ok=True)
                    except Exception as e:
                        warnings.append(f"Could not ensure directory '{p}': {e}")

        # 6. Configuration Version Check
        if config.environment.config_version != "2.0":
            warnings.append(
                f"Configuration version mismatch: found '{config.environment.config_version}', expected '2.0'."
            )

        is_valid = len(errors) == 0
        return ValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)

    @classmethod
    def validate_or_raise(cls, config: JarvisConfig) -> ValidationResult:
        result = cls.validate(config)
        if not result.is_valid:
            msg = "Configuration validation failed with errors:\n  - " + "\n  - ".join(result.errors)
            logger.error(msg)
            raise ConfigurationError(msg)
        for w in result.warnings:
            logger.warning(f"[CONFIG WARNING] {w}")
        return result
