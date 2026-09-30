import re
import logging
from typing import Optional, Dict, Any, List, Tuple

from .base_router import BaseIntentRouter
from backend.core.models import UserInput, Intent, IntentType

logger = logging.getLogger("JARVIS.IntentRouter")


class IntentRouter(BaseIntentRouter):
    """
    Semantic and Pattern-based Intent Router for JARVIS OS.
    Understands daily operating workflows (Morning Brief, Plan Today, Metrics Pull, Close the Day),
    Multi-Agent coding pipelines, and system hardware queries.
    """

    def __init__(self, skill_registry=None):
        self.skill_registry = skill_registry

        # Declarative rule definitions: (Regex Pattern, Skill Name, Action, Param Extractor, Priority/Confidence)
        self._rules: List[Tuple[str, str, str, Any, float]] = [
            # 1. OS Daily Workflows (Morning Brief, Plan Today, Metrics Pull, Close the Day)
            (r"\b(?:morning brief|give me (?:my )?morning brief|what is (?:my )?morning brief|daily brief|morning intelligence)\b", "brief", "get_brief", {}, 0.99),
            (r"\b(?:plan today|plan today'?s priorities|what do i need to do today|today'?s plan|plan my day|plan today'?s objectives)\b", "plan", "plan_today", lambda m: {"task": "Daily Priorities"}, 0.99),
            (r"\b(?:metrics pull|pull metrics(?: report)?|save metrics report|record telemetry)\b", "metrics", "pull_metrics_report", {}, 0.99),
            (r"\b(?:close the day|close day|end of day summary|evening digest|wrap up today|close out today)\b", "close_day", "close_the_day", {}, 0.99),

            # 2. System Status & Hardware (Strict priority over coding)
            (r"\b(?:what is my cpu usage|cpu usage|what is my ram usage|cpu load|cpu utilization|current cpu)\b", "metrics", "get_cpu_load", {}, 0.99),
            (r"\b(?:summarize (?:my )?metrics|my metrics|system metrics|performance metrics|metrics summary)\b", "metrics", "get_summary", {}, 0.99),
            (r"\b(hardware telemetry|telemetry snapshot|metrics|telemetry)\b", "metrics", "get_telemetry", {}, 0.95),
            (r"\b(memory stats|ram stats|swap stats|ram utilization)\b", "metrics", "get_memory_stats", {}, 0.95),

            (r"\b(?:show (?:my )?system status|system status|status of system|system info|sys info|diagnostics|system specs|pc info)\b", "system", "get_system_info", {}, 0.99),
            (r"\b(battery|battery level|battery percentage|power status)\b", "system", "get_battery", {}, 0.95),
            (r"\b(wifi status|check wifi|network status|is wifi connected)\b", "system", "get_wifi_status", {}, 0.95),
            (r"\b(get volume|what is the volume|check volume|current volume)\b", "system", "get_volume", {}, 0.95),
            (r"\bset volume to (\d+)\b", "system", "set_volume", lambda m: {"level": int(m.group(1))}, 0.98),
            (r"\bvolume (\d+)\b", "system", "set_volume", lambda m: {"level": int(m.group(1))}, 0.95),
            (r"\b(mute|mute audio|mute volume|silence)\b", "system", "mute_volume", {}, 0.95),
            (r"\b(unmute|unmute audio|unmute volume)\b", "system", "unmute_volume", {}, 0.95),
            (r"\b(get brightness|current brightness|check brightness)\b", "system", "get_brightness", {}, 0.95),
            (r"\bset brightness to (\d+)\b", "system", "set_brightness", lambda m: {"level": int(m.group(1))}, 0.98),
            (r"\bbrightness (\d+)\b", "system", "set_brightness", lambda m: {"level": int(m.group(1))}, 0.95),
            (r"\b(list processes|running processes|top processes|task manager)\b", "system", "list_processes", {}, 0.95),
            (r"\bkill process (\d+)\b", "system", "kill_process", lambda m: {"pid": int(m.group(1))}, 0.98),

            # 3. Multi-Agent Coding Pipeline (Planner -> Coder -> Reviewer -> Executor)
            (r"\b(?:build (?:a |an )?(?:python )?script (?:that |to )?(.+))\b", "coding", "run_task", lambda m: {"task": m.group(0).strip()}, 0.98),
            (r"\b(?:write (?:a |an )?(?:python |node |bash |script |program |function |app )+(?:that |to |for )?(.+))\b", "coding", "run_task", lambda m: {"task": m.group(0).strip()}, 0.97),
            (r"\b(?:create (?:a |an )?(?:python |script |program |function )+(?:that |to |for )?(.+))\b", "coding", "run_task", lambda m: {"task": m.group(0).strip()}, 0.97),
            (r"\b(?:code (?:a |an )?(.+))\b", "coding", "run_task", lambda m: {"task": m.group(0).strip()}, 0.96),
            (r"\b(?:review (?:this )?code|audit (?:this )?code)\b", "coding", "review_code", {}, 0.95),

            # 4. General Planning & Objectives
            (r"^(?:create (?:a )?plan (?:to|for)|plan) (.+)$", "plan", "create_plan", lambda m: {"task": m.group(1).strip()}, 0.95),
            (r"\b(?:explain (?:the )?plan|breakdown plan)\b", "plan", "explain_plan", lambda m: {"task": "active_plan"}, 0.92),

            # 5. Vault & Long-Term Memory
            (r"\bremember that (.+)$", "memory", "remember", {}, 0.98),
            (r"\b(?:remember|save memory):?\s*(.+)$", "memory", "remember", {}, 0.95),
            (r"\b(?:forget that|forget):?\s*(.+)$", "memory", "forget", {}, 0.95),
            (r"\b(?:what do you know about|what do you remember about|what was) (.+)$", "memory", "query", {}, 0.95),
            (r"\b(?:get secret|vault get|lookup key) ([a-zA-Z0-9_\-]+)\b", "vault", "get_secret", lambda m: {"key": m.group(1)}, 0.95),
            (r"\b(?:set secret|vault set|save to vault) ([a-zA-Z0-9_\-]+) (.+)", "vault", "set_secret", lambda m: {"key": m.group(1), "value": m.group(2).strip()}, 0.98),
            (r"\b(list vault keys|vault keys|list secrets)\b", "vault", "list_keys", {}, 0.95),

            # 6. Trends & Change Analytics
            (r"\b(?:what changed today|what has changed today|what is new today|recent changes|what happened today)\b", "trends", "get_query_trends", {}, 0.98),
            (r"\b(query trends|interaction trends|usage trends)\b", "trends", "get_query_trends", {}, 0.95),
            (r"\b(system trends|performance trends|hardware trends)\b", "trends", "get_system_trends", {}, 0.95),

            # 7. Inbox & Notifications
            (r"\b(check inbox|list inbox|inbox messages|recent notifications)\b", "inbox", "list_messages", {}, 0.95),
            (r"\b(unread notifications|unread messages|count unread)\b", "inbox", "count_unread", {}, 0.95),
            (r"\b(clear inbox|acknowledge alerts)\b", "inbox", "clear_inbox", {}, 0.95),

            # 8. Desktop Automation & Safe Computer Control
            (r"^(?:stop|abort|cancel that|abort automation|emergency stop)$", "desktop", "emergency_stop", {}, 1.0),
            (r"\b(?:open (?:my )?(?:browser|web browser))\b", "desktop", "open_application", {"app_name": "browser"}, 0.99),
            (r"\b(?:take a screenshot|screen capture)\b", "desktop", "screenshot", {}, 0.98),

            # Browser Intents
            (r"\b(?:search (?:for )?|look up )(.+)\b", "browser", "search", {}, 0.90),
            (r"\b(?:read|summarize) (?:this )?(?:webpage|page|website)\b", "browser", "read_page", {}, 0.95),
            (r"\b(?:open|go to) (?:the )?(?:website|url)\b", "browser", "open_url", {}, 0.90),

            (r"\b(?:open (?:my )?jarvis project in vs ?code)\b", "desktop", "open_application", {"app_name": "code", "parameters": ["."]}, 0.99),
            (r"\b(?:open (?:my )?downloads(?: folder)?)\b", "desktop", "open_folder", lambda m: {"folder_path": os.path.expanduser("~/Downloads")}, 0.99),
            (r"\b(?:open (?:the |my )?folder (?:called |named )?(.+))\b", "desktop", "open_folder", lambda m: {"folder_path": m.group(1).strip()}, 0.97),
            (r"\b(?:create (?:a )?folder (?:called |named )?(.+))\b", "desktop", "create_folder", lambda m: {"folder_path": m.group(1).strip()}, 0.98),
            (r"\b(?:organize (?:the )?files in (?:my )?downloads(?: folder)?)\b", "desktop", "organize_files", lambda m: {"folder_path": os.path.expanduser("~/Downloads")}, 0.99),
            (r"\b(?:organize (?:the )?files in (.+))\b", "desktop", "organize_files", lambda m: {"folder_path": m.group(1).strip()}, 0.97),
            (r"\b(?:rename (?:this )?file (.+) to (.+))\b", "desktop", "rename_file", lambda m: {"src": m.group(1).strip(), "dest": m.group(2).strip()}, 0.98),
            (r"\b(?:rename (?:this )?file to (.+))\b", "desktop", "rename_file", lambda m: {"src": "selected_file", "dest": m.group(1).strip()}, 0.96),
            (r"\b(?:move (?:the )?file (.+) to (.+))\b", "desktop", "move_file", lambda m: {"src": m.group(1).strip(), "dest": m.group(2).strip()}, 0.98),
            (r"\b(?:delete (?:these |this |the )?files? (.+))\b", "desktop", "delete_file", lambda m: {"file_path": m.group(1).strip()}, 0.98),
            (r"\b(?:delete (?:these |this )?files?)\b", "desktop", "delete_file", {"file_path": "selected_files"}, 0.97),
            (r"\b(?:close (?:the )?calculator)\b", "desktop", "close_application", {"process_name": "calc.exe"}, 0.99),
            (r"\b(?:close (?:the )?app(?:lication)? (.+))\b", "desktop", "close_application", lambda m: {"process_name": m.group(1).strip()}, 0.98),
            (r"\b(?:close (.+))\b", "desktop", "close_application", lambda m: {"process_name": m.group(1).strip()}, 0.92),
            (r"\b(?:open (?:app(?:lication)? )?([a-zA-Z0-9_\- ]+))\b", "desktop", "open_application", lambda m: {"app_name": m.group(1).strip()}, 0.93),

            # 9. Screen Vision & Computer Understanding
            (r"\b(?:what am i looking at|what is on my screen|read what is on my screen|describe (?:my )?screen)\b", "screen_vision", "describe_screen", {}, 0.99),
            (r"\b(?:explain this error|why did this error happen|what is this error|diagnose this error)\b", "screen_vision", "explain_error", {}, 0.99),
            (r"\b(?:how do i fix (?:it|this)|help me fix this problem|fix this problem|propose a fix)\b", "screen_vision", "propose_fix", {}, 0.99),
            (r"\b(?:read (?:the )?screen|extract (?:the )?text|extract text from (?:this )?screen|copy (?:the )?visible text)\b", "screen_vision", "extract_text", {}, 0.98),
            (r"\b(?:summarize this page|summarize (?:the )?screen)\b", "screen_vision", "summarize_screen", {}, 0.98),
            (r"\b(?:which application is currently open|what app is open|active window|current window)\b", "screen_vision", "get_active_window", {}, 0.98),
        ]

    def route(self, user_input: UserInput) -> Intent:
        """
        Classifies incoming user input into a structured Intent.
        """
        raw_text = user_input.content.strip()
        lower_text = raw_text.lower()

        # 1. Explicit metadata override
        if user_input.metadata.get("explicit_intent"):
            explicit = user_input.metadata["explicit_intent"]
            return Intent(
                intent_type=IntentType(explicit.get("type", "unknown")),
                skill_name=explicit.get("skill_name", "system"),
                action=explicit.get("action", ""),
                parameters=explicit.get("parameters", {}),
                confidence=1.0,
                raw_input=raw_text
            )

        # 2. Check for Ambiguity
        ambiguous_keywords = [
            r"^(?:status|show|get|check|do it|run|all)$",
            r"^(?:system or metrics|plan or vault|trends or inbox|code or plan)$",
            r"^(?:open the project|open project)$",
            r"^(?:look at this)$"
        ]
        for amb_pattern in ambiguous_keywords:
            if re.match(amb_pattern, lower_text):
                logger.warning(f"Ambiguous intent detected for: '{raw_text}'")
                if "look at this" in lower_text:
                    clarification_prompt = "Which display would you like me to look at, or should I inspect the active window?"
                elif "project" in lower_text:
                    clarification_prompt = "Which project do you mean: JARVIS OS or Startup Research?"
                else:
                    clarification_prompt = "Please clarify your request."
                return Intent(
                    intent_type=IntentType.UNKNOWN,
                    skill_name="unknown",
                    action="clarify",
                    parameters={"raw_query": raw_text, "is_ambiguous": True, "clarification_prompt": clarification_prompt},
                    confidence=0.3,
                    raw_input=raw_text
                )

        # 3. Rule-based skill pattern matching
        matched_candidates = []
        for pattern, skill_name, action, param_extractor, confidence in self._rules:
            match = re.search(pattern, raw_text, flags=re.IGNORECASE)
            if match:
                params = {}
                if callable(param_extractor):
                    params = param_extractor(match)
                elif isinstance(param_extractor, dict):
                    params = param_extractor.copy()

                matched_candidates.append(
                    Intent(
                        intent_type=IntentType.CODING_TASK if skill_name == "coding" else (
                            IntentType.SYSTEM_CONTROL if skill_name in ("system", "metrics") else IntentType.PLUGIN
                        ),
                        skill_name=skill_name,
                        action=action,
                        parameters=params,
                        confidence=confidence,
                        raw_input=raw_text
                    )
                )

        if matched_candidates:
            matched_candidates.sort(key=lambda x: x.confidence, reverse=True)
            top_match = matched_candidates[0]
            logger.debug(f"Router resolved intent: {top_match.skill_name}:{top_match.action} ({top_match.confidence})")
            return top_match

        # 4. Dynamic match via registered skills
        if self.skill_registry:
            matched_skill = self.skill_registry.match_intent(user_input)
            if matched_skill:
                return matched_skill

        # 5. Check if text is gibberish / completely unknown
        if len(raw_text) == 0 or raw_text.startswith("!@#$%^"):
            return Intent(
                intent_type=IntentType.UNKNOWN,
                skill_name="unknown",
                action="unknown",
                parameters={},
                confidence=0.1,
                raw_input=raw_text
            )

        # 6. Fallback to Conversation Skill
        return Intent(
            intent_type=IntentType.CONVERSATION,
            skill_name="conversation",
            action="chat",
            parameters={"query": raw_text},
            confidence=0.75,
            raw_input=raw_text
        )
