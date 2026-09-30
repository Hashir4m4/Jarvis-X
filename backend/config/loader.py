import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from .schema import JarvisConfig, EnvironmentProfile, OperatingMode

logger = logging.getLogger("JARVIS.ConfigLoader")


def find_project_root() -> Path:
    """Finds the repository project root directory."""
    env_root = os.getenv("JARVIS_ROOT")
    if env_root and os.path.isdir(env_root):
        return Path(env_root).resolve()

    # Walk up from this file's location (backend/config/loader.py -> backend/config -> backend -> root)
    candidate = Path(__file__).resolve().parents[2]
    if (candidate / "backend").is_dir() and (candidate / "configs").is_dir():
        return candidate

    # Fallback to current working directory if it contains backend
    cwd = Path(os.getcwd()).resolve()
    if (cwd / "backend").is_dir():
        return cwd

    return candidate


def deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merges overlay dictionary into base dictionary."""
    result = dict(base)
    for k, v in overlay.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def map_legacy_json_to_schema(legacy: Dict[str, Any]) -> Dict[str, Any]:
    """Converts existing configs/config.json structure into the new schema structure."""
    mapped: Dict[str, Any] = {}

    # LLM -> local_ai
    if "llm" in legacy:
        llm = legacy["llm"]
        mapped["local_ai"] = {
            "provider": llm.get("provider", "ollama"),
            "base_url": llm.get("base_url", "http://localhost:11434"),
            "default_model": llm.get("model", "qwen2.5-coder:7b"),
            "temperature": llm.get("temperature", 0.7),
            "timeout": llm.get("timeout", 60.0),
        }

    # VLM -> local_ai.vision_model
    if "vlm" in legacy:
        vlm = legacy["vlm"]
        mapped.setdefault("local_ai", {})["vision_model"] = vlm.get("model", "moondream:latest")

    # Logging
    if "logging" in legacy:
        mapped["logging"] = {
            "level": legacy["logging"].get("level", "INFO"),
            "file": legacy["logging"].get("file", "logs/jarvis.log"),
        }

    # Voice
    if "voice" in legacy:
        v = legacy["voice"]
        mapped["voice"] = {
            "wake_word": v.get("wake_word", "jarvis"),
            "tts_engine": v.get("tts_engine", "pyttsx3"),
            "stt_engine": v.get("stt_engine", "whisper"),
            "whisper_model": v.get("whisper_model", "base"),
            "energy_threshold": v.get("energy_threshold", 300),
            "dynamic_energy_threshold": v.get("dynamic_energy_threshold", True),
            "pause_threshold": v.get("pause_threshold", 0.8),
        }

    # Vision
    if "vision" in legacy:
        vi = legacy["vision"]
        mapped["vision"] = {
            "camera_index": vi.get("camera_index", 0),
            "target_fps": vi.get("target_fps", 15),
            "enable_object_detection": vi.get("enable_object_detection", True),
            "enable_face_detection": vi.get("enable_face_detection", True),
            "enable_hand_tracking": vi.get("enable_hand_tracking", True),
            "enable_ocr": vi.get("enable_ocr", True),
            "enable_barcode": vi.get("enable_barcode", True),
            "yolo_model": vi.get("yolo_model", "yolo11n.pt"),
        }

    # Memory & memory_advanced
    if "memory" in legacy:
        mapped.setdefault("memory", {})["max_context_messages"] = legacy["memory"].get("max_context_messages", 20)

    if "memory_advanced" in legacy:
        ma = legacy["memory_advanced"]
        mapped.setdefault("memory", {}).update({
            "sqlite_db_path": ma.get("sqlite_db_path", "memory/database_storage/jarvis.sqlite"),
            "chroma_db_path": ma.get("chroma_db_path", "memory/database_storage/chroma"),
            "embedding_model": ma.get("embedding_model", "all-MiniLM-L6-v2"),
            "retrieval_top_k": ma.get("retrieval_top_k", 3),
            "importance_threshold": ma.get("importance_threshold", 0.5),
            "vault_path": ma.get("vault_path", "vault"),
        })

    # Direct passthroughs if already matching schema keys
    for key in ("environment", "network", "paths", "features", "limits", "cloud_ai", "routing", "security"):
        if key in legacy:
            mapped[key] = legacy[key]

    return mapped


def load_env_overrides() -> Dict[str, Any]:
    """Extracts known JARVIS environment variables into structured schema dictionary."""
    env: Dict[str, Any] = {}

    # 1. Environment & Mode
    profile_str = os.getenv("JARVIS_ENV") or os.getenv("ENVIRONMENT")
    if profile_str:
        env.setdefault("environment", {})["profile"] = profile_str

    mode_str = os.getenv("JARVIS_MODE") or os.getenv("OPERATING_MODE")
    if mode_str:
        env.setdefault("environment", {})["mode"] = mode_str

    if "JARVIS_DEBUG" in os.environ or "DEBUG" in os.environ:
        debug_val = os.getenv("JARVIS_DEBUG", os.getenv("DEBUG", "false")).lower() in ("true", "1", "yes")
        env.setdefault("environment", {})["debug"] = debug_val

    # 2. Network
    host = os.getenv("FASTAPI_HOST")
    if host:
        env.setdefault("network", {})["backend_host"] = host
    port = os.getenv("FASTAPI_PORT")
    if port:
        try:
            env.setdefault("network", {})["backend_port"] = int(port)
        except ValueError:
            pass
    hud_port = os.getenv("HUD_PORT") or os.getenv("FRONTEND_PORT")
    if hud_port:
        try:
            env.setdefault("network", {})["frontend_port"] = int(hud_port)
        except ValueError:
            pass

    # 3. Local AI / Ollama
    ollama_url = os.getenv("OLLAMA_BASE_URL")
    if ollama_url:
        env.setdefault("local_ai", {})["base_url"] = ollama_url
        env.setdefault("network", {})["ollama_url"] = ollama_url
    ollama_model = os.getenv("OLLAMA_MODEL") or os.getenv("LOCAL_CODING_MODEL")
    if ollama_model:
        env.setdefault("local_ai", {})["default_model"] = ollama_model
        env.setdefault("local_ai", {})["coding_model"] = ollama_model

    for role_env, role_key in [
        ("LOCAL_GENERAL_MODEL", "general_model"),
        ("LOCAL_FAST_MODEL", "fast_model"),
        ("LOCAL_REASONING_MODEL", "reasoning_model"),
        ("LOCAL_VISION_MODEL", "vision_model"),
    ]:
        val = os.getenv(role_env)
        if val:
            env.setdefault("local_ai", {})[role_key] = val

    # 4. Cloud AI
    cloud_enabled = os.getenv("CLOUD_PROVIDER_ENABLED")
    if cloud_enabled is not None:
        c_bool = cloud_enabled.lower() in ("true", "1", "yes")
        env.setdefault("cloud_ai", {})["enabled"] = c_bool
        env.setdefault("features", {})["cloud_ai_enabled"] = c_bool

    for key_env, key_target in [
        ("OPENAI_API_KEY", "openai_api_key"),
        ("OPENAI_BASE_URL", "openai_base_url"),
        ("OPENAI_MODEL", "openai_model"),
        ("ANTHROPIC_API_KEY", "anthropic_api_key"),
        ("ANTHROPIC_BASE_URL", "anthropic_base_url"),
        ("ANTHROPIC_MODEL", "anthropic_model"),
        ("GEMINI_API_KEY", "gemini_api_key"),
        ("GEMINI_BASE_URL", "gemini_base_url"),
        ("GEMINI_MODEL", "gemini_model"),
        ("GROQ_API_KEY", "groq_api_key"),
    ]:
        val = os.getenv(key_env)
        if val:
            env.setdefault("cloud_ai", {})[key_target] = val

    # 5. Feature Flags
    for flag_env, flag_field in [
        ("VOICE_ENABLED", "voice_enabled"),
        ("VISION_ENABLED", "vision_enabled"),
        ("BROWSER_ENABLED", "browser_enabled"),
        ("AUTOMATION_ENABLED", "automation_enabled"),
        ("PLUGINS_ENABLED", "plugins_enabled"),
        ("MEMORY_ENABLED", "memory_enabled"),
        ("PROACTIVE_MODE_ENABLED", "proactive_enabled"),
        ("LOCAL_AI_ENABLED", "local_ai_enabled"),
        ("CLOUD_AI_ENABLED", "cloud_ai_enabled"),
        ("HYBRID_MODE_ENABLED", "hybrid_mode_enabled"),
        ("DIAGNOSTICS_ENABLED", "diagnostics_enabled"),
        ("DEVELOPER_MODE", "developer_mode"),
    ]:
        if flag_env in os.environ:
            env.setdefault("features", {})[flag_field] = os.environ[flag_env].lower() in ("true", "1", "yes")

    # 6. Logging
    log_level = os.getenv("LOG_LEVEL")
    if log_level:
        env.setdefault("logging", {})["level"] = log_level

    # 7. Routing
    routing_pref = os.getenv("MODEL_ROUTING_PREFERENCE")
    if routing_pref:
        env.setdefault("routing", {})["routing_preference"] = routing_pref.upper()
    privacy_policy = os.getenv("MODEL_PRIVACY_POLICY")
    if privacy_policy:
        env.setdefault("routing", {})["privacy_policy"] = privacy_policy.upper()

    return env


def load_config(
    config_path: Optional[str] = None,
    profile: Optional[str] = None,
    mode: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None,
    load_dotenv_file: bool = True
) -> JarvisConfig:
    """
    Authoritative configuration loader with documented 4-tier precedence:
      1. Safe built-in schema defaults
      2. Configuration JSON files (`configs/config.json`, `configs/config.<profile>.json`)
      3. Environment variables (loaded from `.env` and `os.environ`)
      4. Explicit runtime overrides
    """
    root = find_project_root()

    # Step 1: Optionally load .env file from project root
    if load_dotenv_file:
        env_file = root / ".env"
        if env_file.is_file():
            load_dotenv(dotenv_path=env_file, override=False)

    # Step 2: Load base configuration JSON
    merged_data: Dict[str, Any] = {"paths": {"project_root": str(root)}}

    cfg_file = Path(config_path) if config_path else (root / "configs" / "config.json")
    if cfg_file.is_file():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                json_data = json.load(f)
            mapped_json = map_legacy_json_to_schema(json_data)
            merged_data = deep_merge(merged_data, mapped_json)
        except Exception as e:
            logger.warning(f"Could not load config file {cfg_file}: {e}")

    # Step 3: Determine Environment Profile and load profile-specific JSON if present
    env_profile = profile or os.getenv("JARVIS_ENV") or os.getenv("ENVIRONMENT")
    if env_profile:
        profile_clean = env_profile.strip().lower()
        profile_file = root / "configs" / f"config.{profile_clean}.json"
        if profile_file.is_file():
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    prof_json = json.load(f)
                merged_data = deep_merge(merged_data, map_legacy_json_to_schema(prof_json))
            except Exception as e:
                logger.warning(f"Could not load profile config {profile_file}: {e}")

    # Step 4: Merge Environment Variables
    env_overrides = load_env_overrides()
    merged_data = deep_merge(merged_data, env_overrides)

    # Step 5: Merge explicit runtime overrides
    if overrides:
        merged_data = deep_merge(merged_data, overrides)

    # Apply explicit profile or mode arguments if provided
    if profile:
        merged_data.setdefault("environment", {})["profile"] = profile
    if mode:
        merged_data.setdefault("environment", {})["mode"] = mode

    # Step 6: Operating Mode Rules Enforcement (Security & Offline Boundary)
    op_mode = merged_data.get("environment", {}).get("mode", OperatingMode.HYBRID)
    if isinstance(op_mode, str):
        op_mode = op_mode.lower()

    if op_mode == "offline":
        # In offline mode: cloud AI must be strictly disabled
        merged_data.setdefault("features", {})["cloud_ai_enabled"] = False
        merged_data.setdefault("cloud_ai", {})["enabled"] = False
        merged_data.setdefault("routing", {})["privacy_policy"] = "LOCAL_ONLY"
        merged_data.setdefault("routing", {})["routing_preference"] = "LOCAL"

    elif op_mode == "online":
        # In online mode: cloud AI is allowed, routing prefers cloud or auto
        merged_data.setdefault("features", {})["cloud_ai_enabled"] = True
        merged_data.setdefault("cloud_ai", {})["enabled"] = True
        merged_data.setdefault("routing", {})["privacy_policy"] = "CLOUD_ALLOWED"

    # Step 7: Instantiate and validate against Pydantic schema
    config = JarvisConfig(**merged_data)
    return config
