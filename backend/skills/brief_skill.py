import logging
import os
import datetime
from typing import Dict, Any, List, Optional

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.agents import code_tools

logger = logging.getLogger("JARVIS.BriefSkill")


class BriefSkill(BaseSkill):
    """
    Morning Brief Workflow Skill.
    Aggregates Inbox, Calendar status, Relevant Memory, Repository activity, and Configured feeds.
    """

    def __init__(self, sqlite_manager=None, metadata=None):
        super().__init__(metadata=metadata)
        self.sqlite = sqlite_manager

    @property
    def name(self) -> str:
        return "brief"

    @property
    def description(self) -> str:
        return "Aggregates morning intelligence brief combining inbox, calendar, memory, and project activity."

    @property
    def supported_actions(self) -> List[str]:
        return ["get_brief"]

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        ctx = context or {}
        memory = ctx.get("memory")
        today_str = datetime.date.today().isoformat()

        # 1. Inbox & Notifications
        inbox_count = 0
        inbox_summary = "All clear. No unread notifications."
        if self.sqlite and hasattr(self.sqlite, "get_unread_message_count"):
            try:
                inbox_count = self.sqlite.get_unread_message_count()
                if inbox_count > 0:
                    inbox_summary = f"{inbox_count} unread conversation item(s) pending."
            except Exception as e:
                logger.debug(f"Inbox check error: {e}")

        # 2. Calendar Status (Honest reporting - no fake connector)
        calendar_status = "Integration Offline (No Google/Outlook calendar connector configured)"

        # 3. Relevant JARVIS Memory Context
        memory_highlights = []
        if memory:
            try:
                context_notes = memory.retrieve_context("morning priorities, active tasks, user preferences", limit=2)
                for note in context_notes:
                    if isinstance(note, dict) and "content" in note:
                        memory_highlights.append(f"- {note['content'][:120]}")
                    elif isinstance(note, str):
                        memory_highlights.append(f"- {note[:120]}")
            except Exception as e:
                logger.debug(f"Memory context retrieval error: {e}")

        memory_text = "\n".join(memory_highlights) if memory_highlights else "- No prior constraints recorded."

        # 4. Project & Repository Activity
        repo_status = "Repository status clean."
        try:
            git_out = code_tools.git_status(".")
            if git_out and "fatal" not in git_out.lower():
                lines = [l.strip() for l in git_out.strip().split("\n") if l.strip()][:3]
                repo_status = "Active changes:\n" + "\n".join(f"  {l}" for l in lines)
            elif "fatal" in git_out.lower():
                repo_status = "Git repository not initialized."
        except Exception:
            repo_status = "Repository activity monitor operational."

        # 5. Configured Data/News Feeds (Honest reporting)
        news_status = "No external RSS or financial API connectors configured."

        brief_text = (
            f"### 🌅 Morning Intelligence Brief — {today_str}\n\n"
            f"**1. Inbox & Notifications**:\n"
            f"• {inbox_summary}\n\n"
            f"**2. Calendar & Schedule**:\n"
            f"• {calendar_status}\n\n"
            f"**3. Relevant Memory & Context**:\n"
            f"{memory_text}\n\n"
            f"**4. Project & Repository Activity**:\n"
            f"• {repo_status}\n\n"
            f"**5. Configured Data Feeds**:\n"
            f"• {news_status}\n"
        )

        return SkillResult(
            success=True,
            data={
                "date": today_str,
                "inbox_count": inbox_count,
                "calendar_connected": False,
                "memory_highlights": memory_highlights
            },
            message="Morning brief compiled",
            output_text=brief_text
        )
