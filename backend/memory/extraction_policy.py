import logging
import json
from typing import Dict, Any, Optional

from .memory_models import MemoryDecision, MemoryCategory, MemoryImportance, MemoryConfidence
from backend.llm.model_router import ModelRouter

logger = logging.getLogger("JARVIS.MemoryExtractor")

class MemoryExtractor:
    """
    Evaluates whether a message contains information worth storing long-term.
    Implements relevance policy to avoid polluting long-term memory with
    temporary context, small talk, or irrelevant data.
    """

    def __init__(self, model_router: Optional[ModelRouter] = None):
        self.model_router = model_router

    def evaluate_message(self, text: str, role: str) -> MemoryDecision:
        """
        Determines if a message is worth remembering based on heuristics or LLM evaluation.
        """
        # Only evaluate user or assistant facts
        if role not in ["user", "assistant"]:
            return MemoryDecision.discard()

        text_lower = text.lower().strip()

        # 1. Fast heuristics: Explicit commands
        if text_lower.startswith("remember that") or text_lower.startswith("remember this") or "save this to memory" in text_lower:
            # Strip the trigger prefix
            content = text
            for trigger in ["remember that", "remember this", "save this to memory"]:
                if text_lower.startswith(trigger):
                    content = text[len(trigger):].strip()
                    break
                    
            return MemoryDecision(
                should_save=True,
                category=MemoryCategory.SEMANTIC,
                importance=MemoryImportance.HIGH,
                confidence=MemoryConfidence.USER_EXPLICIT
            )

        # 2. Fast heuristics: Discard small talk, common transient queries
        transient_phrases = ["hello", "hi", "thanks", "thank you", "what's the weather", "open notepad", "bye"]
        if text_lower in transient_phrases or len(text_lower) < 10:
            return MemoryDecision.discard()

        # 3. Fast heuristics: Discard system telemetry
        if "cpu usage" in text_lower or "ram usage" in text_lower:
            return MemoryDecision.discard()

        # 4. LLM-based evaluation
        if self.model_router:
            prompt = f"""
Analyze the following user message to determine if it contains long-term, stable information worth remembering.
Information worth remembering: Preferences, stable facts, project names, technical architecture, user context.
NOT worth remembering: Small talk, greetings, transient questions (weather, open an app), temporary system stats.

Message: "{text}"

Reply in JSON format only with the following structure:
{{
    "should_save": bool,
    "category": "semantic" | "project" | "task" | "episodic" | "short_term",
    "importance": "low" | "medium" | "high",
    "reason": "Brief reason why"
}}
"""
            try:
                # We assume a fast local model is available
                # Using max_tokens=100 as this should be a quick yes/no json response
                response = self.model_router.route_request([{"role": "user", "content": prompt}], fallback_allowed=True)
                # Attempt to parse json
                # The model_router returns text. We'll extract json blocks
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    parsed = json.loads(json_match.group(0))
                    if parsed.get("should_save") is True:
                        cat_str = parsed.get("category", "semantic").upper()
                        imp_str = parsed.get("importance", "low").upper()
                        
                        try:
                            cat = MemoryCategory[cat_str]
                        except KeyError:
                            cat = MemoryCategory.SEMANTIC
                            
                        try:
                            imp = MemoryImportance[imp_str]
                        except KeyError:
                            imp = MemoryImportance.MEDIUM
                            
                        return MemoryDecision(
                            should_save=True,
                            category=cat,
                            importance=imp,
                            confidence=MemoryConfidence.MODEL_INFERRED
                        )
                    else:
                        return MemoryDecision.discard()
            except Exception as e:
                logger.warning(f"Memory extraction LLM evaluation failed: {e}. Defaulting to discard.")
                return MemoryDecision.discard()

        # Default fallback if no router or heuristic matches
        return MemoryDecision.discard()
