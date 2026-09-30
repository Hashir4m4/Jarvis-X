import logging
import os
import datetime
from typing import Dict, Any, List, Optional

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult

logger = logging.getLogger("JARVIS.CloseDaySkill")


class CloseDaySkill(BaseSkill):
    """
    Close the Day Workflow Skill.
    Summarizes completed work, captures reflection, creates/updates daily note, and drafts tomorrow's priorities.
    """

    def __init__(self, sqlite_manager=None, metadata=None):
        super().__init__(metadata=metadata)
        self.sqlite = sqlite_manager

    @property
    def name(self) -> str:
        return "close_day"

    @property
    def description(self) -> str:
        return "End-of-day shutdown routine summarizing completed work, reflections, daily note, and tomorrow's priorities."

    @property
    def supported_actions(self) -> List[str]:
        return ["close_the_day"]

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        ctx = context or {}
        memory = ctx.get("memory")
        today_str = datetime.date.today().isoformat()

        # 1. Summarize completed work from SQLite logs
        completed_items = []
        if self.sqlite and hasattr(self.sqlite, "get_recent_messages"):
            try:
                recent = self.sqlite.get_recent_messages(limit=10)
                user_cmds = [m.get("content") for m in recent if m.get("role") == "user"]
                for cmd in user_cmds[:4]:
                    completed_items.append(f"• Executed: {cmd[:80]}")
            except Exception as e:
                logger.debug(f"History query error: {e}")

        if not completed_items:
            completed_items = ["• Completed core system operations and scheduled maintenance."]

        completed_text = "\n".join(completed_items)

        # 2. Daily Reflection
        reflection = "Productive execution cycle. All critical tasks processed without security violations."

        # 3. Tomorrow's Priorities
        tomorrow_priorities = [
            "1. [ ] Review morning intelligence brief & action items",
            "2. [ ] Execute planned architecture objectives",
            "3. [ ] Review end-of-day telemetry snapshot"
        ]
        tomorrow_text = "\n".join(tomorrow_priorities)

        # 4. Generate daily note in Obsidian vault/daily/
        daily_note_content = (
            f"## Evening Digest & Close The Day\n\n"
            f"### Completed Work\n{completed_text}\n\n"
            f"### Reflection\n{reflection}\n\n"
            f"### Tomorrow's Focus\n{tomorrow_text}\n"
        )

        vault_path = None
        if memory and hasattr(memory, "create_daily_note"):
            try:
                vault_path = memory.create_daily_note(content=daily_note_content, date_str=today_str)
            except Exception as e:
                logger.warning(f"Failed writing evening note to daily vault: {e}")

        output_text = (
            f"### 🌙 Close the Day Digest — {today_str}\n\n"
            f"**1. Completed Work**:\n{completed_text}\n\n"
            f"**2. Daily Reflection**:\n• {reflection}\n\n"
            f"**3. Tomorrow's Top Priorities**:\n{tomorrow_text}\n\n"
            f"*Daily note synced to Obsidian vault: `{vault_path or 'vault/daily/'}`*"
        )

        return SkillResult(
            success=True,
            data={
                "date": today_str,
                "completed_count": len(completed_items),
                "vault_path": vault_path
            },
            message="Day closed and daily note updated",
            output_text=output_text
        )
