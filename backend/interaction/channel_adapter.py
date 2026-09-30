"""
JARVIS Channel Adapter

Adapts a raw response string to appropriate output for each delivery channel:
- TEXT: Full response, shaped by strategy (length, tone, humor)
- VOICE: Shorter, naturally spoken version (strips markdown, code blocks, headers)
- HUD: Ultra-compact status line (≤12 words)

Also handles:
- Error communication reformatting (raw errors → human-readable)
- Confidence-aware language injection
- Humor insertion (controlled, contextual, never in critical situations)
- Proactive notification text adaptation
"""
import logging
import re
from typing import Optional, Tuple

from .models import (
    ResponseStrategy, ChannelOutput, ResponseLength, TechnicalDepth,
    HumorLevel, VoiceStyle, HUDStyle, InteractionMode, EmotionalSignal,
    ToneStyle
)

logger = logging.getLogger("JARVIS.ChannelAdapter")

# ─────────────────────────────────────────────────────────────────────────────
# Voice content: patterns to strip from spoken output
# ─────────────────────────────────────────────────────────────────────────────
_MARKDOWN_HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
_MARKDOWN_BOLD = re.compile(r"\*{1,2}(.+?)\*{1,2}")
_MARKDOWN_ITALIC = re.compile(r"_{1,2}(.+?)_{1,2}")
_MARKDOWN_CODE_BLOCK = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_MARKDOWN_INLINE_CODE = re.compile(r"`([^`]+)`")
_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_MARKDOWN_BULLET = re.compile(r"^\s*[-*•]\s+", re.MULTILINE)
_MARKDOWN_NUMBERED = re.compile(r"^\s*\d+\.\s+", re.MULTILINE)
_MARKDOWN_TABLE_ROW = re.compile(r"^\|.+\|$", re.MULTILINE)
_MARKDOWN_HR = re.compile(r"^[-_*]{3,}$", re.MULTILINE)

# Voice char limit — anything beyond this gets summarized to first 2 sentences
_VOICE_MAX_CHARS = 300

# HUD word limit
_HUD_MAX_WORDS = 12

# ─────────────────────────────────────────────────────────────────────────────
# Wit snippets for controlled humor injection
# Only used when: humor_level != NONE and not is_critical
# ─────────────────────────────────────────────────────────────────────────────
_WIT_SUFFIXES = {
    "slow": "Fortunately, it has not achieved sentience and started negotiating for better hardware.",
    "processing": "The computations are underway. Patience is a virtue, even for AI.",
    "done": "Done. That was considerably less dramatic than anticipated.",
    "complete": "Complete. All the tedious parts handled, as usual.",
}


