import json
import os
import logging

logger = logging.getLogger(__name__)

DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")


def load_config(path: str = None) -> dict:
    """
    Loads the Jarvis X configuration dictionary.
    Bridges legacy callers to the centralized, validated backend.config engine
    while preserving 100% backward compatibility for callers expecting a dictionary.
    """
    config_path = path or DEFAULT_CONFIG_PATH

    try:
        from backend.config.loader import load_config as _load_central_config
        config_obj = _load_central_config(config_path=config_path)
        return config_obj.to_legacy_dict()
    except Exception as e:
        logger.warning(f"Could not use centralized config loader ({e}). Falling back to JSON parse.")

    if not os.path.exists(config_path):
        logger.warning(f"Config file not found at {config_path}. Using defaults.")
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}
