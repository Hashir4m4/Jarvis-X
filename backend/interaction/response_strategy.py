"""
JARVIS Response Strategy Engine

Determines the concrete communication strategy before the final response
is generated or delivered. Maps personality profile + interaction state +
emotional signal + task category + channel to a ResponseStrategy.

This engine does NOT generate text. It produces a structured decision
that the ChannelAdapter uses to shape the final output.
"""
import logging
from typing import Optional

from .models import (
    PersonalityProfile, InteractionState, EmotionalSignalResult,
    ResponseStrategy, ResponseLength, ToneStyle, TechnicalDepth,
    HumorLevel, VoiceStyle, HUDStyle, InteractionMode,
    EmotionalSignal, SignalConfidence, VerbosityLevel
)

logger = logging.getLogger("JARVIS.ResponseStrategyEngine")

# Task categories that always suppress humor regardless of profile
_CRITICAL_TASK_CATEGORIES = {
    "computer_action", "coding_task", "COMPUTER_ACTION", "CODING_TASK"
}

# Statuses that classify as critical/error states
_CRITICAL_STATUSES = {"error", "timeout", "permission_denied", "cancelled", "partial_failure"}

# Response length mapping from verbosity preference
_VERBOSITY_TO_LENGTH = {
    VerbosityLevel.CONCISE: ResponseLength.SHORT,
    VerbosityLevel.DETAILED: ResponseLength.LONG,
    VerbosityLevel.ADAPTIVE: ResponseLength.ADAPTIVE,
}