class ChannelAdapter:
    """
    Adapts a raw JARVIS response to each delivery channel.

    TEXT, VOICE, and HUD outputs may differ significantly.
    Voice output is always shorter, uses no markdown, and is designed for TTS.
    HUD output is always ultra-compact (status-line style).
    """

    def adapt(
        self,
        raw_response: str,
        strategy: ResponseStrategy,
        channel: str = "text",
        execution_status: Optional[str] = None,
        routing_status: Optional[str] = None,
    ) -> ChannelOutput:
        """
        Produces ChannelOutput with text, voice, and hud variants.

        Args:
            raw_response: The raw response string from the Orchestrator/Skill.
            strategy: ResponseStrategy from the ResponseStrategyEngine.
            channel: Primary delivery channel ("text", "voice", "hud").
            execution_status: "success", "error", "timeout", etc.
            routing_status: "local_only", "cloud", "hybrid", etc.
        """
        if not raw_response:
            raw_response = "Ready."

        # ── Error Communication Reformatter ───────────────────────
        if strategy.is_error:
            raw_response = self._format_error_response(raw_response, execution_status)

        # ── Confidence-Aware Language ─────────────────────────────
        raw_response = self._inject_confidence_language(raw_response, execution_status, routing_status)

        # ── Text Adaptation ───────────────────────────────────────
        text_response = self._adapt_text(raw_response, strategy)

        # ── Voice Adaptation ──────────────────────────────────────
        voice_response = self._adapt_voice(text_response, strategy)

        # ── HUD Adaptation ────────────────────────────────────────
        hud_response = self._adapt_hud(text_response, strategy, execution_status)

        # ── Humor Injection (text only, never voice/HUD) ──────────
        if (
            strategy.humor_level not in (HumorLevel.NONE,) and
            not strategy.is_critical and
            not strategy.is_error
        ):
            text_response = self._maybe_inject_wit(text_response, raw_response, strategy)

        output = ChannelOutput(
            text=text_response,
            voice=voice_response,
            hud=hud_response,
            strategy=strategy
        )

        logger.debug(
            f"[ChannelAdapter] channel={channel} "
            f"text_len={len(text_response)} voice_len={len(voice_response)} hud='{hud_response}'"
        )
        return output

    # ── Text Adaptation ───────────────────────────────────────────

    def _adapt_text(self, response: str, strategy: ResponseStrategy) -> str:
        """Shapes text response by strategy length and tone."""
        if strategy.response_length == ResponseLength.SHORT:
            return self._truncate_to_sentences(response, max_sentences=2)
        elif strategy.response_length == ResponseLength.MEDIUM:
            return self._truncate_to_sentences(response, max_sentences=5)
        elif strategy.response_length == ResponseLength.LONG:
            return response  # Full response
        else:  # ADAPTIVE
            return response

    # ── Voice Adaptation ──────────────────────────────────────────

    def _adapt_voice(self, response: str, strategy: ResponseStrategy) -> str:
        """
        Strips markdown, code blocks, and tables.
        Limits to 1–3 sentences for simple answers.
        Designed to sound natural when spoken aloud.
        """
        voice = response

        # Strip code blocks first (before other patterns)
        voice = _MARKDOWN_CODE_BLOCK.sub("(code block omitted)", voice)
        voice = _MARKDOWN_TABLE_ROW.sub("", voice)
        voice = _MARKDOWN_HR.sub("", voice)
        voice = _MARKDOWN_HEADING.sub("", voice)
        voice = _MARKDOWN_BOLD.sub(r"\1", voice)
        voice = _MARKDOWN_ITALIC.sub(r"\1", voice)
        voice = _MARKDOWN_INLINE_CODE.sub(r"\1", voice)
        voice = _MARKDOWN_LINK.sub(r"\1", voice)
        voice = _MARKDOWN_BULLET.sub("", voice)
        voice = _MARKDOWN_NUMBERED.sub("", voice)

        # Collapse multiple blank lines
        voice = re.sub(r"\n{2,}", " ", voice)
        voice = re.sub(r"\s{2,}", " ", voice).strip()

        # Trim to voice char limit for non-status responses
        if strategy.voice_style != VoiceStyle.NEUTRAL and len(voice) > _VOICE_MAX_CHARS:
            voice = self._truncate_to_sentences(voice, max_sentences=2)

        # For STATUS style — keep even shorter
        if strategy.voice_style == VoiceStyle.STATUS:
            voice = self._truncate_to_sentences(voice, max_sentences=1)

        return voice.strip()

    # ── HUD Adaptation ────────────────────────────────────────────

    def _adapt_hud(self, response: str, strategy: ResponseStrategy, execution_status: Optional[str]) -> str:
        """
        Produces a ≤12-word status string for the HUD overlay.
        """
        # Use known status templates where possible
        if strategy.is_error:
            return "Operation paused. Awaiting your instruction."

        if execution_status == "cancelled":
            return "Operation cancelled."

        if execution_status == "timeout":
            return "Timed out. Ready for your next request."

        # Extract first sentence as HUD basis
        first_sentence = self._get_first_sentence(response)
        words = first_sentence.split()
        if len(words) <= _HUD_MAX_WORDS:
            return first_sentence

        # Truncate to word limit
        return " ".join(words[:_HUD_MAX_WORDS]) + "…"

    # ── Error Communication Reformatter ──────────────────────────

    @staticmethod
    def _format_error_response(raw_response: str, execution_status: Optional[str]) -> str:
        """
        Converts technical error strings to user-readable communication.

        Does NOT fabricate causes. Only reformats what is available.
        """
        lower = raw_response.lower()

        # AI service unavailable
        if any(w in lower for w in ("ai service", "llm", "model", "ollama", "openai", "anthropic")) and \
           any(w in lower for w in ("unavailable", "offline", "failed", "connection")):
            return (
                "The AI service is unavailable right now. "
                "The local fallback is ready, so I can continue offline."
            )

        # Timeout
        if "timeout" in lower or execution_status == "timeout":
            return (
                "The operation timed out before completing. "
                "This can happen with complex tasks or slow connections. "
                "You can try again or break the task into smaller steps."
            )

        # Permission denied
        if "permission" in lower or "denied" in lower or execution_status == "permission_denied":
            return (
                "The action was not permitted under the current security policy. "
                "If you intended this action, you can adjust permissions in settings."
            )

        # Generic error — preserve original but prefix clearly
        if raw_response.strip():
            return f"An issue occurred: {raw_response.strip()}"

        return "Something went wrong. The operation did not complete successfully."

    # ── Confidence-Aware Language ─────────────────────────────────

    @staticmethod
    def _inject_confidence_language(
        response: str,
        execution_status: Optional[str],
        routing_status: Optional[str]
    ) -> str:
        """
        Prefixes responses with appropriate certainty language where needed.

        High confidence → direct statement
        Partial/degraded → "may be" / "appears to"
        Unknown/error → "I cannot confirm yet"
        """
        if not response:
            return response

        lower = response.lower()

        # Already has appropriate hedging? Don't double-wrap.
        already_hedged = any(w in lower for w in (
            "may be", "might be", "appears to", "i cannot confirm", "possibly",
            "it seems", "likely", "uncertain"
        ))
        if already_hedged:
            return response

        # Partial failure or unknown cause
        if execution_status in ("partial_failure", "offline_limited"):
            if not lower.startswith("the connection") and "may" not in lower:
                # Only prefix diagnostics, not all responses
                if any(w in lower for w in ("cause", "reason", "because", "failed", "error")):
                    return "The connection failure may be caused by " + response[0].lower() + response[1:]

        return response

    # ── Controlled Wit Injection ──────────────────────────────────

    @staticmethod
    def _maybe_inject_wit(text: str, raw: str, strategy: ResponseStrategy) -> str:
        """
        Adds a single contextual wit remark when appropriate.

        Rules:
        - Only for LOW or MODERATE humor level in profile
        - Not in URGENT, FRUSTRATED, CONFUSED, FOCUSED signals
        - Not in TECHNICAL_EXPERT mode
        - Maximum one remark per response
        - Only appended — never replaces substantive content
        """
        if strategy.signal in (
            EmotionalSignal.FRUSTRATED, EmotionalSignal.URGENT,
            EmotionalSignal.CONFUSED, EmotionalSignal.FOCUSED
        ):
            return text

        if strategy.interaction_mode == InteractionMode.TECHNICAL_EXPERT:
            return text

        lower = raw.lower()
        for trigger_word, wit in _WIT_SUFFIXES.items():
            if trigger_word in lower:
                # Only append if text doesn't already end with wit
                if wit not in text:
                    return text.rstrip(".") + " " + wit
                break

        return text

    # ── Social Interaction Responses ──────────────────────────────

    @staticmethod
    def build_social_response(user_input: str) -> str:
        """
        Generates a natural assistant response to social greetings.

        Does NOT pretend JARVIS has human feelings.
        Does NOT activate tools, agents, or diagnostics.
        """
        lower = user_input.strip().lower()

        if any(g in lower for g in ("how are you", "how's it going", "how do you do")):
            return "Operational and ready. What would you like to work on?"

        if any(g in lower for g in ("good morning", "morning")):
            return "Good morning. Ready to get started whenever you are."

        if any(g in lower for g in ("good evening", "evening")):
            return "Good evening. Ready to help whenever you need."

        if any(g in lower for g in ("good night", "goodnight")):
            return "Good night. I'll be here when you need me."

        if any(g in lower for g in ("hi", "hey", "hello", "hiya", "howdy")):
            return "Hello. What can I help you with?"

        if "what's up" in lower or "sup" in lower:
            return "Systems nominal. Ready for your next task."

        return "Hello. What would you like to work on?"

    # ── Utilities ─────────────────────────────────────────────────

    @staticmethod
    def _truncate_to_sentences(text: str, max_sentences: int = 2) -> str:
        """Truncates text to first N sentences."""
        # Split on sentence boundaries
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        truncated = " ".join(sentences[:max_sentences])
        return truncated.strip()

    @staticmethod
    def _get_first_sentence(text: str) -> str:
        """Extracts the first sentence from text."""
        match = re.split(r"(?<=[.!?])\s+", text.strip())
        return match[0].strip() if match else text.strip()

    # ── Proactive Notification Adapter ────────────────────────────

    def adapt_notification(
        self,
        title: str,
        message: str,
        suggestion: Optional[str],
        is_focus_active: bool = False
    ) -> Tuple[str, str, str]:
        """
        Adapts a proactive notification for text, voice, and HUD.

        Returns: (text_message, voice_message, hud_message)
        """
        # In focus mode, shorten everything
        if is_focus_active:
            hud = self._truncate_to_sentences(message, max_sentences=1)
            return message, self._adapt_voice_text(message), hud

        # Standard notification
        voice_msg = self._adapt_voice_text(message)
        if suggestion and not is_focus_active:
            voice_msg += f" {suggestion}"

        hud = self._adapt_hud(message, ResponseStrategy(), execution_status=None)
        return message, voice_msg, hud

    @staticmethod
    def _adapt_voice_text(text: str) -> str:
        """Minimal voice cleanup for notification text."""
        clean = _MARKDOWN_BOLD.sub(r"\1", text)
        clean = _MARKDOWN_INLINE_CODE.sub(r"\1", clean)
        return clean.strip()
