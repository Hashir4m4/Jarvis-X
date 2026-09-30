"""
JARVIS Personality Registry

Manages personality profiles: loading from config, persistence, active profile
selection, and per-session preference updates.

Profiles are NEVER hard-coded across the project. All personality values are
read from here. Changes to personality only require updating the profile or config.
"""
import json
import logging
import os
from typing import Dict, Optional, Any

from .models import (
    PersonalityProfile, CommunicationStyle, FormalityLevel, VerbosityLevel,
    HumorLevel, TechnicalDepth, WarmthLevel, ProactivityLevel, VoiceStyle
)

logger = logging.getLogger("JARVIS.PersonalityRegistry")

# ─────────────────────────────────────────────────────────────────────────────
# Built-in Default Profile
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_JARVIS_PROFILE = PersonalityProfile(
    profile_id="default_jarvis",
    name="Default JARVIS",
    communication_style=CommunicationStyle.BALANCED,
    formality=FormalityLevel.PROFESSIONAL,
    verbosity=VerbosityLevel.ADAPTIVE,
    humor_level=HumorLevel.LOW,
    technical_depth=TechnicalDepth.ADAPTIVE,
    warmth_level=WarmthLevel.MODERATE,
    proactivity_level=ProactivityLevel.CONTROLLED,
    voice_style=VoiceStyle.CONVERSATIONAL,
    preferred_response_patterns=[
        "lead with action, follow with context",
        "use structured output for multi-step answers",
        "avoid excessive flattery",
        "avoid unnecessary apologies",
        "avoid fake enthusiasm",
        "avoid robotic repetition"
    ]
)

TECHNICAL_EXPERT_PROFILE = PersonalityProfile(
    profile_id="technical_expert",
    name="Technical Expert",
    communication_style=CommunicationStyle.DETAILED,
    formality=FormalityLevel.TECHNICAL,
    verbosity=VerbosityLevel.DETAILED,
    humor_level=HumorLevel.NONE,
    technical_depth=TechnicalDepth.EXPERT,
    warmth_level=WarmthLevel.MINIMAL,
    proactivity_level=ProactivityLevel.CONTROLLED,
    voice_style=VoiceStyle.NEUTRAL,
    preferred_response_patterns=[
        "use architecture terminology",
        "distinguish evidence from inference",
        "mention assumptions explicitly",
        "provide structured reasoning"
    ]
)

BUILDER_PROFILE = PersonalityProfile(
    profile_id="builder",
    name="Builder Mode",
    communication_style=CommunicationStyle.CONCISE,
    formality=FormalityLevel.CASUAL,
    verbosity=VerbosityLevel.CONCISE,
    humor_level=HumorLevel.LOW,
    technical_depth=TechnicalDepth.EXPERT,
    warmth_level=WarmthLevel.MODERATE,
    proactivity_level=ProactivityLevel.PROACTIVE,
    voice_style=VoiceStyle.CONVERSATIONAL,
    preferred_response_patterns=[
        "identify objective first",
        "propose next practical step",
        "avoid unnecessary theory",
        "be collaborative and action-oriented"
    ]
)

FOCUS_PROFILE = PersonalityProfile(
    profile_id="focus",
    name="Focus Mode",
    communication_style=CommunicationStyle.CONCISE,
    formality=FormalityLevel.PROFESSIONAL,
    verbosity=VerbosityLevel.CONCISE,
    humor_level=HumorLevel.NONE,
    technical_depth=TechnicalDepth.ADAPTIVE,
    warmth_level=WarmthLevel.MINIMAL,
    proactivity_level=ProactivityLevel.MINIMAL,
    voice_style=VoiceStyle.STATUS,
    preferred_response_patterns=[
        "suppress low-priority suggestions",
        "avoid interruptions",
        "provide concise updates only"
    ]
)

BUILT_IN_PROFILES: Dict[str, PersonalityProfile] = {
    "default_jarvis": DEFAULT_JARVIS_PROFILE,
    "technical_expert": TECHNICAL_EXPERT_PROFILE,
    "builder": BUILDER_PROFILE,
    "focus": FOCUS_PROFILE,
}


# ─────────────────────────────────────────────────────────────────────────────
# PersonalityRegistry
# ─────────────────────────────────────────────────────────────────────────────

