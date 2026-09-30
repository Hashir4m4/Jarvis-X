"""
JARVIS Interaction Engine

Central coordinator for the Personality and Adaptive Interaction System.

Pipeline:
    USER INPUT
      → pre_process()     [before Orchestrator]
          → InteractionStateManager.update_state()
          → EmotionalSignalDetector.detect()
          → ResponseStrategyEngine.determine()
      → JARVIS ORCHESTRATOR (unchanged)
      → post_process()    [after Orchestrator]
          → ChannelAdapter.adapt()
      → ChannelOutput (text / voice / hud)

The personality system INFLUENCES communication.
It does NOT replace intelligence, safety, permissions, or reasoning.
Personality remains consistent regardless of which model was selected.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple

from .models import (
    InteractionState, EmotionalSignalResult, ResponseStrategy, ChannelOutput,
    InteractionMode, EmotionalSignal
)
from .personality import PersonalityRegistry
from .signal_detector import EmotionalSignalDetector
from .state_manager import InteractionStateManager
from .response_strategy import ResponseStrategyEngine
from .channel_adapter import ChannelAdapter

logger = logging.getLogger("JARVIS.InteractionEngine")


class InteractionEngine:
    """
    Facade coordinating the full Personality and Adaptive Interaction pipeline.

    Instantiated once in JarvisCore and injected into JarvisOrchestrator.
    All methods are synchronous — no async needed (pure computation).
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        personality_registry: Optional[PersonalityRegistry] = None,
        state_manager: Optional[InteractionStateManager] = None,
        strategy_engine: Optional[ResponseStrategyEngine] = None,
        channel_adapter: Optional[ChannelAdapter] = None,
    ):
        self.config = config or {}
        self.personality = personality_registry or PersonalityRegistry(config=config)
        self.state_manager = state_manager or InteractionStateManager()
        self.strategy_engine = strategy_engine or ResponseStrategyEngine()
        self.channel_adapter = channel_adapter or ChannelAdapter()
        self.detector = EmotionalSignalDetector()

        logger.info(
            f"[InteractionEngine] Initialized. "
            f"Active profile: '{self.personality.get_active_profile().name}'"
        )

    # ─────────────────────────────────────────────────────────────
    # Pre-Processing (called BEFORE Orchestrator executes)
    # ─────────────────────────────────────────────────────────────

    def pre_process(
        self,
        user_input: str,
        session_id: str = "default",
        task_category: str = "conversation",
        channel: str = "text",
        history: Optional[List[str]] = None,
        active_task_id: Optional[str] = None,
        active_task_context: Optional[str] = None,
    ) -> Tuple[InteractionState, EmotionalSignalResult, ResponseStrategy]:
        """
        Analyzes the incoming request and determines how JARVIS should respond.

        Returns:
            (state, signal_result, strategy) to be passed into the Orchestrator context.
        """
        # 1. Get current session state
        state = self.state_manager.get_or_create(session_id)
        if active_task_id:
            state.active_task_id = active_task_id
        if active_task_context:
            state.active_task_context = active_task_context

        # 2. Detect emotional signal
        history = history or []
        frustration_count = self.state_manager.get_frustration_count(session_id)
        signal_result = EmotionalSignalDetector.detect(
            user_input=user_input,
            history=history,
            session_frustration_count=frustration_count
        )

        # 3. Update state
        state = self.state_manager.update_state(
            session_id=session_id,
            user_input=user_input,
            signal_result=signal_result,
            task_category=task_category,
            active_task_id=active_task_id,
            active_task_context=active_task_context,
        )

        # 4. Determine response strategy
        profile = self.personality.get_active_profile()
        strategy = self.strategy_engine.determine(
            profile=profile,
            state=state,
            signal_result=signal_result,
            task_category=task_category,
            channel=channel,
            user_input=user_input,
        )

        logger.debug(
            f"[InteractionEngine] pre_process: session={session_id} "
            f"signal={signal_result.signal.value}({signal_result.confidence.value}) "
            f"strategy=len:{strategy.response_length.value},tone:{strategy.tone.value}"
        )
        return state, signal_result, strategy

    # ─────────────────────────────────────────────────────────────
    # Post-Processing (called AFTER Orchestrator returns)
    # ─────────────────────────────────────────────────────────────

    def post_process(
        self,
        raw_response: str,
        strategy: ResponseStrategy,
        channel: str = "text",
        execution_status: Optional[str] = None,
        routing_status: Optional[str] = None,
        session_id: str = "default",
        task_category: str = "conversation",
    ) -> ChannelOutput:
        """
        Adapts the raw Orchestrator response through the personality pipeline.

        The same raw content is adapted differently for text, voice, and HUD.
        Personality remains consistent regardless of which model was used.

        Returns:
            ChannelOutput with .text, .voice, and .hud fields.
        """
        # Refresh strategy with execution outcome (error override, confidence language)
        profile = self.personality.get_active_profile()
        state = self.state_manager.get_or_create(session_id)

        # Re-determine strategy with execution outcome baked in
        signal_result = EmotionalSignalResult(
            signal=strategy.signal,
            confidence=strategy.response_length.__class__.__mro__[0].__mro__[0]  # dummy, use existing
        )
        # Build a fresh signal result from strategy state (avoids re-detection)
        from .models import EmotionalSignalResult as ESR, SignalConfidence
        signal_result = ESR(
            signal=strategy.signal,
            confidence=SignalConfidence.MODERATE
        )

        final_strategy = self.strategy_engine.determine(
            profile=profile,
            state=state,
            signal_result=signal_result,
            task_category=task_category,
            channel=channel,
            user_input=raw_response[:80],  # Only for length heuristics
            execution_status=execution_status,
            routing_status=routing_status,
        )

        output = self.channel_adapter.adapt(
            raw_response=raw_response,
            strategy=final_strategy,
            channel=channel,
            execution_status=execution_status,
            routing_status=routing_status,
        )

        logger.debug(
            f"[InteractionEngine] post_process: status={execution_status} "
            f"channel={channel} text_len={len(output.text)} hud='{output.hud}'"
        )
        return output

    # ─────────────────────────────────────────────────────────────
    # Social Interaction Routing
    # ─────────────────────────────────────────────────────────────

    def handle_social(self, user_input: str, session_id: str = "default") -> Optional[ChannelOutput]:
        """
        Checks if input is a social greeting and returns a canned response.

        Returns ChannelOutput if social, None if not (let Orchestrator handle).

        IMPORTANT: Social responses DO NOT activate tools, agents, or skills.
        JARVIS does NOT pretend to have human feelings.
        """
        if not EmotionalSignalDetector.is_social_greeting(user_input):
            return None

        text = ChannelAdapter.build_social_response(user_input)
        profile = self.personality.get_active_profile()
        state = self.state_manager.get_or_create(session_id)

        from .models import EmotionalSignalResult, SignalConfidence
        strategy = self.strategy_engine.determine(
            profile=profile,
            state=state,
            signal_result=EmotionalSignalResult(
                signal=EmotionalSignal.NEUTRAL,
                confidence=SignalConfidence.HIGH
            ),
            task_category="conversation",
            channel="text",
            user_input=user_input,
            execution_status="success"
        )
        strategy.interaction_mode = InteractionMode.SOCIAL

        return self.channel_adapter.adapt(
            raw_response=text,
            strategy=strategy,
            channel="text",
            execution_status="success"
        )

    # ─────────────────────────────────────────────────────────────
    # Interruption Handling
    # ─────────────────────────────────────────────────────────────

    def check_interruption(self, user_input: str) -> Tuple[bool, bool]:
        """
        Detects voice/task interruption intent.

        Returns:
            (stop_voice: bool, stop_task: bool)
        """
        return EmotionalSignalDetector.is_interruption_command(user_input)

    # ─────────────────────────────────────────────────────────────
    # Profile & Mode Management
    # ─────────────────────────────────────────────────────────────

    def switch_profile(self, name_or_id: str) -> bool:
        """
        Switches active personality profile by name or ID.
        Called when user says "switch to builder mode", etc.
        """
        success = self.personality.set_profile_by_name(name_or_id)
        if not success:
            success = self.personality.set_active_profile(name_or_id)
        return success

    def set_interaction_mode(self, session_id: str, mode: InteractionMode):
        """Sets the current interaction mode for the session."""
        self.state_manager.set_interaction_mode(session_id, mode)

    def set_focus_mode(self, session_id: str, active: bool):
        """Toggles Focus Mode for the session."""
        self.state_manager.set_focus_mode(session_id, active)

    def record_user_preference(self, key: str, value: Any, memory_api=None):
        """
        Records an explicit user preference.

        Only explicit statements are stored (e.g., "Always give me technical explanations").
        Temporary moods are NEVER stored here.
        Forwards to MemoryAPI if provided and permitted.
        """
        self.personality.update_preference(key, value)
        if memory_api:
            try:
                memory_api.add_message(
                    "preference",
                    f"{key}: {value}",
                    {"type": "user_preference", "importance": "HIGH"}
                )
            except Exception as e:
                logger.debug(f"[InteractionEngine] Could not persist preference to memory: {e}")

    def record_correction(self, session_id: str):
        """Records that the user corrected JARVIS this turn."""
        self.state_manager.record_correction(session_id)

    def clear_task_context(self, session_id: str):
        """Clears task context when a task completes or is cancelled."""
        self.state_manager.clear_task_context(session_id)

    # ─────────────────────────────────────────────────────────────
    # Notification Adaptation
    # ─────────────────────────────────────────────────────────────

    def adapt_notification(
        self,
        title: str,
        message: str,
        suggestion: Optional[str],
        session_id: str = "default"
    ) -> Tuple[str, str, str]:
        """
        Adapts a proactive notification for text, voice, and HUD.

        Respects focus mode and notification priority.
        Returns (text, voice, hud) strings.
        """
        state = self.state_manager.get_or_create(session_id)
        return self.channel_adapter.adapt_notification(
            title=title,
            message=message,
            suggestion=suggestion,
            is_focus_active=state.focus_active
        )

    # ─────────────────────────────────────────────────────────────
    # Diagnostics
    # ─────────────────────────────────────────────────────────────

    def get_status(self, session_id: str = "default") -> Dict[str, Any]:
        """Returns non-sensitive diagnostic state for debugging/HUD."""
        profile = self.personality.get_active_profile()
        return {
            "active_profile": profile.name,
            "session": self.state_manager.snapshot(session_id),
            "available_profiles": list(self.personality.list_profiles().keys()),
        }
