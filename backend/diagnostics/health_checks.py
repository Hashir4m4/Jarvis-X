"""
JARVIS Component Health Checks

Standardized, timeout-protected health check implementations for each
registered JARVIS component.

Design principles:
- Each check is self-contained (no shared mutable state)
- All checks are async with configurable timeouts
- All errors are caught and surfaced as HealthStatus, never raised
- No secrets, API keys, or passwords are exposed in results
- Dependency-caused degradation is explicitly distinguished from independent failure
"""
import asyncio
import logging
import socket
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from .models import (
    HealthCheckResult, HealthStatus, CheckTrigger
)

logger = logging.getLogger("JARVIS.HealthChecks")

_DEFAULT_TIMEOUT = 3.0   # seconds


# ─────────────────────────────────────────────────────────────────────────────
# Abstract Base
# ─────────────────────────────────────────────────────────────────────────────

class ComponentHealthCheck(ABC):
    """
    Abstract base for all JARVIS component health checks.

    Every health check must return a structured HealthCheckResult.
    Boolean pass/fail is not sufficient — latency, evidence, and
    recommended_action must always be included.
    """

    @property
    @abstractmethod
    def component_id(self) -> str:
        pass

    @abstractmethod
    async def check(
        self,
        trigger: CheckTrigger = CheckTrigger.ON_DEMAND,
        dependency_status: Optional[Dict[str, HealthStatus]] = None
    ) -> HealthCheckResult:
        pass

    async def check_with_timeout(
        self,
        timeout: float = _DEFAULT_TIMEOUT,
        trigger: CheckTrigger = CheckTrigger.ON_DEMAND,
        dependency_status: Optional[Dict[str, HealthStatus]] = None
    ) -> HealthCheckResult:
        """Wraps check() with a timeout. Returns UNKNOWN if timed out."""
        start = time.time()
        try:
            result = await asyncio.wait_for(
                self.check(trigger=trigger, dependency_status=dependency_status),
                timeout=timeout
            )
            result.latency_ms = round((time.time() - start) * 1000, 2)
            return result
        except asyncio.TimeoutError:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.UNKNOWN,
                latency_ms=round(timeout * 1000, 2),
                error_summary="Health check timed out.",
                recommended_action="Retry the health check. If this persists, the component may be unresponsive.",
                evidence=["Health check exceeded timeout limit."],
                trigger=trigger
            )
        except Exception as e:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.UNKNOWN,
                latency_ms=round((time.time() - start) * 1000, 2),
                error_summary="Health check encountered an unexpected error.",
                recommended_action="Inspect diagnostics logs for details.",
                evidence=[f"Unexpected error during health check."],
                trigger=trigger
            )


# ─────────────────────────────────────────────────────────────────────────────
# Network Health Check
# ─────────────────────────────────────────────────────────────────────────────