class PersonalityRegistry:
    """
    Central store for JARVIS personality profiles.

    - Loads profiles from configs/personality_profiles.json on init.
    - Falls back to built-in defaults if config is absent or corrupt.
    - Active profile can be changed at runtime (e.g., "switch to builder mode").
    - Explicit user preferences are tracked and can be forwarded to MemoryAPI.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._profiles: Dict[str, PersonalityProfile] = dict(BUILT_IN_PROFILES)
        self._active_profile_id: str = "default_jarvis"
        self._config_path = self._resolve_config_path()
        self._user_preferences: Dict[str, Any] = {}

        self._load_from_config()
        logger.info(f"[PersonalityRegistry] Active profile: '{self._active_profile_id}'")

    def _resolve_config_path(self) -> str:
        base = self.config.get("base_dir", os.path.abspath(os.path.join(
            os.path.dirname(__file__), "../.."
        )))
        return os.path.join(base, "configs", "personality_profiles.json")

    def _load_from_config(self):
        """Loads persisted profiles and active profile ID from disk."""
        if not os.path.isfile(self._config_path):
            logger.debug(f"[PersonalityRegistry] No config at {self._config_path}, using defaults.")
            return

        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Load custom profiles
            for profile_data in data.get("profiles", []):
                p = PersonalityProfile.from_dict(profile_data)
                self._profiles[p.profile_id] = p

            # Restore active profile
            active_id = data.get("active_profile_id", "default_jarvis")
            if active_id in self._profiles:
                self._active_profile_id = active_id

            # Restore user preferences
            self._user_preferences = data.get("user_preferences", {})

        except Exception as e:
            logger.warning(f"[PersonalityRegistry] Config load failed (using defaults): {e}")

    def save_to_config(self):
        """Persists current profiles and active selection to disk."""
        try:
            os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
            data = {
                "active_profile_id": self._active_profile_id,
                "profiles": [
                    p.to_dict() for pid, p in self._profiles.items()
                    if pid not in BUILT_IN_PROFILES  # don't re-serialize built-ins
                ],
                "user_preferences": self._user_preferences
            }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"[PersonalityRegistry] Could not save config: {e}")

    # ── Profile Access ────────────────────────────────────────────

    def get_active_profile(self) -> PersonalityProfile:
        """Returns the currently active personality profile."""
        return self._profiles.get(self._active_profile_id, DEFAULT_JARVIS_PROFILE)

    def get_profile(self, profile_id: str) -> Optional[PersonalityProfile]:
        return self._profiles.get(profile_id)

    def list_profiles(self) -> Dict[str, str]:
        """Returns {profile_id: name} for all available profiles."""
        return {pid: p.name for pid, p in self._profiles.items()}

    # ── Profile Switching ─────────────────────────────────────────

    def set_active_profile(self, profile_id: str) -> bool:
        """
        Switches the active profile.
        Returns True on success, False if profile_id not found.
        """
        if profile_id in self._profiles:
            self._active_profile_id = profile_id
            self.save_to_config()
            logger.info(f"[PersonalityRegistry] Switched to profile: '{profile_id}'")
            return True
        logger.warning(f"[PersonalityRegistry] Profile '{profile_id}' not found.")
        return False

    def set_profile_by_name(self, name_fragment: str) -> bool:
        """
        Fuzzy-match profile by name (e.g., "builder" matches "Builder Mode").
        Used for natural voice/text commands like "switch to builder mode".
        """
        name_lower = name_fragment.strip().lower()
        for pid, p in self._profiles.items():
            if name_lower in p.name.lower() or name_lower in pid.lower():
                return self.set_active_profile(pid)
        return False

    def register_profile(self, profile: PersonalityProfile):
        """Registers a custom personality profile."""
        self._profiles[profile.profile_id] = profile
        self.save_to_config()
        logger.info(f"[PersonalityRegistry] Registered custom profile: '{profile.profile_id}'")

    # ── User Preference Tracking ──────────────────────────────────

    def update_preference(self, key: str, value: Any):
        """
        Records an explicit user preference (e.g., 'always give me technical explanations').

        IMPORTANT: Only explicit user statements are tracked here.
        Temporary emotional states are NEVER stored.
        Caller is responsible for persisting to MemoryAPI if permitted.
        """
        self._user_preferences[key] = value
        self.save_to_config()
        logger.info(f"[PersonalityRegistry] Preference updated: {key}={value}")

    def get_preference(self, key: str, default: Any = None) -> Any:
        return self._user_preferences.get(key, default)

    def get_all_preferences(self) -> Dict[str, Any]:
        return dict(self._user_preferences)
