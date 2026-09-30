import json
import logging
import os
from typing import Dict, Any, List, Optional

from .models import (
    MonitorDefinition, ConditionRule, Reminder,
    NotificationMode, EventPriority, RecurrencePattern,
    EventType, MonitorStatus
)

logger = logging.getLogger("JARVIS.ProactiveStorage")


class ProactiveStorage:
    """
    Manages persistence of active monitors, rules, reminders, and user notification modes.
    Saves to configs/proactive_state.json safely.
    """

    def __init__(self, storage_path: Optional[str] = None):
        if storage_path:
            self.storage_path = storage_path
        else:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../configs"))
            os.makedirs(base_dir, exist_ok=True)
            self.storage_path = os.path.join(base_dir, "proactive_state.json")

    def load_state(self) -> Dict[str, Any]:
        """Loads persisted state from disk or returns default configuration."""
        if not os.path.exists(self.storage_path):
            return {
                "notification_mode": "NORMAL",
                "monitors": {},
                "rules": [],
                "reminders": []
            }

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data
        except Exception as e:
            logger.error(f"[PROACTIVE_STORAGE] Error loading state from '{self.storage_path}': {e}")
            return {
                "notification_mode": "NORMAL",
                "monitors": {},
                "rules": [],
                "reminders": []
            }

    def save_state(
        self,
        notification_mode: NotificationMode,
        monitors: Dict[str, MonitorDefinition],
        rules: List[ConditionRule],
        reminders: List[Reminder]
    ) -> bool:
        """Saves current proactive settings to disk."""
        def _serialize_monitor(m: Any) -> Dict[str, Any]:
            if hasattr(m, "to_dict"):
                return m.to_dict()
            elif hasattr(m, "definition") and hasattr(m.definition, "to_dict"):
                return m.definition.to_dict()
            return {}

        data = {
            "notification_mode": notification_mode.value,
            "monitors": {mid: _serialize_monitor(m) for mid, m in monitors.items()},
            "rules": [r.to_dict() for r in rules],
            "reminders": [rem.to_dict() for rem in reminders]
        }

        try:
            temp_path = f"{self.storage_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, self.storage_path)
            logger.debug(f"[PROACTIVE_STORAGE] Successfully saved state to '{self.storage_path}'.")
            return True
        except Exception as e:
            logger.error(f"[PROACTIVE_STORAGE] Error saving state to '{self.storage_path}': {e}")
            return False