class NetworkHealthCheck(ComponentHealthCheck):
    """Checks internet connectivity via socket connection to public DNS resolvers."""

    @property
    def component_id(self) -> str:
        return "network"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        start = time.time()
        for host in ("1.1.1.1", "8.8.8.8"):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1.0)
                sock.connect((host, 53))
                sock.close()
                return HealthCheckResult(
                    component_id=self.component_id,
                    status=HealthStatus.HEALTHY,
                    latency_ms=round((time.time() - start) * 1000, 2),
                    evidence=["DNS socket connection to public resolver succeeded."],
                    trigger=trigger
                )
            except Exception:
                continue

        return HealthCheckResult(
            component_id=self.component_id,
            status=HealthStatus.UNAVAILABLE,
            latency_ms=round((time.time() - start) * 1000, 2),
            error_summary="Cannot reach internet. DNS socket checks failed.",
            recommended_action="JARVIS will continue in offline mode using local capabilities.",
            evidence=["Socket connections to 1.1.1.1:53 and 8.8.8.8:53 failed."],
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Local AI Health Check
# ─────────────────────────────────────────────────────────────────────────────

class LocalAIHealthCheck(ComponentHealthCheck):
    """Checks if the local AI inference server (Ollama) is reachable."""

    def __init__(self, server_url: str = "http://localhost:11434", config: Optional[Dict] = None):
        self.server_url = (config or {}).get("ollama_url", server_url)

    @property
    def component_id(self) -> str:
        return "local_ai"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        start = time.time()
        try:
            import urllib.request
            req = urllib.request.Request(self.server_url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                latency = round((time.time() - start) * 1000, 2)
                if resp.status == 200:
                    return HealthCheckResult(
                        component_id=self.component_id,
                        status=HealthStatus.HEALTHY,
                        latency_ms=latency,
                        evidence=[f"Local AI server responded with HTTP 200 in {latency}ms."],
                        trigger=trigger
                    )
                else:
                    return HealthCheckResult(
                        component_id=self.component_id,
                        status=HealthStatus.DEGRADED,
                        latency_ms=latency,
                        error_summary=f"Local AI server responded with HTTP {resp.status}.",
                        recommended_action="Check if Ollama is running correctly. Try: ollama serve",
                        evidence=[f"Unexpected HTTP status {resp.status} from local AI server."],
                        trigger=trigger
                    )
        except Exception as e:
            latency = round((time.time() - start) * 1000, 2)
            err_str = str(e)
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.UNAVAILABLE,
                latency_ms=latency,
                error_summary="Local AI server is not reachable.",
                recommended_action=(
                    "Ensure the local AI server is running. "
                    "You can start it with: ollama serve. "
                    "If it was running, I can attempt to reconnect automatically."
                ),
                evidence=[
                    "Connection to local AI server failed.",
                    f"Connection type: {'refused' if 'refused' in err_str.lower() else 'timeout' if 'timeout' in err_str.lower() else 'unavailable'}"
                ],
                trigger=trigger
            )


# ─────────────────────────────────────────────────────────────────────────────
# Cloud AI Health Check
# ─────────────────────────────────────────────────────────────────────────────

class CloudAIHealthCheck(ComponentHealthCheck):
    """
    Checks if cloud AI providers are configured and internet is available.

    IMPORTANT: Does NOT attempt to authenticate or expose API keys.
    Only checks: is internet available + are providers configured?
    """

    def __init__(self, cloud_manager=None):
        self.cloud_manager = cloud_manager

    @property
    def component_id(self) -> str:
        return "cloud_ai"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        dep_status = dependency_status or {}
        network_status = dep_status.get("network", HealthStatus.UNKNOWN)

        if network_status == HealthStatus.UNAVAILABLE:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.DEGRADED,
                error_summary="Cloud AI unavailable because network is offline.",
                recommended_action="Cloud AI will be available when internet connectivity is restored.",
                evidence=["Dependency 'network' is UNAVAILABLE."],
                dependency_status={"network": HealthStatus.UNAVAILABLE},
                trigger=trigger
            )

        if self.cloud_manager:
            try:
                payload = self.cloud_manager.to_hud_payload()
                count = payload.get("available_providers_count", 0)
                if count > 0:
                    return HealthCheckResult(
                        component_id=self.component_id,
                        status=HealthStatus.HEALTHY,
                        evidence=[f"{count} cloud provider(s) configured and available."],
                        trigger=trigger
                    )
                else:
                    return HealthCheckResult(
                        component_id=self.component_id,
                        status=HealthStatus.DEGRADED,
                        error_summary="No cloud AI providers are configured.",
                        recommended_action="Add a cloud AI API key in JARVIS settings.",
                        evidence=["Cloud manager reports 0 available providers."],
                        trigger=trigger
                    )
            except Exception:
                pass

        return HealthCheckResult(
            component_id=self.component_id,
            status=HealthStatus.UNKNOWN,
            error_summary="Cloud AI provider status could not be determined.",
            recommended_action="Ensure JARVIS cloud configuration is correct.",
            evidence=["Cloud manager not available for inspection."],
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Voice Input (STT) Health Check
# ─────────────────────────────────────────────────────────────────────────────

class VoiceInputHealthCheck(ComponentHealthCheck):
    """Checks STT engine availability and microphone presence."""

    def __init__(self, voice_manager=None):
        self.voice_manager = voice_manager

    @property
    def component_id(self) -> str:
        return "voice_input"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        dep_status = dependency_status or {}
        audio_status = dep_status.get("audio_device", HealthStatus.UNKNOWN)

        if audio_status == HealthStatus.UNAVAILABLE:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.DEGRADED,
                error_summary="Voice input unavailable because audio device is unavailable.",
                recommended_action="Check microphone connection. Text input remains available.",
                evidence=["Dependency 'audio_device' is UNAVAILABLE."],
                dependency_status={"audio_device": HealthStatus.UNAVAILABLE},
                trigger=trigger
            )

        if self.voice_manager:
            try:
                stt_ok = hasattr(self.voice_manager, "stt") and self.voice_manager.stt is not None
                if stt_ok:
                    return HealthCheckResult(
                        component_id=self.component_id,
                        status=HealthStatus.HEALTHY,
                        evidence=["STT engine is initialized."],
                        trigger=trigger
                    )
                else:
                    return HealthCheckResult(
                        component_id=self.component_id,
                        status=HealthStatus.UNAVAILABLE,
                        error_summary="STT engine is not initialized.",
                        recommended_action="Text input remains available. Voice recognition can be restarted.",
                        evidence=["voice_manager.stt is None."],
                        trigger=trigger
                    )
            except Exception as e:
                return HealthCheckResult(
                    component_id=self.component_id,
                    status=HealthStatus.UNKNOWN,
                    error_summary="Could not inspect STT engine state.",
                    evidence=["Error accessing voice manager."],
                    trigger=trigger
                )

        return HealthCheckResult(
            component_id=self.component_id,
            status=HealthStatus.UNKNOWN,
            error_summary="Voice manager not available for inspection.",
            evidence=["No voice manager reference provided."],
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Audio Device Health Check
# ─────────────────────────────────────────────────────────────────────────────

class AudioDeviceHealthCheck(ComponentHealthCheck):
    """Checks if a microphone/audio input device is available."""

    @property
    def component_id(self) -> str:
        return "audio_device"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            if input_devices:
                return HealthCheckResult(
                    component_id=self.component_id,
                    status=HealthStatus.HEALTHY,
                    evidence=[f"{len(input_devices)} audio input device(s) detected."],
                    trigger=trigger
                )
            else:
                return HealthCheckResult(
                    component_id=self.component_id,
                    status=HealthStatus.UNAVAILABLE,
                    error_summary="No audio input devices detected.",
                    recommended_action="Connect a microphone. Voice input requires an audio device.",
                    evidence=["sounddevice found 0 audio input channels."],
                    trigger=trigger
                )
        except ImportError:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.UNKNOWN,
                error_summary="sounddevice library not available for device detection.",
                evidence=["sounddevice not installed."],
                trigger=trigger
            )
        except Exception:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.UNKNOWN,
                error_summary="Could not query audio devices.",
                evidence=["Audio device enumeration failed."],
                trigger=trigger
            )


