import logging
from typing import Dict, Any, Generator, List

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.brain import Brain

logger = logging.getLogger(__name__)


class ConversationSkill(BaseSkill):
    """
    Skill for general conversation, multi-modal reasoning, and complex LLM tool synthesis.
    Delegates to the existing Brain engine.
    """

    def __init__(self, brain: Brain, metadata=None):
        super().__init__(metadata=metadata)
        self.brain = brain

    @property
    def name(self) -> str:
        return "conversation"

    @property
    def description(self) -> str:
        return "Handles general AI dialogue, question answering, and LLM tool execution."

    @property
    def supported_actions(self) -> List[str]:
        return ["chat"]

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        """Synchronous chat processing via Brain."""
        query = intent.parameters.get("query", intent.raw_input)
        try:
            response_text = self.brain.chat_sync(query)
            return SkillResult(
                success=True,
                data={"response": response_text},
                message="Conversation response generated",
                output_text=response_text
            )
        except Exception as e:
            logger.error(f"Error in ConversationSkill: {e}")
            return SkillResult(success=False, message=str(e), output_text=f"AI brain error: {e}")

    def execute_stream(self, intent: Intent, context: Dict[str, Any] = None) -> Generator[str, None, None]:
        """Streaming chat processing via Brain."""
        query = intent.parameters.get("query", intent.raw_input)
        try:
            yield from self.brain.chat_stream(query)
        except Exception as e:
            logger.error(f"Error in ConversationSkill stream: {e}")
            yield f"\n[Brain error: {e}]"
