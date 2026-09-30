import os
import enum
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class EnvironmentProfile(str, enum.Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class OperatingMode(str, enum.Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    HYBRID = "hybrid"


class EnvironmentConfig(BaseModel):
    profile: EnvironmentProfile = EnvironmentProfile.DEVELOPMENT
    mode: OperatingMode = OperatingMode.HYBRID
    debug: bool = False
    config_version: str = "2.0"

    @field_validator("profile", mode="before")
    @classmethod
    def parse_profile(cls, v):
        if isinstance(v, str):
            v_clean = v.strip().lower()
            for p in EnvironmentProfile:
                if p.value == v_clean:
                    return p
        return v

    @field_validator("mode", mode="before")
    @classmethod
    def parse_mode(cls, v):
        if isinstance(v, str):
            v_clean = v.strip().lower()
            for m in OperatingMode:
                if m.value == v_clean:
                    return m
        return v


class NetworkConfig(BaseModel):
    backend_host: str = "127.0.0.1"
    backend_port: int = Field(8000, ge=1, le=65535)
    websocket_url: str = "ws://127.0.0.1:8000/ws/chat"
    frontend_port: int = Field(5173, ge=1, le=65535)
    frontend_url: str = "http://localhost:5173"
    ollama_url: str = "http://localhost:11434"
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    request_timeout: float = Field(30.0, gt=0)

    @field_validator("backend_port", "frontend_port", mode="before")
    @classmethod
    def parse_port(cls, v):
        try:
            return int(v)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid port number: {v}")


class PathConfig(BaseModel):
    project_root: str = Field(default_factory=lambda: str(Path(__file__).resolve().parents[2]))
    logs_dir: str = "logs"
    data_dir: str = "memory/database_storage"
    sqlite_path: str = "memory/database_storage/jarvis.sqlite"
    chroma_path: str = "memory/database_storage/chroma"
    vault_path: str = "vault"
    plugins_dir: str = "backend/plugins"
    skills_dir: str = "skills"
    temp_dir: str = "temp"
    cache_dir: str = ".cache"

    def resolve(self, path_str: str) -> Path:
        """Resolves relative paths against project_root, preserving absolute paths."""
        p = Path(path_str)
        if p.is_absolute():
            return p.resolve()
        return (Path(self.project_root) / p).resolve()

    def get_resolved_paths(self) -> Dict[str, Path]:
        return {
            "project_root": Path(self.project_root),
            "logs_dir": self.resolve(self.logs_dir),
            "data_dir": self.resolve(self.data_dir),
            "sqlite_path": self.resolve(self.sqlite_path),
            "chroma_path": self.resolve(self.chroma_path),
            "vault_path": self.resolve(self.vault_path),
            "plugins_dir": self.resolve(self.plugins_dir),
            "skills_dir": self.resolve(self.skills_dir),
            "temp_dir": self.resolve(self.temp_dir),
            "cache_dir": self.resolve(self.cache_dir),
        }


class FeatureFlags(BaseModel):
    voice_enabled: bool = True
    vision_enabled: bool = True
    browser_enabled: bool = True
    automation_enabled: bool = True
    plugins_enabled: bool = True
    memory_enabled: bool = True
    proactive_enabled: bool = True
    local_ai_enabled: bool = True
    cloud_ai_enabled: bool = False
    hybrid_mode_enabled: bool = True
    diagnostics_enabled: bool = True
    developer_mode: bool = True

    @field_validator("*", mode="before")
    @classmethod
    def parse_bool(cls, v):
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "on", "enabled")
        return bool(v)


class ResourceLimits(BaseModel):
    llm_timeout: float = Field(60.0, gt=0)
    tool_timeout: float = Field(30.0, gt=0)
    agent_timeout: float = Field(120.0, gt=0)
    browser_timeout: float = Field(30.0, gt=0)
    max_concurrent_agents: int = Field(4, ge=1, le=16)
    max_task_depth: int = Field(2, ge=1, le=10)
    max_tool_calls: int = Field(20, ge=1, le=100)
    max_retrieval_results: int = Field(3, ge=1, le=50)
    max_file_size_mb: float = Field(50.0, gt=0)
    max_log_size_mb: float = Field(10.0, gt=0)
    max_subprocess_runtime: float = Field(60.0, gt=0)
    voice_timeout: float = Field(10.0, gt=0)
    vision_fps: int = Field(15, ge=1, le=60)


class LocalAIConfig(BaseModel):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    default_model: str = "qwen2.5-coder:7b"
    general_model: str = "qwen2.5-coder:7b"
    fast_model: str = "qwen2.5:1.5b"
    reasoning_model: str = "deepseek-r1:7b"
    coding_model: str = "qwen2.5-coder:7b"
    vision_model: str = "moondream:latest"
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    timeout: float = Field(60.0, gt=0)
    context_length: int = Field(8192, ge=512)
    streaming: bool = True
    enabled: bool = True


class CloudAIConfig(BaseModel):
    enabled: bool = False
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com/v1"
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-1.5-flash"
    groq_api_key: str = ""
    general_model: str = "gpt-4o-mini"
    reasoning_model: str = "o3-mini"
    coding_model: str = "claude-3-5-sonnet-20241022"
    fast_model: str = "gpt-4o-mini"
    vision_model: str = "gpt-4o"

    def has_any_credentials(self) -> bool:
        return bool(
            self.openai_api_key.strip()
            or self.anthropic_api_key.strip()
            or self.gemini_api_key.strip()
            or self.groq_api_key.strip()
        )


class ModelRoutingConfig(BaseModel):
    routing_preference: str = "AUTO"  # AUTO, LOCAL, CLOUD, HYBRID
    privacy_policy: str = "PREFER_LOCAL"  # PREFER_LOCAL, LOCAL_ONLY, CLOUD_ALLOWED


class VoiceConfig(BaseModel):
    enabled: bool = True
    wake_word: str = "jarvis"
    tts_engine: str = "pyttsx3"
    stt_engine: str = "whisper"
    whisper_model: str = "base"
    energy_threshold: int = Field(300, ge=50, le=5000)
    dynamic_energy_threshold: bool = True
    pause_threshold: float = Field(0.8, ge=0.1, le=5.0)


class VisionConfig(BaseModel):
    enabled: bool = True
    online_vision_enabled: bool = False
    local_vision_enabled: bool = True
    camera_index: int = 0
    target_fps: int = Field(15, ge=1, le=60)
    enable_object_detection: bool = True
    enable_face_detection: bool = True
    enable_hand_tracking: bool = True
    enable_ocr: bool = True
    enable_barcode: bool = True
    yolo_model: str = "yolo11n.pt"


class MemoryConfig(BaseModel):
    max_context_messages: int = Field(20, ge=1, le=200)
    sqlite_db_path: str = "memory/database_storage/jarvis.sqlite"
    chroma_db_path: str = "memory/database_storage/chroma"
    embedding_model: str = "all-MiniLM-L6-v2"
    retrieval_top_k: int = Field(3, ge=1, le=50)
    importance_threshold: float = Field(0.5, ge=0.0, le=1.0)
    vault_path: str = "vault"


class SecurityConfig(BaseModel):
    log_dir: str = "logs"
    audit_log_file: str = "automation_audit.log"
    jsonl_audit_file: str = "security_audit.jsonl"
    enable_confirmation_for_destructive: bool = True
    block_untrusted_paths: bool = True
    secret_redaction: bool = True


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "logs/jarvis.log"
    max_bytes: int = Field(10485760, ge=1024)  # 10MB
    backup_count: int = Field(5, ge=1, le=50)
    redact_secrets: bool = True

    @field_validator("level", mode="before")
    @classmethod
    def parse_level(cls, v):
        if isinstance(v, str):
            v_upper = v.strip().upper()
            if v_upper in ("DEBUG", "INFO", "WARNING", "WARN", "ERROR", "CRITICAL"):
                return "WARNING" if v_upper == "WARN" else v_upper
        return "INFO"


class JarvisConfig(BaseModel):
    """
    Unified, authoritative configuration root for JARVIS X.
    Maintains 100% backward compatibility with dictionary consumers.
    """
    environment: EnvironmentConfig = Field(default_factory=EnvironmentConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    paths: PathConfig = Field(default_factory=PathConfig)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    limits: ResourceLimits = Field(default_factory=ResourceLimits)
    local_ai: LocalAIConfig = Field(default_factory=LocalAIConfig)
    cloud_ai: CloudAIConfig = Field(default_factory=CloudAIConfig)
    routing: ModelRoutingConfig = Field(default_factory=ModelRoutingConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    vision: VisionConfig = Field(default_factory=VisionConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def to_legacy_dict(self) -> Dict[str, Any]:
        """
        Exports configuration matching the legacy JSON structure expected
        by JarvisCore, Brain, MemoryManager, and existing skills.
        """
        resolved = self.paths.get_resolved_paths()
        return {
            "config_version": self.environment.config_version,
            "environment": self.environment.profile.value,
            "operating_mode": self.environment.mode.value,
            "offline_mode": self.environment.mode == OperatingMode.OFFLINE,
            "cloud_enabled": self.features.cloud_ai_enabled and self.environment.mode != OperatingMode.OFFLINE,
            "llm": {
                "provider": self.local_ai.provider,
                "base_url": self.local_ai.base_url,
                "model": self.local_ai.default_model,
                "temperature": self.local_ai.temperature,
                "timeout": self.local_ai.timeout,
                "system_prompt": (
                    "You are Jarvis, a highly capable, autonomous, and intelligent AI assistant. "
                    "You are concise, highly analytical, and always ready to help your creator. "
                    "Keep your answers brief, as they will be spoken aloud."
                ),
                # Cloud provider settings for cloud_manager
                "openai_api_key": self.cloud_ai.openai_api_key,
                "openai_base_url": self.cloud_ai.openai_base_url,
                "openai_model": self.cloud_ai.openai_model,
                "anthropic_api_key": self.cloud_ai.anthropic_api_key,
                "anthropic_base_url": self.cloud_ai.anthropic_base_url,
                "anthropic_model": self.cloud_ai.anthropic_model,
                "gemini_api_key": self.cloud_ai.gemini_api_key,
                "gemini_base_url": self.cloud_ai.gemini_base_url,
                "gemini_model": self.cloud_ai.gemini_model,
                "groq_api_key": self.cloud_ai.groq_api_key,
            },
            "memory": {
                "max_context_messages": self.memory.max_context_messages,
            },
            "logging": {
                "level": self.logging.level,
                "file": str(resolved["logs_dir"] / "jarvis.log"),
            },
            "voice": {
                "enabled": self.features.voice_enabled,
                "wake_word": self.voice.wake_word,
                "tts_engine": self.voice.tts_engine,
                "stt_engine": self.voice.stt_engine,
                "whisper_model": self.voice.whisper_model,
                "energy_threshold": self.voice.energy_threshold,
                "dynamic_energy_threshold": self.voice.dynamic_energy_threshold,
                "pause_threshold": self.voice.pause_threshold,
            },
            "vision": {
                "enabled": self.features.vision_enabled,
                "online_vision_enabled": self.vision.online_vision_enabled,
                "local_vision_enabled": self.vision.local_vision_enabled,
                "camera_index": self.vision.camera_index,
                "target_fps": self.vision.target_fps,
                "enable_object_detection": self.vision.enable_object_detection,
                "enable_face_detection": self.vision.enable_face_detection,
                "enable_hand_tracking": self.vision.enable_hand_tracking,
                "enable_ocr": self.vision.enable_ocr,
                "enable_barcode": self.vision.enable_barcode,
                "yolo_model": self.vision.yolo_model,
            },
            "memory_advanced": {
                "sqlite_db_path": str(resolved["sqlite_path"]),
                "chroma_db_path": str(resolved["chroma_path"]),
                "embedding_model": self.memory.embedding_model,
                "retrieval_top_k": self.memory.retrieval_top_k,
                "importance_threshold": self.memory.importance_threshold,
                "vault_path": str(resolved["vault_path"]),
            },
            "vlm": {
                "model": self.local_ai.vision_model,
                "host": self.local_ai.base_url,
                "max_image_size": [800, 800],
            },
            "security": {
                "log_dir": str(resolved["logs_dir"]),
                "audit_log_file": self.security.audit_log_file,
                "jsonl_audit_file": self.security.jsonl_audit_file,
            },
            "network": {
                "host": self.network.backend_host,
                "port": self.network.backend_port,
                "cors_origins": self.network.cors_origins,
            },
            "limits": self.limits.model_dump(),
            "features": self.features.model_dump(),
        }

    def to_sanitized_dict(self) -> Dict[str, Any]:
        """Returns full config dict with all secrets/tokens masked."""
        data = self.model_dump()
        c_ai = data.get("cloud_ai", {})
        for key in ["openai_api_key", "anthropic_api_key", "gemini_api_key", "groq_api_key"]:
            if c_ai.get(key):
                val = c_ai[key]
                if len(val) >= 8:
                    c_ai[key] = f"{val[:3]}...{val[-3:]}"
                else:
                    c_ai[key] = "[REDACTED]"
        return data