class ResponseStrategyEngine:
    """
    Maps the current context to a concrete ResponseStrategy.

    Priority order (highest → lowest):
    1. Critical situation (error, security, safety) → overrides everything
    2. Focus Mode active → suppress, be concise
    3. Emotional signal (if actionable confidence) → tone adaptation
    4. Interaction mode (TECHNICAL_EXPERT, BUILDER, SOCIAL) → style
    5. Task category → depth and length defaults
    6. Personality profile → baseline preferences
    """

    def determine(
        self,
        profile: PersonalityProfile,
        state: InteractionState,
        signal_result: EmotionalSignalResult,
        task_category: str = "conversation",
        channel: str = "text",
        user_input: str = "",
        execution_status: Optional[str] = None,
        routing_status: Optional[str] = None,
    ) -> ResponseStrategy:
        """
        Determines the full ResponseStrategy for this interaction turn.

        Args:
            profile: Active personality profile.
            state: Current interaction state.
            signal_result: Emotional signal classification result.
            task_category: Task category from Orchestrator.
            channel: "text", "voice", or "hud".
            user_input: Raw user text (for heuristics).
            execution_status: Outcome from Orchestrator ("success", "error", etc.)
            routing_status: Model routing result ("local_only", "cloud", etc.)

        Returns:
            ResponseStrategy with all fields populated.
        """
        strategy = ResponseStrategy()

        # ── Layer 1: Critical / Error Override ────────────────────
        is_critical = (
            execution_status in _CRITICAL_STATUSES or
            task_category in _CRITICAL_TASK_CATEGORIES or
            "emergency" in user_input.lower() or
            "critical" in user_input.lower()
        )
        is_error = execution_status in ("error", "timeout", "permission_denied", "partial_failure")

        strategy.is_critical = is_critical
        strategy.is_error = is_error
        strategy.signal = signal_result.signal

        if is_critical or is_error:
            strategy.humor_level = HumorLevel.NONE
            strategy.tone = ToneStyle.PROFESSIONAL
            strategy.proactive_suggestions = False
            strategy.response_length = ResponseLength.MEDIUM  # Errors need enough context
            strategy.voice_style = VoiceStyle.ALERT if is_error else VoiceStyle.STATUS
            strategy.hud_style = HUDStyle.ERROR

            # Still apply technical depth from profile/mode
            strategy.technical_depth = self._resolve_technical_depth(profile, state, task_category)

            logger.debug(f"[StrategyEngine] Critical/error path — humor suppressed")
            return strategy

        # ── Layer 2: Focus Mode ────────────────────────────────────
        if state.focus_active or state.interaction_mode == InteractionMode.FOCUS:
            strategy.interaction_mode = InteractionMode.FOCUS
            strategy.response_length = ResponseLength.SHORT
            strategy.humor_level = HumorLevel.NONE
            strategy.tone = ToneStyle.DIRECT
            strategy.proactive_suggestions = False
            strategy.voice_style = VoiceStyle.STATUS
            strategy.hud_style = HUDStyle.STATUS
            strategy.technical_depth = profile.technical_depth
            logger.debug("[StrategyEngine] Focus mode active — concise, no suggestions")
            return strategy

        # ── Layer 3: Emotional Signal Adaptation ──────────────────
        signal = signal_result.signal
        strategy.signal = signal

        if signal_result.is_actionable():
            self._apply_signal_adaptation(strategy, signal, profile)
        else:
            # Default to profile baseline
            strategy.humor_level = profile.humor_level
            strategy.tone = ToneStyle.PROFESSIONAL

        # ── Layer 4: Interaction Mode Overrides ───────────────────
        mode = state.interaction_mode
        strategy.interaction_mode = mode

        if mode == InteractionMode.SOCIAL:
            strategy.response_length = ResponseLength.SHORT
            strategy.tone = ToneStyle.WARM
            strategy.humor_level = min(profile.humor_level, HumorLevel.MODERATE)
            strategy.proactive_suggestions = False
            strategy.voice_style = VoiceStyle.CONVERSATIONAL
            strategy.hud_style = HUDStyle.STATUS

        elif mode == InteractionMode.TECHNICAL_EXPERT:
            strategy.technical_depth = TechnicalDepth.EXPERT
            strategy.response_length = ResponseLength.LONG
            strategy.humor_level = HumorLevel.NONE
            strategy.tone = ToneStyle.PROFESSIONAL
            strategy.voice_style = VoiceStyle.NEUTRAL

        elif mode == InteractionMode.BUILDER:
            strategy.technical_depth = TechnicalDepth.EXPERT
            strategy.response_length = ResponseLength.MEDIUM
            strategy.tone = ToneStyle.DIRECT
            strategy.proactive_suggestions = True
            strategy.voice_style = VoiceStyle.CONVERSATIONAL

        else:
            # Standard mode — use task category and profile defaults
            # BUT respect any signal-driven overrides set in Layer 3

            # Only set technical_depth if signal didn't already override it
            if not (signal_result.is_actionable() and signal == EmotionalSignal.CONFUSED):
                strategy.technical_depth = self._resolve_technical_depth(profile, state, task_category)
            strategy.voice_style = profile.voice_style

            # Only set proactive_suggestions if signal didn't already set it to False
            if signal_result.is_actionable() and signal in (
                EmotionalSignal.URGENT, EmotionalSignal.FOCUSED
            ):
                # Keep signal-driven False
                pass
            else:
                strategy.proactive_suggestions = (
                    profile.proactivity_level.value != "MINIMAL" and not state.focus_active
                )

            # Only resolve length if signal didn't already fix it
            if not signal_result.is_actionable():
                strategy.response_length = self._resolve_length(profile, task_category, user_input)

        # ── Layer 5: HUD Style ────────────────────────────────────
        if not strategy.hud_style or strategy.hud_style == HUDStyle.STATUS:
            strategy.hud_style = self._resolve_hud_style(task_category, execution_status)

        # ── Layer 6: Clarification Check ──────────────────────────
        strategy.clarification_needed = self._needs_clarification(user_input, state)

        logger.debug(
            f"[StrategyEngine] Strategy: len={strategy.response_length.value} "
            f"tone={strategy.tone.value} tech={strategy.technical_depth.value} "
            f"humor={strategy.humor_level.value} mode={mode.value}"
        )
        return strategy

    # ── Signal → Strategy Mapping Table ──────────────────────────

    @staticmethod
    def _apply_signal_adaptation(
        strategy: ResponseStrategy,
        signal: EmotionalSignal,
        profile: PersonalityProfile
    ):
        """Maps detected communication signal to tone and style adjustments."""
        if signal == EmotionalSignal.FRUSTRATED:
            strategy.tone = ToneStyle.CALM
            strategy.humor_level = HumorLevel.NONE  # Never joke when frustrated
            strategy.proactive_suggestions = True   # But do offer solutions
            strategy.response_length = ResponseLength.MEDIUM

        elif signal == EmotionalSignal.CONFUSED:
            strategy.tone = ToneStyle.SUPPORTIVE
            strategy.technical_depth = TechnicalDepth.SIMPLE  # Reduce jargon
            strategy.humor_level = HumorLevel.NONE
            strategy.response_length = ResponseLength.MEDIUM
            strategy.proactive_suggestions = True

        elif signal == EmotionalSignal.EXCITED:
            # Match energy moderately — don't match all caps enthusiasm
            strategy.tone = ToneStyle.WARM
            strategy.humor_level = min(profile.humor_level, HumorLevel.LOW)
            strategy.response_length = ResponseLength.MEDIUM

        elif signal == EmotionalSignal.URGENT:
            strategy.tone = ToneStyle.DIRECT
            strategy.humor_level = HumorLevel.NONE
            strategy.response_length = ResponseLength.SHORT  # Direct action first
            strategy.proactive_suggestions = False           # No tangents

        elif signal == EmotionalSignal.FOCUSED:
            strategy.tone = ToneStyle.DIRECT
            strategy.humor_level = HumorLevel.NONE
            strategy.response_length = ResponseLength.SHORT
            strategy.proactive_suggestions = False

        elif signal == EmotionalSignal.UNSURE:
            strategy.tone = ToneStyle.SUPPORTIVE
            strategy.technical_depth = TechnicalDepth.ADAPTIVE
            strategy.response_length = ResponseLength.MEDIUM
            strategy.proactive_suggestions = True

        else:  # NEUTRAL
            strategy.tone = ToneStyle.PROFESSIONAL
            strategy.humor_level = profile.humor_level

    @staticmethod
    def _resolve_technical_depth(
        profile: PersonalityProfile,
        state: InteractionState,
        task_category: str
    ) -> TechnicalDepth:
        """Resolves technical depth from profile and task signals."""
        if state.interaction_mode == InteractionMode.TECHNICAL_EXPERT:
            return TechnicalDepth.EXPERT
        if state.correction_frequency >= 3:
            return TechnicalDepth.SIMPLE  # Simplify after repeated corrections
        tech_tasks = {"coding_task", "research_task", "vision_task", "CODING_TASK", "RESEARCH_TASK"}
        if task_category in tech_tasks:
            return TechnicalDepth.EXPERT
        return profile.technical_depth

    @staticmethod
    def _resolve_length(
        profile: PersonalityProfile,
        task_category: str,
        user_input: str
    ) -> ResponseLength:
        """Resolves response length from context."""
        # Very short questions → short answers
        word_count = len(user_input.split())
        if word_count <= 5 and "?" in user_input:
            return ResponseLength.SHORT

        task_to_length = {
            "question": ResponseLength.SHORT,
            "conversation": ResponseLength.SHORT,
            "command": ResponseLength.SHORT,
            "computer_action": ResponseLength.SHORT,
            "coding_task": ResponseLength.LONG,
            "research_task": ResponseLength.LONG,
            "planning_task": ResponseLength.LONG,
            "multi_step_task": ResponseLength.LONG,
        }
        cat_lower = task_category.lower()
        for cat, length in task_to_length.items():
            if cat in cat_lower:
                return length

        return _VERBOSITY_TO_LENGTH.get(profile.verbosity, ResponseLength.ADAPTIVE)

    @staticmethod
    def _resolve_hud_style(task_category: str, execution_status: Optional[str]) -> HUDStyle:
        if execution_status in ("error", "timeout", "permission_denied"):
            return HUDStyle.ERROR
        if execution_status == "cancelled":
            return HUDStyle.NOTIFICATION
        if "task" in task_category.lower() or "coding" in task_category.lower():
            return HUDStyle.PROGRESS
        return HUDStyle.STATUS

    @staticmethod
    def _needs_clarification(user_input: str, state: InteractionState) -> bool:
        """
        Determines if clarification should be requested.

        Clarification is ONLY requested when intent is genuinely ambiguous.
        If context is clear, JARVIS proceeds without asking.
        """
        vague_inputs = {"it", "that", "this", "them", "those", "open it", "do it", "do that"}
        lower = user_input.strip().lower()

        # "Continue" with an active task = no clarification needed
        if lower in ("continue", "go on", "proceed", "keep going") and state.active_task_id:
            return False

        # Vague pronouns with no active context
        if lower in vague_inputs and not state.active_task_context:
            return True

        # Short vague command: "open it" with no context
        if len(lower.split()) <= 3 and any(w in lower for w in ("it", "that", "this")):
            if not state.active_task_context:
                return True

        return False
