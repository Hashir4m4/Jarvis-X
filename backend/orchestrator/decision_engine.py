import re
import logging
from typing import Dict, Any, List, Optional, Tuple

from backend.core.models import TaskCategory, Intent, IntentType

logger = logging.getLogger("JARVIS.DecisionEngine")

# Pattern rules for task classification
PATTERNS = {
    TaskCategory.CODING_TASK: [
        r"\b(build|write|create|generate|fix|refactor|debug|code|script|python|javascript|html|css|program)\b.*\b(script|file|app|function|class|code|program|test|csv|pipeline)\b",
        r"^write a (python|script|program)",
        r"^code a",
        r"^build a"
    ],
    TaskCategory.PLANNING_TASK: [
        r"\b(plan|prioritize|schedule|roadmap|goals|agenda)\b",
        r"plan today",
        r"what do i need to do",
        r"daily plan"
    ],
    TaskCategory.MEMORY_REQUEST: [
        r"\b(remember|recall|memory|vault|what did i say|what was|store this|search notes|daily log|find note)\b",
        r"^remember that",
        r"^recall"
    ],
    TaskCategory.RESEARCH_TASK: [
        r"\b(research|investigate|compare|deep dive|study|literature|options for|pros and cons of)\b"
    ],
    TaskCategory.COMPUTER_ACTION: [
        r"\b(open|close|launch|minimize|maximize|kill|click|press|type|screenshot|volume|brightness|wifi|bluetooth)\b",
        r"^open ",
        r"^close ",
        r"^set volume",
        r"^set brightness"
    ],
    TaskCategory.COMMAND: [
        r"\b(brief|metrics|status|diagnostic|telemetry|close the day|scan|pull|restart|shutdown)\b",
        r"morning brief",
        r"metrics pull",
        r"system status",
        r"close the day"
    ],
    TaskCategory.QUESTION: [
        r"^(what|who|where|when|why|how|is|are|can|could|should|tell me|explain)\b",
        r"\?$"
    ]
}



class DecisionAction(str):
    IGNORE = "IGNORE"
    NOTIFY = "NOTIFY"
    ASK_CONFIRMATION = "ASK_CONFIRMATION"
    EXECUTE = "EXECUTE"

