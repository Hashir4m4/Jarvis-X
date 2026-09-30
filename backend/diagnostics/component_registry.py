"""
JARVIS Component Health Registry

Central store for all registered component health records.

Each component declares:
- Its identity (id, name, category, criticality)
- Its dependencies (other component_ids it requires)
- Its recovery capabilities (action_ids it supports)

The registry tracks live health status and failure counters.
It is the authoritative source for "what does JARVIS consist of?"
"""
import logging
import time
from typing import Dict, List, Optional, Any

from .models import (
    HealthRecord, HealthStatus, ComponentCategory, ComponentCriticality
)

logger = logging.getLogger("JARVIS.ComponentRegistry")


# ─────────────────────────────────────────────────────────────────────────────
# Built-in Component Definitions
# ─────────────────────────────────────────────────────────────────────────────

def _build_default_components() -> List[HealthRecord]:
    """Defines all built-in JARVIS components with their dependencies and recovery capabilities."""
    return [
        HealthRecord(
            component_id="core_orchestrator",
            name="Core Orchestrator",
            category=ComponentCategory.CORE,
            criticality=ComponentCriticality.CRITICAL,
            dependencies=[],
            recovery_capabilities=[]
        ),
        HealthRecord(
            component_id="event_bus",
            name="Event Bus",
            category=ComponentCategory.CORE,
            criticality=ComponentCriticality.CRITICAL,
            dependencies=[],
            recovery_capabilities=[]
        ),
        HealthRecord(
            component_id="memory",
            name="Memory System",
            category=ComponentCategory.STORAGE,
            criticality=ComponentCriticality.CRITICAL,
            dependencies=[],
            recovery_capabilities=["reinitialize_memory"]
        ),
        HealthRecord(
            component_id="network",
            name="Network Connectivity",
            category=ComponentCategory.NETWORK,
            criticality=ComponentCriticality.MEDIUM,
            dependencies=[],
            recovery_capabilities=[]
        ),
        HealthRecord(
            component_id="local_ai",
            name="Local AI (Ollama)",
            category=ComponentCategory.AI_MODEL,
            criticality=ComponentCriticality.HIGH,
            dependencies=["network"],
            recovery_capabilities=[
                "retry_local_ai_connection",
                "restart_local_ai_server"
            ]
        ),
        HealthRecord(
            component_id="cloud_ai",
            name="Cloud AI Providers",
            category=ComponentCategory.AI_MODEL,
            criticality=ComponentCriticality.MEDIUM,
            dependencies=["network"],
            recovery_capabilities=["refresh_cloud_provider_config"]
        ),
        HealthRecord(
            component_id="voice_input",
            name="Voice Input (STT)",
            category=ComponentCategory.VOICE,
            criticality=ComponentCriticality.MEDIUM,
            dependencies=["audio_device"],
            recovery_capabilities=["restart_voice_stt"]
        ),
        HealthRecord(
            component_id="audio_device",
            name="Audio Device / Microphone",
            category=ComponentCategory.VOICE,
            criticality=ComponentCriticality.MEDIUM,
            dependencies=[],
            recovery_capabilities=[]
        ),
        HealthRecord(
            component_id="wake_word",
            name="Wake Word Engine",
            category=ComponentCategory.VOICE,
            criticality=ComponentCriticality.LOW,
            dependencies=["audio_device"],
            recovery_capabilities=["restart_wake_word"]
        ),
        HealthRecord(
            component_id="voice_output",
            name="Voice Output (TTS)",
            category=ComponentCategory.VOICE,
            criticality=ComponentCriticality.MEDIUM,
            dependencies=[],
            recovery_capabilities=["restart_voice_tts"]
        ),
        HealthRecord(
            component_id="vision",
            name="Screen Vision & OCR",
            category=ComponentCategory.VISION,
            criticality=ComponentCriticality.LOW,
            dependencies=[],
            recovery_capabilities=[]
        ),
        HealthRecord(
            component_id="browser",
            name="Browser Intelligence",
            category=ComponentCategory.AUTOMATION,
            criticality=ComponentCriticality.LOW,
            dependencies=["network"],
            recovery_capabilities=[]
        ),
        HealthRecord(
            component_id="knowledge_base",
            name="Personal Knowledge Base",
            category=ComponentCategory.KNOWLEDGE,
            criticality=ComponentCriticality.MEDIUM,
            dependencies=[],
            recovery_capabilities=[
                "reinitialize_knowledge_base_index",
                "fallback_to_keyword_search"
            ]
        ),
        HealthRecord(
            component_id="agents",
            name="Multi-Agent System",
            category=ComponentCategory.AGENT,
            criticality=ComponentCriticality.MEDIUM,
            dependencies=["local_ai"],
            recovery_capabilities=["reset_agent_registry"]
        ),
        HealthRecord(
            component_id="automation",
            name="Desktop Automation",
            category=ComponentCategory.AUTOMATION,
            criticality=ComponentCriticality.MEDIUM,
            dependencies=[],
            recovery_capabilities=[]
        ),
        HealthRecord(
            component_id="hud",
            name="HUD Interface",
            category=ComponentCategory.INTERFACE,
            criticality=ComponentCriticality.LOW,
            dependencies=["event_bus"],
            recovery_capabilities=[]
        ),
        HealthRecord(
            component_id="permission_system",
            name="Permission & Security System",
            category=ComponentCategory.CORE,
            criticality=ComponentCriticality.CRITICAL,
            dependencies=[],
            recovery_capabilities=[]
        ),
    ]


# ─────────────────────────────────────────────────────────────────────────────
# ComponentRegistry
# ─────────────────────────────────────────────────────────────────────────────

