from typing import Optional, Dict, Any

from .schema import (
    JarvisConfig,
    EnvironmentProfile,
    OperatingMode,
    EnvironmentConfig,
    NetworkConfig,
    PathConfig,
    FeatureFlags,
    ResourceLimits,
    LocalAIConfig,
    CloudAIConfig,
    ModelRoutingConfig,
    VoiceConfig,
    VisionConfig,
    MemoryConfig,
    SecurityConfig,
    LoggingConfig,
)
from .loader import load_config, find_project_root
from .validator import ConfigValidator, ConfigurationError, ValidationResult
from .banner import generate_startup_banner

_GLOBAL_CONFIG: Optional[JarvisConfig] = None


def get_config(
    profile: Optional[str] = None,
    mode: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
    force_reload: bool = False
) -> JarvisConfig:
    """
    Returns the cached global JarvisConfig singleton, or loads it on first call.
    """
    global _GLOBAL_CONFIG
    if _GLOBAL_CONFIG is None or force_reload or profile or mode or overrides:
        _GLOBAL_CONFIG = load_config(
            profile=profile,
            mode=mode,
            overrides=overrides
        )
    return _GLOBAL_CONFIG


def reload_config(**kwargs) -> JarvisConfig:
    """Forces reloading configuration from disk and environment."""
    return get_config(force_reload=True, **kwargs)


__all__ = [
    "JarvisConfig",
    "EnvironmentProfile",
    "OperatingMode",
    "EnvironmentConfig",
    "NetworkConfig",
    "PathConfig",
    "FeatureFlags",
    "ResourceLimits",
    "LocalAIConfig",
    "CloudAIConfig",
    "ModelRoutingConfig",
    "VoiceConfig",
    "VisionConfig",
    "MemoryConfig",
    "SecurityConfig",
    "LoggingConfig",
    "load_config",
    "find_project_root",
    "get_config",
    "reload_config",
    "ConfigValidator",
    "ConfigurationError",
    "ValidationResult",
    "generate_startup_banner",
]
