"""
JARVIS Interaction State Manager

Maintains per-session, short-term interaction state.

PRIVACY GUARANTEE:
- State is in-memory only. Never auto-persisted.
- Emotional signals are NOT written to Long-Term Memory.
- Only explicit user preferences may be forwarded to MemoryAPI (by caller, with permission check).
- State is cleared when a session ends.
"""
import logging
import time
from typing import Dict, Optional, Any

from .models import (
    InteractionState, InteractionMode, EmotionalSignal, EmotionalSignalResult
)

logger = logging.getLogger("JARVIS.InteractionStateManager")


class InteractionStateManager:
    """
    Maintains short-term, per-session interaction state.

    State is volatile and lives in Python memory only.
    It accumulates signals across the session to give context to the
    ResponseStrategyEngine without making permanent inferences.
    """

    def __init__(self):
        self._sessions: Dict[str, InteractionState] = {}

    # ── Session Management ────────────────────────────────────────

    def get_or_create(self, session_id: str) -> InteractionState:
        """Returns existing session state or creates a fresh one."""
        if session_id not in self._sessions:
            self._sessions[session_id] = InteractionState(session_id=session_id)
            logger.debug(f"[StateManager] Created new interaction state for session: {session_id}")
        return self._sessions[session_id]

    def clear_session(self, session_id: str):
        """Removes all interaction state for a session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.debug(f"[StateManager] Cleared interaction state for session: {session_id}")

    def clear_all(self):
        """Clears all session states."""
        self._sessions.clear()

    # ── State Updates ─────────────────────────────────────────────

    def update_state(
        self,
        session_id: str,
        user_input: str,
        signal_result: Optional[EmotionalSignalResult] = None,
        task_category: Optional[str] = None,
        active_task_id: Optional[str] = None,
        active_task_context: Optional[str] = None,
    ) -> InteractionState:
        """
        Updates interaction state based on current turn.

        IMPORTANT:
        - Emotional signals are accumulated as counters only.
        - No raw text from emotional states is persisted.
        - State update is non-destructive (merges, does not overwrite context).
        """
        state = self.get_or_create(session_id)
        state.conversation_turn += 1
        state.last_activity = time.time()

        # Update task context if provided
        if active_task_id:
            state.active_task_id = active_task_id
        if active_task_context:
            state.active_task_context = active_task_context

        # Update emotional signal counters
        if signal_result and signal_result.is_actionable():
            state.recent_tone = signal_result.signal

            if signal_result.signal == EmotionalSignal.FRUSTRATED:
                state.frustration_indicators = min(state.frustration_indicators + 1, 10)

            if signal_result.signal == EmotionalSignal.URGENT:
                state.urgency_level = min(state.urgency_level + 1, 2)
            elif signal_result.signal != EmotionalSignal.URGENT and state.urgency_level > 0:
                state.urgency_level = max(state.urgency_level - 1, 0)
        else:
            # Decay toward neutral if no signal detected
            if state.frustration_indicators > 0:
                state.frustration_indicators -= 1
            state.recent_tone = (
                signal_result.signal if signal_result and signal_result.signal != EmotionalSignal.NEUTRAL
                else EmotionalSignal.NEUTRAL
            )

        logger.debug(
            f"[StateManager] Session={session_id} turn={state.conversation_turn} "
            f"tone={state.recent_tone.value} frustration={state.frustration_indicators}"
        )
        return state

    def set_interaction_mode(self, session_id: str, mode: InteractionMode):
        """Sets the active interaction mode (standard / technical / builder / focus / social)."""
        state = self.get_or_create(session_id)
        state.interaction_mode = mode
        state.focus_active = (mode == InteractionMode.FOCUS)
        logger.info(f"[StateManager] Session={session_id} mode → {mode.value}")

    def set_focus_mode(self, session_id: str, active: bool):
        """Toggles focus mode. When active, suppresses low-priority notifications."""
        state = self.get_or_create(session_id)
        state.focus_active = active
        if active:
            state.interaction_mode = InteractionMode.FOCUS
        elif state.interaction_mode == InteractionMode.FOCUS:
            state.interaction_mode = InteractionMode.STANDARD
        logger.info(f"[StateManager] Session={session_id} focus_mode={'ON' if active else 'OFF'}")

    def record_correction(self, session_id: str):
        """Records that the user corrected JARVIS in this session."""
        state = self.get_or_create(session_id)
        state.correction_frequency = min(state.correction_frequency + 1, 20)
        logger.debug(f"[StateManager] Session={session_id} corrections={state.correction_frequency}")

    def clear_task_context(self, session_id: str):
        """Clears the active task context when a task completes or is cancelled."""
        state = self.get_or_create(session_id)
        state.active_task_id = None
        state.active_task_context = None

    def get_frustration_count(self, session_id: str) -> int:
        state = self.get_or_create(session_id)
        return state.frustration_indicators

    def snapshot(self, session_id: str) -> Dict[str, Any]:
        """Returns a non-sensitive summary of interaction state for debugging."""
        state = self.get_or_create(session_id)
        return {
            "session_id": state.session_id,
            "turn": state.conversation_turn,
            "mode": state.interaction_mode.value,
            "tone": state.recent_tone.value,
            "focus": state.focus_active,
            "urgency": state.urgency_level,
            "has_active_task": state.active_task_id is not None
        }