class ComponentRegistry:
    """
    Central store for all JARVIS component health records.

    Components are registered once at startup. Health status is updated
    in-place as health checks run. The registry is the single source of
    truth for what JARVIS is composed of and what state each part is in.
    """

    def __init__(self):
        self._records: Dict[str, HealthRecord] = {}
        self._register_defaults()

    def _register_defaults(self):
        for record in _build_default_components():
            self._records[record.component_id] = record
        logger.info(f"[ComponentRegistry] Registered {len(self._records)} built-in components.")

    # ── Registration ──────────────────────────────────────────────

    def register(self, record: HealthRecord):
        """Registers a component. Overwrites if already registered."""
        self._records[record.component_id] = record
        logger.debug(f"[ComponentRegistry] Registered: '{record.component_id}' ({record.category.value})")

    def unregister(self, component_id: str) -> bool:
        if component_id in self._records:
            del self._records[component_id]
            return True
        return False

    # ── Query ─────────────────────────────────────────────────────

    def get(self, component_id: str) -> Optional[HealthRecord]:
        return self._records.get(component_id)

    def exists(self, component_id: str) -> bool:
        return component_id in self._records

    def get_all(self) -> Dict[str, HealthRecord]:
        return dict(self._records)

    def list_ids(self) -> List[str]:
        return list(self._records.keys())

    def get_by_category(self, category: ComponentCategory) -> List[HealthRecord]:
        return [r for r in self._records.values() if r.category == category]

    def get_by_criticality(self, criticality: ComponentCriticality) -> List[HealthRecord]:
        return [r for r in self._records.values() if r.criticality == criticality]

    def get_critical(self) -> List[HealthRecord]:
        return self.get_by_criticality(ComponentCriticality.CRITICAL)

    def get_unhealthy(self) -> List[HealthRecord]:
        """Returns all components that are not HEALTHY, DISABLED, or UNKNOWN."""
        return [
            r for r in self._records.values()
            if r.health_status not in (
                HealthStatus.HEALTHY, HealthStatus.DISABLED, HealthStatus.UNKNOWN
            )
        ]

    def get_dependencies(self, component_id: str) -> List[HealthRecord]:
        """Returns HealthRecord objects for all declared dependencies."""
        record = self.get(component_id)
        if not record:
            return []
        return [self._records[dep] for dep in record.dependencies if dep in self._records]

    def get_dependency_chain(self, component_id: str, visited: Optional[set] = None) -> List[str]:
        """Returns full transitive dependency chain for a component."""
        if visited is None:
            visited = set()
        if component_id in visited:
            return []
        visited.add(component_id)
        record = self.get(component_id)
        if not record:
            return []
        chain = list(record.dependencies)
        for dep_id in record.dependencies:
            chain.extend(self.get_dependency_chain(dep_id, visited))
        return list(dict.fromkeys(chain))  # Preserve order, deduplicate

    # ── Status Updates ────────────────────────────────────────────

    def update_status(self, component_id: str, status: HealthStatus, error: str = ""):
        """Updates the health status of a registered component."""
        record = self.get(component_id)
        if not record:
            logger.warning(f"[ComponentRegistry] Unknown component: '{component_id}'")
            return

        old_status = record.health_status
        record.health_status = status
        record.last_check = time.time()

        if status == HealthStatus.HEALTHY:
            record.mark_healthy()
        elif status in (HealthStatus.UNAVAILABLE, HealthStatus.FAILING):
            record.mark_failed(error)
        else:
            record.health_status = status
            if error:
                record.last_error = error[:200]

        if old_status != status:
            logger.info(
                f"[ComponentRegistry] '{component_id}' status: "
                f"{old_status.value} → {status.value}"
            )

    def record_failure(self, component_id: str, error: str = ""):
        """Increments failure counter and adjusts status accordingly."""
        record = self.get(component_id)
        if record:
            record.mark_failed(error)

    def record_healthy(self, component_id: str):
        record = self.get(component_id)
        if record:
            record.mark_healthy()

    # ── Overview ──────────────────────────────────────────────────

    def get_all_statuses(self) -> Dict[str, str]:
        """Returns {component_id: status_value} for all components."""
        return {cid: r.health_status.value for cid, r in self._records.items()}

    def get_overall_status(self) -> HealthStatus:
        """
        Derives overall system health:
        - Any CRITICAL component FAILING/UNAVAILABLE → FAILING
        - Any HIGH component unhealthy → DEGRADED
        - All healthy → HEALTHY
        """
        for record in self._records.values():
            if not record.enabled:
                continue
            if record.criticality == ComponentCriticality.CRITICAL and record.health_status in (
                HealthStatus.FAILING, HealthStatus.UNAVAILABLE
            ):
                return HealthStatus.FAILING

        for record in self._records.values():
            if not record.enabled:
                continue
            if record.health_status in (
                HealthStatus.DEGRADED, HealthStatus.UNAVAILABLE, HealthStatus.FAILING
            ):
                return HealthStatus.DEGRADED

        statuses = {r.health_status for r in self._records.values() if r.enabled}
        if HealthStatus.UNKNOWN in statuses and len(statuses) == 1:
            return HealthStatus.UNKNOWN
        if all(s in (HealthStatus.HEALTHY, HealthStatus.DISABLED, HealthStatus.UNKNOWN)
               for s in statuses):
            return HealthStatus.HEALTHY

        return HealthStatus.DEGRADED

    def snapshot(self) -> Dict[str, Any]:
        """Non-sensitive diagnostic summary."""
        return {
            "total": len(self._records),
            "overall": self.get_overall_status().value,
            "statuses": self.get_all_statuses()
        }