class DecisionEngine:
    """
    Evaluates incoming requests to determine task category, required capabilities,
    execution strategy, model selection, tool/agent needs, and memory persistence policies.
    """
    @staticmethod
    def evaluate(event, rule_suggestion: Optional[str] = None) -> str:
        suggestion = str(rule_suggestion).lower() if rule_suggestion else ""
        if "diagnose" in suggestion or "cleanup" in suggestion or "scan" in suggestion:
            priority = getattr(event, "priority", None)
            # Try to import EventPriority dynamically if not present
            try:
                from backend.proactive.models import EventPriority
                if priority in (EventPriority.HIGH, EventPriority.CRITICAL):
                    return DecisionAction.ASK_CONFIRMATION
            except ImportError:
                pass
            return DecisionAction.EXECUTE

        return DecisionAction.NOTIFY

    @staticmethod
    def classify_task(user_input: str, intent: Optional[Intent] = None) -> TaskCategory:
        """Determines the high-level task category from user text and intent."""
        lower = user_input.strip().lower()

        # 1. Check intent override
        if intent:
            if intent.intent_type == IntentType.CODING_TASK:
                return TaskCategory.CODING_TASK
            elif intent.intent_type == IntentType.APP_CONTROL or intent.intent_type == IntentType.SYSTEM_CONTROL:
                return TaskCategory.COMPUTER_ACTION
            elif intent.intent_type == IntentType.FILE_MANAGEMENT:
                return TaskCategory.COMPUTER_ACTION
            elif intent.skill_name == "vault":
                return TaskCategory.MEMORY_REQUEST
            elif intent.skill_name in ("plan", "close_day"):
                return TaskCategory.PLANNING_TASK

        # 2. Check regex classification patterns
        for category, pattern_list in PATTERNS.items():
            for pat in pattern_list:
                if re.search(pat, lower, re.IGNORECASE):
                    return category

        # Default fallback
        if len(lower.split()) <= 4 and ("hi" in lower or "hello" in lower or "hey" in lower):
            return TaskCategory.CONVERSATION
        return TaskCategory.QUESTION

    @staticmethod
    def requires_memory_context(task_cat: TaskCategory, user_input: str) -> bool:
        """Determines whether context retrieval from Vault/SQLite is necessary."""
        lower = user_input.lower()
        if task_cat in (TaskCategory.MEMORY_REQUEST, TaskCategory.PLANNING_TASK, TaskCategory.RESEARCH_TASK):
            return True
        if any(w in lower for w in ("project", "last time", "earlier", "yesterday", "context", "notes", "my ")):
            return True
        return False

    @staticmethod
    def select_strategy_and_capabilities(
        task_cat: TaskCategory,
        skill_name: Optional[str],
        user_input: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Optional[str], List[str], List[str]]:
        """
        Returns:
        (execution_strategy, selected_model, selected_tools, selected_agents)

        Model selection is deferred to the ModelRouter. This method returns
        model=None for strategies that need AI, allowing the orchestrator
        to fill it via the Hybrid Intelligent Model Router.
        """
        # 1. Simple direct skills (Zero unnecessary agent or LLM overhead)
        if skill_name in ("system", "metrics", "trends", "inbox", "screen_vision", "desktop") or task_cat == TaskCategory.COMPUTER_ACTION:
            return ("direct_skill", None, ["system_tools"], [])

        # 2. Coding tasks (Invoke Coding Agent)
        if task_cat == TaskCategory.CODING_TASK or skill_name == "coding":
            return (
                "multi_agent",
                None,  # Deferred to ModelRouter
                ["code_tools", "terminal_tools", "file_tools"],
                ["coding_agent"]
            )

        # 3. Planning & Roadmaps
        lower = user_input.lower()
        if any(w in lower for w in ("roadmap", "milestone", "plan development", "project plan")):
            return ("multi_agent", None, ["plan_tools"], ["planning_agent"])

        # 4. Research Tasks (Research Agent + Analysis Agent if comparing)
        if task_cat == TaskCategory.RESEARCH_TASK or "research" in lower:
            agents = ["research_agent"]
            if any(w in lower for w in ("compare", "recommend", "evaluate", "vs", "versus")):
                agents.append("analysis_agent")
            return ("multi_agent", None, ["web_tools", "analysis_tools"], agents)

        # 5. Planning & Daily Notes
        if task_cat == TaskCategory.PLANNING_TASK or skill_name in ("plan", "close_day", "brief"):
            return ("direct_skill", None, ["vault_tools"], [])

        # 6. Memory Queries
        if task_cat == TaskCategory.MEMORY_REQUEST or skill_name == "vault":
            return ("direct_skill", None, ["vault_tools", "sqlite_tools"], [])

        # 7. General Conversation & Knowledge Questions
        return ("conversation", None, [], [])

    @staticmethod
    def requires_verification(task_cat: TaskCategory, skill_name: Optional[str]) -> bool:
        """Checks if the result of this execution requires post-execution verification."""
        if task_cat in (TaskCategory.CODING_TASK, TaskCategory.COMPUTER_ACTION, TaskCategory.RESEARCH_TASK):
            return True
        if skill_name in ("coding", "system"):
            return True
        return False

    @staticmethod
    def should_save_memory(task_cat: TaskCategory, skill_name: Optional[str], success: bool, user_input: str = "") -> 'MemoryDecision':
        """Determines if and how the result should be preserved in Obsidian Vault / SQLite memory."""
        from backend.memory.memory_models import MemoryDecision, MemoryCategory, MemoryImportance

        if not success:
            return MemoryDecision.discard()

        lower_input = user_input.lower()

        # Explicit memory skills handle their own persistence, but we record the command itself
        if skill_name == "memory":
            return MemoryDecision(should_save=True, category=MemoryCategory.SEMANTIC, importance=MemoryImportance.CRITICAL)

        # Detect explicit preferences
        if any(w in lower_input for w in ("prefer", "always", "never", "make sure to", "i like")):
            return MemoryDecision(should_save=True, category=MemoryCategory.SEMANTIC, importance=MemoryImportance.HIGH)

        # Detect architecture/decisions
        if any(w in lower_input for w in ("decided", "architecture", "design", "rule")):
            return MemoryDecision(should_save=True, category=MemoryCategory.PROJECT, importance=MemoryImportance.HIGH)

        # Categorize by task/skill
        if task_cat in (TaskCategory.PLANNING_TASK, TaskCategory.RESEARCH_TASK):
            return MemoryDecision(should_save=True, category=MemoryCategory.PROJECT, importance=MemoryImportance.MEDIUM)

        if skill_name in ("plan", "close_day", "brief", "metrics", "vault", "coding"):
            return MemoryDecision(should_save=True, category=MemoryCategory.EPISODIC, importance=MemoryImportance.MEDIUM)

        # Temporary/Trivia
        if task_cat in (TaskCategory.QUESTION, TaskCategory.CONVERSATION, TaskCategory.COMPUTER_ACTION, TaskCategory.COMMAND):
            return MemoryDecision(should_save=False, category=MemoryCategory.SHORT_TERM, importance=MemoryImportance.LOW)

        return MemoryDecision.discard()