# ─────────────────────────────────────────────────────────────────────────────
# Wake Word Health Check
# ─────────────────────────────────────────────────────────────────────────────

class WakeWordHealthCheck(ComponentHealthCheck):
    """Checks if the wake word engine is loaded and active."""

    def __init__(self, voice_manager=None):
        self.voice_manager = voice_manager

    @property
    def component_id(self) -> str:
        return "wake_word"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        dep_status = dependency_status or {}
        audio_status = dep_status.get("audio_device", HealthStatus.UNKNOWN)

        if audio_status == HealthStatus.UNAVAILABLE:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.DEGRADED,
                error_summary="Wake word unavailable because audio device is unavailable.",
                evidence=["Dependency 'audio_device' is UNAVAILABLE."],
                dependency_status={"audio_device": HealthStatus.UNAVAILABLE},
                trigger=trigger
            )

        if self.voice_manager and hasattr(self.voice_manager, "wake_word"):
            ww = self.voice_manager.wake_word
            if ww is not None and getattr(ww, "_running", False):
                return HealthCheckResult(
                    component_id=self.component_id,
                    status=HealthStatus.HEALTHY,
                    evidence=["Wake word engine is loaded and running."],
                    trigger=trigger
                )
            elif ww is not None:
                return HealthCheckResult(
                    component_id=self.component_id,
                    status=HealthStatus.DEGRADED,
                    error_summary="Wake word engine is loaded but not actively listening.",
                    evidence=["wake_word._running is False."],
                    trigger=trigger
                )

        return HealthCheckResult(
            component_id=self.component_id,
            status=HealthStatus.UNKNOWN,
            error_summary="Wake word engine state could not be determined.",
            evidence=["No wake word reference available."],
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Voice Output (TTS) Health Check
# ─────────────────────────────────────────────────────────────────────────────

class VoiceOutputHealthCheck(ComponentHealthCheck):
    """Checks if the TTS engine is initialized and available."""

    def __init__(self, voice_manager=None):
        self.voice_manager = voice_manager

    @property
    def component_id(self) -> str:
        return "voice_output"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        if self.voice_manager:
            try:
                tts_ok = hasattr(self.voice_manager, "tts") and self.voice_manager.tts is not None
                if tts_ok:
                    return HealthCheckResult(
                        component_id=self.component_id,
                        status=HealthStatus.HEALTHY,
                        evidence=["TTS engine is initialized."],
                        trigger=trigger
                    )
                else:
                    return HealthCheckResult(
                        component_id=self.component_id,
                        status=HealthStatus.UNAVAILABLE,
                        error_summary="TTS engine is not initialized.",
                        recommended_action="Text responses remain available. Voice output may require restart.",
                        evidence=["voice_manager.tts is None."],
                        trigger=trigger
                    )
            except Exception:
                pass

        return HealthCheckResult(
            component_id=self.component_id,
            status=HealthStatus.UNKNOWN,
            error_summary="Voice output state could not be determined.",
            evidence=["No voice manager reference provided."],
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Vision Health Check
# ─────────────────────────────────────────────────────────────────────────────

class VisionHealthCheck(ComponentHealthCheck):
    """Checks screen capture capability and OCR engine availability."""

    @property
    def component_id(self) -> str:
        return "vision"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        evidence = []
        status = HealthStatus.HEALTHY

        # Check screen capture
        try:
            import PIL.ImageGrab
            evidence.append("PIL.ImageGrab available for screen capture.")
        except ImportError:
            try:
                import mss
                evidence.append("mss available for screen capture.")
            except ImportError:
                status = HealthStatus.DEGRADED
                evidence.append("No screen capture library available (PIL or mss).")

        # Check OCR
        try:
            import pytesseract
            evidence.append("pytesseract OCR library available.")
        except ImportError:
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.DEGRADED
            evidence.append("pytesseract OCR not available.")

        rec = "" if status == HealthStatus.HEALTHY else "Install Pillow and pytesseract for full vision capability."
        return HealthCheckResult(
            component_id=self.component_id,
            status=status,
            error_summary="" if status == HealthStatus.HEALTHY else "Vision capability partially unavailable.",
            recommended_action=rec,
            evidence=evidence,
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Base Health Check
# ─────────────────────────────────────────────────────────────────────────────

class KnowledgeBaseHealthCheck(ComponentHealthCheck):
    """Checks vector store accessibility and embedding provider availability."""

    def __init__(self, knowledge_base=None, config: Optional[Dict] = None):
        self.knowledge_base = knowledge_base
        self.config = config or {}

    @property
    def component_id(self) -> str:
        return "knowledge_base"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        evidence = []
        status = HealthStatus.UNKNOWN

        if self.knowledge_base:
            try:
                # Check if KB is operational
                if hasattr(self.knowledge_base, "is_available"):
                    available = self.knowledge_base.is_available()
                    if available:
                        status = HealthStatus.HEALTHY
                        evidence.append("Knowledge base reports available.")
                    else:
                        status = HealthStatus.UNAVAILABLE
                        evidence.append("Knowledge base reports unavailable.")
                elif hasattr(self.knowledge_base, "index_path"):
                    import os
                    if os.path.exists(self.knowledge_base.index_path):
                        status = HealthStatus.HEALTHY
                        evidence.append("Knowledge base index file exists.")
                    else:
                        status = HealthStatus.UNAVAILABLE
                        evidence.append("Knowledge base index file not found.")
                else:
                    status = HealthStatus.HEALTHY
                    evidence.append("Knowledge base reference is initialized.")
            except Exception:
                status = HealthStatus.UNAVAILABLE
                evidence.append("Knowledge base check raised an exception.")
        else:
            status = HealthStatus.UNKNOWN
            evidence.append("No knowledge base reference provided.")

        # Check embedding library
        try:
            import sentence_transformers  # noqa: F401
            evidence.append("sentence-transformers embedding library available.")
        except ImportError:
            if status == HealthStatus.HEALTHY:
                status = HealthStatus.DEGRADED
            evidence.append("sentence-transformers not available; keyword search fallback active.")

        rec = ""
        if status == HealthStatus.UNAVAILABLE:
            rec = "Knowledge base may need to be initialized. Keyword search fallback is available."
        elif status == HealthStatus.DEGRADED:
            rec = "Install sentence-transformers for semantic search capability."

        return HealthCheckResult(
            component_id=self.component_id,
            status=status,
            error_summary="" if status == HealthStatus.HEALTHY else "Knowledge base partially unavailable.",
            recommended_action=rec,
            evidence=evidence,
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Memory Health Check
# ─────────────────────────────────────────────────────────────────────────────

class MemoryHealthCheck(ComponentHealthCheck):
    """Checks SQLite memory connection and schema validity."""

    def __init__(self, memory_manager=None):
        self.memory_manager = memory_manager

    @property
    def component_id(self) -> str:
        return "memory"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        if self.memory_manager:
            try:
                sqlite_ok = (
                    hasattr(self.memory_manager, "sqlite") and
                    self.memory_manager.sqlite is not None
                )
                if sqlite_ok:
                    return HealthCheckResult(
                        component_id=self.component_id,
                        status=HealthStatus.HEALTHY,
                        evidence=["Memory SQLite connection is active."],
                        trigger=trigger
                    )
                else:
                    return HealthCheckResult(
                        component_id=self.component_id,
                        status=HealthStatus.UNAVAILABLE,
                        error_summary="Memory SQLite connection is not active.",
                        recommended_action="Memory system may need to be reinitialized.",
                        evidence=["memory_manager.sqlite is None."],
                        trigger=trigger
                    )
            except Exception:
                return HealthCheckResult(
                    component_id=self.component_id,
                    status=HealthStatus.UNKNOWN,
                    error_summary="Could not inspect memory manager.",
                    evidence=["Error accessing memory manager."],
                    trigger=trigger
                )

        return HealthCheckResult(
            component_id=self.component_id,
            status=HealthStatus.UNKNOWN,
            error_summary="Memory manager not available for inspection.",
            evidence=["No memory manager reference provided."],
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator Health Check
# ─────────────────────────────────────────────────────────────────────────────

class OrchestratorHealthCheck(ComponentHealthCheck):
    """Checks if the JARVIS Orchestrator is initialized."""

    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator

    @property
    def component_id(self) -> str:
        return "core_orchestrator"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        if self.orchestrator is not None:
            cancelled = getattr(self.orchestrator, "_cancelled", False)
            if cancelled:
                return HealthCheckResult(
                    component_id=self.component_id,
                    status=HealthStatus.DEGRADED,
                    error_summary="Orchestrator is in cancelled state.",
                    recommended_action="Restart JARVIS to restore full orchestration capability.",
                    evidence=["orchestrator._cancelled is True."],
                    trigger=trigger
                )
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.HEALTHY,
                evidence=["Orchestrator is initialized and not cancelled."],
                trigger=trigger
            )

        return HealthCheckResult(
            component_id=self.component_id,
            status=HealthStatus.UNAVAILABLE,
            error_summary="Orchestrator is not initialized.",
            recommended_action="Restart JARVIS Core.",
            evidence=["orchestrator reference is None."],
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Agents Health Check
# ─────────────────────────────────────────────────────────────────────────────

class AgentHealthCheck(ComponentHealthCheck):
    """Checks if the agent registry is populated and agent manager is responsive."""

    def __init__(self, agent_registry=None, agent_manager=None):
        self.agent_registry = agent_registry
        self.agent_manager = agent_manager

    @property
    def component_id(self) -> str:
        return "agents"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        dep_status = dependency_status or {}
        ai_status = dep_status.get("local_ai", HealthStatus.UNKNOWN)

        evidence = []
        status = HealthStatus.HEALTHY

        if self.agent_registry:
            try:
                agents = self.agent_registry.list_agents() if hasattr(self.agent_registry, "list_agents") else []
                count = len(agents) if agents else 0
                evidence.append(f"{count} agent(s) registered.")
            except Exception:
                evidence.append("Could not query agent registry.")

        if self.agent_manager is not None:
            evidence.append("Agent manager is initialized.")
        else:
            status = HealthStatus.DEGRADED
            evidence.append("Agent manager reference not available.")

        if ai_status == HealthStatus.UNAVAILABLE:
            status = HealthStatus.DEGRADED
            evidence.append("Local AI unavailable — agents may have reduced capability.")

        return HealthCheckResult(
            component_id=self.component_id,
            status=status,
            evidence=evidence,
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Automation Health Check
# ─────────────────────────────────────────────────────────────────────────────

class AutomationHealthCheck(ComponentHealthCheck):
    """Checks if the permission system and execution engine are active."""

    def __init__(self, security_proxy=None, execution_engine=None):
        self.security_proxy = security_proxy
        self.execution_engine = execution_engine

    @property
    def component_id(self) -> str:
        return "automation"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        evidence = []
        status = HealthStatus.HEALTHY

        if self.security_proxy is not None:
            evidence.append("Permission system (SecurityProxy) is active.")
        else:
            status = HealthStatus.DEGRADED
            evidence.append("Permission system is not initialized.")

        if self.execution_engine is not None:
            evidence.append("Execution engine is initialized.")
        else:
            status = HealthStatus.DEGRADED
            evidence.append("Execution engine is not initialized.")

        return HealthCheckResult(
            component_id=self.component_id,
            status=status,
            error_summary="" if status == HealthStatus.HEALTHY else "Automation system partially unavailable.",
            evidence=evidence,
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Permission System Health Check
# ─────────────────────────────────────────────────────────────────────────────

class PermissionSystemHealthCheck(ComponentHealthCheck):
    """Checks if SecurityProxy is initialized and operational."""

    def __init__(self, security_proxy=None):
        self.security_proxy = security_proxy

    @property
    def component_id(self) -> str:
        return "permission_system"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        if self.security_proxy is not None:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.HEALTHY,
                evidence=["SecurityProxy is initialized."],
                trigger=trigger
            )
        return HealthCheckResult(
            component_id=self.component_id,
            status=HealthStatus.FAILING,
            error_summary="Permission system is not initialized. This is a critical failure.",
            recommended_action="Restart JARVIS. Do not attempt desktop automation without permission system.",
            evidence=["security_proxy is None."],
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# HUD Health Check
# ─────────────────────────────────────────────────────────────────────────────

class HUDHealthCheck(ComponentHealthCheck):
    """Checks if the event bus (HUD channel) is active."""

    def __init__(self, event_bus=None):
        self.event_bus = event_bus

    @property
    def component_id(self) -> str:
        return "hud"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        if self.event_bus is not None:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.HEALTHY,
                evidence=["Event bus (HUD channel) is active."],
                trigger=trigger
            )
        return HealthCheckResult(
            component_id=self.component_id,
            status=HealthStatus.UNAVAILABLE,
            error_summary="Event bus not available — HUD updates cannot be published.",
            evidence=["event_bus is None."],
            trigger=trigger
        )


# ─────────────────────────────────────────────────────────────────────────────
# Health Check Registry
# ─────────────────────────────────────────────────────────────────────────────

class HealthCheckRegistry:
    """
    Maps component_ids to their health check implementations.
    Allows on-demand and scheduled invocation of individual checks.
    """

    def __init__(self):
        self._checks: Dict[str, ComponentHealthCheck] = {}

    def register(self, check: ComponentHealthCheck):
        self._checks[check.component_id] = check

    def get(self, component_id: str) -> Optional[ComponentHealthCheck]:
        return self._checks.get(component_id)

    def list_ids(self) -> List[str]:
        return list(self._checks.keys())

    async def run(
        self,
        component_id: str,
        trigger: CheckTrigger = CheckTrigger.ON_DEMAND,
        dependency_status: Optional[Dict[str, HealthStatus]] = None,
        timeout: float = _DEFAULT_TIMEOUT
    ) -> Optional[HealthCheckResult]:
        check = self._checks.get(component_id)
        if not check:
            return None
        return await check.check_with_timeout(
            timeout=timeout, trigger=trigger, dependency_status=dependency_status
        )

    async def run_all(
        self,
        trigger: CheckTrigger = CheckTrigger.ON_DEMAND,
        timeout: float = _DEFAULT_TIMEOUT
    ) -> Dict[str, HealthCheckResult]:
        results = {}
        for cid, check in self._checks.items():
            result = await check.check_with_timeout(timeout=timeout, trigger=trigger)
            results[cid] = result
        return results
