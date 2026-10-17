"""
Ambient Intelligence Mode Service.
Prompt 74 — Ambient Intelligence Mode.
"""
import logging
import time
import datetime
from typing import Dict, Any, List, Optional
import uuid

from backend.ambient.models import (
    AmbientOperatingMode, AmbientSuggestion, AmbientConfiguration
)

logger = logging.getLogger("JARVIS.AmbientIntelligence")


class AmbientIntelligenceService:
    """
    Opt-in Ambient Intelligence Mode Service.
    STRICT PRIVACY GUARANTEES:
    - Disabled by default.
    - No covert microphone monitoring.
    - No covert camera monitoring.
    - No keylogging or hidden screen captures.
    - No autonomous high-impact actions; suggestions strictly require approval.
    - Active status is always visible, and can be paused or disabled instantly.
    """

    def __init__(
        self,
        config: Optional[AmbientConfiguration] = None,
        notification_service: Optional[Any] = None,
        control_framework: Optional[Any] = None
    ):
        self.config = config or AmbientConfiguration()
        self.notif_service = notification_service
        self.control_framework = control_framework
        self.mode: AmbientOperatingMode = AmbientOperatingMode.ACTIVE if self.config.enabled else AmbientOperatingMode.DISABLED
        self._last_suggestion_time: float = 0.0
        self._last_user_activity: float = time.time()
        self._suggestions: List[AmbientSuggestion] = []

    def enable(self) -> bool:
        """Enables ambient mode via explicit user request."""
        self.config.enabled = True
        self.mode = AmbientOperatingMode.ACTIVE
        self._last_user_activity = time.time()
        logger.info("Ambient Intelligence Mode ACTIVATED by user.")
        return True

    def disable(self) -> bool:
        """Immediately disables ambient mode and revokes permissions."""
        self.config.enabled = False
        self.mode = AmbientOperatingMode.DISABLED
        logger.info("Ambient Intelligence Mode DISABLED.")
        return True

    def pause(self) -> bool:
        if self.mode == AmbientOperatingMode.ACTIVE:
            self.mode = AmbientOperatingMode.PAUSED
            logger.info("Ambient Intelligence Mode PAUSED.")
            return True
        return False

    def resume(self) -> bool:
        if self.mode == AmbientOperatingMode.PAUSED and self.config.enabled:
            self.mode = AmbientOperatingMode.ACTIVE
            self._last_user_activity = time.time()
            logger.info("Ambient Intelligence Mode RESUMED.")
            return True
        return False

    def is_within_schedule(self) -> bool:
        now_time = datetime.datetime.now().time()
        try:
            sh, sm = map(int, self.config.schedule_start.split(":"))
            eh, em = map(int, self.config.schedule_end.split(":"))
            start_t = datetime.time(sh, sm)
            end_t = datetime.time(eh, em)
            if start_t <= end_t:
                return start_t <= now_time <= end_t
            else:
                return now_time >= start_t or now_time <= end_t
        except Exception:
            return True

    def emit_suggestion(
        self,
        title: str,
        rationale: str,
        action_type: Optional[str] = None,
        action_payload: Optional[Dict[str, Any]] = None,
        confidence: float = 0.8
    ) -> Optional[AmbientSuggestion]:
        # Enforce strict active state
        if self.mode != AmbientOperatingMode.ACTIVE:
            return None

        # Check schedule
        if not self.is_within_schedule():
            return None

        # Enforce cooldown
        now = time.time()
        if now - self._last_suggestion_time < self.config.cooldown_seconds:
            return None

        # Check session timeout
        if now - self._last_user_activity > self.config.session_timeout_seconds:
            self.mode = AmbientOperatingMode.STANDBY
            logger.info("Ambient Intelligence Mode entered STANDBY due to session inactivity.")
            return None

        sugg = AmbientSuggestion(
            suggestion_id=f"sug_{uuid.uuid4().hex[:8]}",
            title=title,
            rationale=rationale,
            action_type=action_type,
            action_payload=action_payload or {},
            confidence=confidence,
            requires_approval=True
        )
        self._suggestions.append(sugg)
        self._last_suggestion_time = now

        # Optionally publish notification
        if self.notif_service and hasattr(self.notif_service, "post_notification"):
            self.notif_service.post_notification(
                title=f"Ambient Suggestion: {title}",
                message=rationale,
                priority="INFO",
                category="background_update",
                action_type=action_type,
                action_payload=action_payload
            )

        return sugg

    def get_recent_suggestions(self, limit: int = 10) -> List[AmbientSuggestion]:
        return list(self._suggestions)[-limit:]
