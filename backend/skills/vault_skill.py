import logging
from typing import Dict, Any, List

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.memory.database.sqlite_manager import SQLiteManager

logger = logging.getLogger(__name__)


class VaultSkill(BaseSkill):
    """
    Skill for securely managing user preferences, persistent variables, and profile secrets.
    Reuses existing SQLite database storage.
    """

    def __init__(self, sqlite_manager: SQLiteManager = None, metadata=None):
        super().__init__(metadata=metadata)
        self.sqlite_mgr = sqlite_manager

    @property
    def name(self) -> str:
        return "vault"

    @property
    def description(self) -> str:
        return "Securely stores and retrieves persistent user preferences, profile variables, and memories."

    @property
    def supported_actions(self) -> List[str]:
        return ["get_secret", "set_secret", "list_keys"]

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        action = intent.action.lower()
        params = intent.parameters or {}

        if not self.sqlite_mgr:
            # Check if context provides sqlite manager or memory manager
            if context and "memory" in context and hasattr(context["memory"], "sqlite"):
                self.sqlite_mgr = context["memory"].sqlite

        if not self.sqlite_mgr:
            return SkillResult(success=False, message="Database storage not available", output_text="Vault database not initialized.")

        try:
            if action == "get_secret":
                key = params.get("key", "")
                if not key:
                    return SkillResult(success=False, message="Missing required input: key", output_text="Please specify a key to look up.")
                val = self.sqlite_mgr.get_user_pref(key)
                if val is not None:
                    return SkillResult(success=True, data={"key": key, "value": val}, message="Key retrieved", output_text=f"Vault [{key}]: {val}")
                return SkillResult(success=False, message="Key not found", output_text=f"No entry found in vault for key '{key}'.")

            elif action == "set_secret":
                key = params.get("key", "")
                val = params.get("value", "")
                if not key or val == "":
                    return SkillResult(success=False, message="Missing required inputs: key, value", output_text="Please specify both key and value.")
                self.sqlite_mgr.set_user_pref(key, str(val))
                return SkillResult(success=True, data={"key": key}, message="Key saved", output_text=f"Saved '{key}' to vault.")

            elif action == "list_keys":
                # Query user_profile keys
                cursor = self.sqlite_mgr.conn.cursor()
                cursor.execute("SELECT key FROM user_profile")
                keys = [r[0] for r in cursor.fetchall()]
                return SkillResult(success=True, data={"keys": keys}, message="Keys listed", output_text=f"Stored vault keys: {', '.join(keys) if keys else 'None'}.")

            else:
                return SkillResult(success=False, message=f"Unknown action: {action}", output_text=f"Unknown vault action '{action}'.")

        except Exception as e:
            logger.error(f"Error in VaultSkill: {e}")
            return SkillResult(success=False, message=str(e), output_text=f"Vault storage error: {e}")
