import logging
from typing import Dict, Any
from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult

logger = logging.getLogger("JARVIS.MemorySkill")


class MemorySkill(BaseSkill):
    """
    Skill for explicitly managing long-term memory.
    Supports explicitly remembering facts/preferences, forgetting them,
    and querying the knowledge base directly.
    """

    @property
    def name(self) -> str:
        return "memory"

    @property
    def description(self) -> str:
        return "Explicitly manages JARVIS's long-term memory. Supports remember, forget, and query."

    def execute(self, intent: Intent, context: Dict[str, Any]) -> SkillResult:
        memory_api = context.get("memory")
        if not memory_api:
            return SkillResult(
                success=False,
                message="Memory API is not available.",
                output_text="I cannot access my memory systems right now."
            )

        # Basic action parsing from raw_input
        lower_input = intent.raw_input.lower()
        
        # Action: FORGET
        if "forget" in lower_input or "don't remember" in lower_input:
            content_to_forget = intent.raw_input.replace("forget that", "").replace("forget", "").replace("don't remember", "").strip()
            
            logger.info("MEMORY: Forgetting memory")
            
            # Try to search for it first
            results = memory_api.search_memory(content_to_forget, limit=1)
            if results:
                target_id = results[0].get("id") or results[0].get("path", "")
                if target_id:
                    memory_api.forget_memory(target_id)
                    return SkillResult(
                        success=True,
                        message="Forget command processed.",
                        output_text="I have removed that information from my active memory."
                    )
            
            return SkillResult(
                success=True,
                message="Forget command processed, but no match found.",
                output_text="I couldn't find any specific memory matching that to delete."
            )

        # Action: CLEAR
        elif "clear conversation memory" in lower_input or "clear memory" in lower_input:
            memory_api.clear_memory()
            return SkillResult(
                success=True,
                message="Conversation memory cleared.",
                output_text="I have cleared the short-term conversation memory. Long term memories have been retained."
            )

        # Action: QUERY
        elif "what do you remember" in lower_input or "what was" in lower_input or "search" in lower_input:
            # Extract query roughly
            query = intent.raw_input.replace("what do you remember about", "").replace("what do you remember", "").strip()
            if not query:
                query = "JARVIS"
                
            results = memory_api.search_memory(query, limit=3)
            if not results:
                logger.info("MEMORY: No relevant memory found")
                return SkillResult(
                    success=True,
                    message="Query executed, no results.",
                    output_text=f"I couldn't find any long-term memories related to '{query}'."
                )
            
            logger.info("MEMORY: Retrieving project knowledge")
            
            output = f"Here is what I remember about '{query}':\n"
            for r in results:
                content = r.get("content", "").strip()
                output += f"- {content}\n"
                
            return SkillResult(
                success=True,
                message="Memory query successful.",
                output_text=output,
                data={"results": results}
            )

        # Action: REMEMBER (Default)
        else:
            content_to_remember = intent.raw_input.replace("remember that", "").replace("remember this", "").replace("save this to memory", "").strip()
            
            logger.info("MEMORY: Saving important explicit decision")
            
            # Explicit user memory
            memory_api.write_memory(
                content=content_to_remember,
                memory_type="semantic",
                category="semantic",
                metadata={"importance": "high", "confidence": "user_explicit", "role": "user"}
            )
            
            return SkillResult(
                success=True,
                message="Memory explicitly saved.",
                output_text=f"I have saved '{content_to_remember}' to my long-term memory."
            )
