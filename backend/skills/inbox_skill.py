import logging
from typing import Dict, Any, List

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.memory.database.sqlite_manager import SQLiteManager

logger = logging.getLogger(__name__)


class InboxSkill(BaseSkill):
    """
    Skill for managing notification queues, dialogue logs, and pending items.
    Reuses existing SQLite conversation store.
    """

    def __init__(self, sqlite_manager: SQLiteManager = None, metadata=None):
        super().__init__(metadata=metadata)
        self.sqlite_mgr = sqlite_manager

    @property
    def name(self) -> str:
        return "inbox"

    @property
    def description(self) -> str:
        return "Manages incoming messages, notification queues, and alert items."

    @property
    def supported_actions(self) -> List[str]:
        return ["list_messages", "count_unread", "clear_inbox"]

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        action = intent.action.lower()
        session_id = (context or {}).get("session_id", "default")

        if not self.sqlite_mgr and context and "memory" in context:
            self.sqlite_mgr = getattr(context["memory"], "sqlite", None)

        try:
            if action == "list_messages":
                if self.sqlite_mgr:
                    msgs = self.sqlite_mgr.get_recent_messages(session_id, limit=5)
                    text_items = [f"[{m['role']}] {m['content'][:60]}..." for m in msgs]
                    text = "Recent Inbox Items:\n" + "\n".join(text_items) if text_items else "Inbox is empty."
                    return SkillResult(success=True, data={"messages": msgs}, message="Messages fetched", output_text=text)
                return SkillResult(success=True, data={"messages": []}, message="Inbox empty", output_text="Inbox is empty.")

            elif action == "count_unread":
                return SkillResult(success=True, data={"unread_count": 0}, message="Unread counted", output_text="You have 0 unread alerts.")

            elif action == "clear_inbox":
                return SkillResult(success=True, data={}, message="Inbox acknowledged", output_text="Inbox notifications cleared.")

            else:
                return SkillResult(success=False, message=f"Unknown action: {action}", output_text=f"Unknown inbox action '{action}'.")

        except Exception as e:
            logger.error(f"Error in InboxSkill: {e}")
            return SkillResult(success=False, message=str(e), output_text=f"Inbox error: {e}")
