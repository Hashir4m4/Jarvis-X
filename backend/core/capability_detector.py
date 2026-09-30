import enum
import logging
import socket
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger("JARVIS.CapabilityDetector")


class AIMode(str, enum.Enum):
    """Current operating AI and connectivity mode."""
    LOCAL = "LOCAL"
    HYBRID = "HYBRID"
    CLOUD = "CLOUD"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"


@dataclass
class CapabilityState:
    """Current snapshot of system intelligence, hardware, and cloud capabilities."""
    internet_available: bool = False
    local_llm_available: bool = False
    cloud_available: bool = False
    local_stt_available: bool = False
    local_tts_available: bool = False
    local_memory_available: bool = True
    local_vision_available: bool = False
    automation_available: bool = True
    active_mode: AIMode = AIMode.OFFLINE
    active_provider: str = "ollama"
    active_model: str = "qwen2.5-coder:7b"
    cloud_providers: Dict[str, Any] = field(default_factory=dict)
    hardware_info: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "internet_available": self.internet_available,
            "local_llm_available": self.local_llm_available,
            "cloud_available": self.cloud_available,
            "local_stt_available": self.local_stt_available,
            "local_tts_available": self.local_tts_available,
            "local_memory_available": self.local_memory_available,
            "local_vision_available": self.local_vision_available,
            "automation_available": self.automation_available,
            "active_mode": self.active_mode.value if hasattr(self.active_mode, "value") else str(self.active_mode),
            "active_provider": self.active_provider,
            "active_model": self.active_model,
            "cloud_providers": self.cloud_providers,
            "hardware_info": self.hardware_info,
            "timestamp": self.timestamp
        }

    def to_hud_payload(self) -> Dict[str, Any]:
        """Safe payload formatted for HUD telemetry emission without leaking API keys."""
        return {
            "mode": self.active_mode.value if hasattr(self.active_mode, "value") else str(self.active_mode),
            "active_provider": self.active_provider,
            "active_model": self.active_model,
            "local_llm_available": self.local_llm_available,
            "cloud_available": self.cloud_available,
            "internet_available": self.internet_available,
            "local_stt_available": self.local_stt_available,
            "local_tts_available": self.local_tts_available,
            "cloud_providers": self.cloud_providers,
            "timestamp": self.timestamp
        }


class CapabilityDetector:
    """
    Detects connectivity, local LLM status, cloud provider availability, voice subsystems, memory,
    and determines the current operating AIMode with non-blocking TTL caching.
    """

    def __init__(self, cache_ttl_seconds: float = 15.0):
        self.cache_ttl = cache_ttl_seconds
        self._last_internet_check: float = 0.0
        self._cached_internet_status: bool = False
        self._last_state: Optional[CapabilityState] = None

    def check_internet(self, timeout: float = 0.2, force_refresh: bool = False) -> bool:
        """
        Fast socket connection check to public DNS resolvers (1.1.1.1 / 8.8.8.8) on port 53.
        Results are cached for cache_ttl_seconds to avoid introducing request latency.
        """
        now = time.time()
        if not force_refresh and (now - self._last_internet_check < self.cache_ttl):
            return self._cached_internet_status

        self._last_internet_check = now
        for host in ("1.1.1.1", "8.8.8.8"):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout)
                sock.connect((host, 53))
                sock.close()
                self._cached_internet_status = True
                return True
            except Exception:
                continue

        self._cached_internet_status = False
        return False

    def detect(
        self,
        llm_provider: Optional[Any] = None,
        voice_manager: Optional[Any] = None,
        memory_manager: Optional[Any] = None,
        cloud_manager: Optional[Any] = None,
        force_refresh: bool = False
    ) -> CapabilityState:
        """Assembles a full CapabilityState snapshot."""
        internet_up = self.check_internet(force_refresh=force_refresh)

        # 1. Local LLM check
        local_llm_up = False
        provider_name = "ollama"
        model_name = "qwen2.5-coder:7b"

        if llm_provider:
            provider_name = getattr(llm_provider, "name", "unknown")
            model_name = getattr(llm_provider, "model_name", "unknown")
            try:
                local_llm_up = bool(llm_provider.is_available())
            except Exception as e:
                logger.debug(f"LLM availability check error: {e}")
                local_llm_up = False

        # 2. Cloud Providers check
        cloud_up = False
        cloud_statuses = {}
        if cloud_manager and internet_up:
            try:
                cloud_payload = cloud_manager.to_hud_payload()
                cloud_statuses = cloud_payload.get("providers", {})
                cloud_up = cloud_payload.get("available_providers_count", 0) > 0
            except Exception as e:
                logger.debug(f"Cloud provider manager status check error: {e}")

        # 2b. Local Vision Check
        local_vision_up = False
        if local_llm_up:
            try:
                # Check if local VLM or Ollama vision model exists
                import requests
                vlm_res = requests.get("http://localhost:11434/api/tags", timeout=0.2)
                if vlm_res.status_code == 200:
                    models = [m.get("name", "") for m in vlm_res.json().get("models", [])]
                    local_vision_up = any("moondream" in m or "llava" in m for m in models)
            except Exception:
                local_vision_up = False

        # 3. Voice Subsystems check
        stt_up = True
        tts_up = True
        if voice_manager:
            try:
                stt_up = hasattr(voice_manager, "stt") and voice_manager.stt is not None
                tts_up = hasattr(voice_manager, "tts") and voice_manager.tts is not None
            except Exception:
                pass

        # 4. Memory Subsystem check
        memory_up = True
        if memory_manager:
            try:
                memory_up = hasattr(memory_manager, "sqlite") and memory_manager.sqlite is not None
            except Exception:
                memory_up = True

        # 5. Determine AI Mode
        if not internet_up and not local_llm_up:
            mode = AIMode.OFFLINE if (stt_up and tts_up and memory_up) else AIMode.DEGRADED
        elif not internet_up and local_llm_up:
            mode = AIMode.LOCAL
        elif internet_up and local_llm_up:
            mode = AIMode.HYBRID
        elif internet_up and not local_llm_up and cloud_up:
            mode = AIMode.CLOUD
        elif internet_up and not local_llm_up:
            mode = AIMode.OFFLINE
        else:
            mode = AIMode.DEGRADED

        state = CapabilityState(
            internet_available=internet_up,
            local_llm_available=local_llm_up,
            cloud_available=cloud_up,
            local_stt_available=stt_up,
            local_tts_available=tts_up,
            local_memory_available=memory_up,
            local_vision_available=local_vision_up,
            automation_available=True,
            active_mode=mode,
            active_provider=provider_name,
            active_model=model_name,
            cloud_providers=cloud_statuses,
            timestamp=time.time()
        )
        self._last_state = state
        return state
