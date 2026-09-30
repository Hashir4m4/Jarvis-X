import logging
from typing import Dict, Any, List, Optional
from backend.core.models import SkillStatus, SkillCategory
from backend.core.capability_detector import CapabilityState, AIMode

logger = logging.getLogger("JARVIS.CapabilityRegistry")


class CapabilityRegistry:
    """
    Manages capability discovery and dependency enforcement for JARVIS Skills.
    Distinguishes between registered, available, unavailable, and failed states.
    """

    def __init__(self):
        self._skills_metadata: Dict[str, Any] = {}
        self._skill_status: Dict[str, SkillStatus] = {}
        self._skill_reasons: Dict[str, str] = {}

    def register_skill_metadata(self, name: str, category: SkillCategory, dependencies: List[str], supported_modes: List[AIMode]):
        """Registers a skill's fundamental capabilities and sets state to REGISTERED."""
        lower_name = name.lower()
        self._skills_metadata[lower_name] = {
            "name": lower_name,
            "category": category,
            "dependencies": dependencies,
            "supported_modes": supported_modes,
        }
        self._set_status(lower_name, SkillStatus.REGISTERED, "Registered successfully.")

    def _set_status(self, name: str, status: SkillStatus, reason: str = ""):
        self._skill_status[name] = status
        self._skill_reasons[name] = reason

    def get_skill_status(self, name: str) -> SkillStatus:
        """Returns current status of the skill."""
        return self._skill_status.get(name.lower(), SkillStatus.UNAVAILABLE)

    def get_skill_reason(self, name: str) -> str:
        """Returns the reason for current status."""
        return self._skill_reasons.get(name.lower(), "Skill not registered.")

    def evaluate_availability(self, current_state: CapabilityState):
        """
        Re-evaluates the availability of all registered skills against the current CapabilityState.
        Marks skills as AVAILABLE or UNAVAILABLE based on dependencies.
        """
        for name, meta in self._skills_metadata.items():
            # Only evaluate skills that haven't failed or been explicitly disabled
            current_status = self._skill_status.get(name)
            if current_status in (SkillStatus.FAILED, SkillStatus.DISABLED):
                continue

            available, reason = self._check_dependencies(meta, current_state)
            if available:
                self._set_status(name, SkillStatus.AVAILABLE, "All dependencies met.")
            else:
                self._set_status(name, SkillStatus.UNAVAILABLE, f"Missing dependency: {reason}")

    def _check_dependencies(self, meta: Dict[str, Any], state: CapabilityState) -> tuple[bool, str]:
        """Checks if a skill's requirements are met by the current CapabilityState."""
        deps = meta.get("dependencies", [])
        
        if "internet" in deps and not state.internet_available:
            return False, "internet"
            
        if "local_llm" in deps and not state.local_llm_available:
            return False, "local_llm"
            
        if "cloud_provider" in deps and not state.cloud_available:
            return False, "cloud_provider"
            
        if "camera" in deps and not state.local_vision_available:
            return False, "camera"
            
        if "stt" in deps and not state.local_stt_available:
            return False, "stt"
            
        # Modes check
        supported_modes = meta.get("supported_modes", [])
        if supported_modes and state.active_mode not in supported_modes:
            return False, f"current AI mode {state.active_mode.value} not in supported modes"
            
        return True, ""

    def get_all_capabilities(self) -> List[Dict[str, Any]]:
        """Returns a snapshot of all capabilities for discovery."""
        result = []
        for name, meta in self._skills_metadata.items():
            result.append({
                "name": name,
                "category": meta["category"].value if hasattr(meta["category"], "value") else str(meta["category"]),
                "dependencies": meta["dependencies"],
                "supported_modes": [m.value for m in meta["supported_modes"]],
                "status": self._skill_status[name].value,
                "reason": self._skill_reasons[name]
            })
        return result

    def mark_failed(self, name: str, reason: str):
        """Marks a skill as failed, preventing its selection until reset."""
        self._set_status(name.lower(), SkillStatus.FAILED, reason)

    def mark_disabled(self, name: str, reason: str):
        """Administratively disables a skill."""
        self._set_status(name.lower(), SkillStatus.DISABLED, reason)
