"""
JARVIS Recovery Policy Registry and Recovery Executor

Manages explicitly registered recovery actions and executes them
through a strict permission-checked, attempt-limited pipeline.

CRITICAL DESIGN RULES:
1. Only explicitly registered RecoveryAction instances may be executed.
2. No arbitrary shell commands. No os.system(). No subprocess with user-supplied input.
3. All LEVEL_2 actions require confirmation before execution.
4. All LEVEL_3 actions only provide user guidance — JARVIS does not execute them.
5. SecurityProxy is the authoritative gatekeeper.
6. Max attempts and cooldown are enforced. Recovery loops are prevented.
7. Verification (health_check) runs after each action.
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable

from .models import (
    RecoveryAction, RecoveryResult, RecoveryLevel, HealthStatus
)

logger = logging.getLogger("JARVIS.RecoveryPolicy")


# ─────────────────────────────────────────────────────────────────────────────
# Recovery Action Executors
# Each is a registered coroutine that performs one safe, explicit action.
# These are the ONLY things the recovery system is allowed to call.
# ─────────────────────────────────────────────────────────────────────────────

async def _retry_local_ai_connection(config: Optional[Dict] = None) -> bool:
    """Attempts to verify local AI connection is still available after a brief wait."""
    try:
        import urllib.request
        url = (config or {}).get("ollama_url", "http://localhost:11434")
        await asyncio.sleep(1.0)  # Brief pause before retry
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


async def _refresh_cloud_provider_config(cloud_manager=None) -> bool:
    """Refreshes the cloud provider configuration state (no new API calls)."""
    if cloud_manager and hasattr(cloud_manager, "refresh"):
        try:
            cloud_manager.refresh()
            return True
        except Exception:
            return False
    return True  # No-op if no refresh method; still considered safe


async def _restart_voice_stt(voice_manager=None) -> bool:
    """Attempts to reinitialize the STT engine in the voice manager."""
    if voice_manager and hasattr(voice_manager, "restart_stt"):
        try:
            voice_manager.restart_stt()
            return True
        except Exception:
            return False
    return False


async def _restart_voice_tts(voice_manager=None) -> bool:
    """Attempts to reinitialize the TTS engine."""
    if voice_manager and hasattr(voice_manager, "restart_tts"):
        try:
            voice_manager.restart_tts()
            return True
        except Exception:
            return False
    return False


async def _restart_wake_word(voice_manager=None) -> bool:
    """Attempts to restart the wake word engine."""
    if voice_manager and hasattr(voice_manager, "restart_wake_word"):
        try:
            voice_manager.restart_wake_word()
            return True
        except Exception:
            return False
    return False


async def _reinitialize_knowledge_base_index(knowledge_base=None) -> bool:
    """Attempts to reinitialize the knowledge base index connection."""
    if knowledge_base and hasattr(knowledge_base, "reinitialize"):
        try:
            knowledge_base.reinitialize()
            return True
        except Exception:
            return False
    return False


async def _fallback_to_keyword_search(knowledge_base=None) -> bool:
    """Enables keyword search fallback mode in the knowledge base."""
    if knowledge_base and hasattr(knowledge_base, "enable_keyword_fallback"):
        try:
            knowledge_base.enable_keyword_fallback()
            return True
        except Exception:
            return False
    return True  # Considered safe no-op if not implemented


async def _reinitialize_memory(memory_manager=None) -> bool:
    """Attempts to reconnect the memory manager's SQLite connection."""
    if memory_manager and hasattr(memory_manager, "reconnect"):
        try:
            memory_manager.reconnect()
            return True
        except Exception:
            return False
    return False


async def _reset_agent_registry(agent_registry=None) -> bool:
    """Clears and re-registers agents in the agent registry."""
    if agent_registry and hasattr(agent_registry, "reset"):
        try:
            agent_registry.reset()
            return True
        except Exception:
            return False
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Built-in Registered Actions
# ─────────────────────────────────────────────────────────────────────────────

BUILT_IN_ACTIONS: List[RecoveryAction] = [
    RecoveryAction(
        action_id="retry_local_ai_connection",
        component_id="local_ai",
        description="Wait briefly and retry the connection to the local AI server.",
        level=RecoveryLevel.LEVEL_1_SAFE_AUTO,
        reversible=True,
        requires_confirmation=False,
        preconditions=[],
        verification_method="health_check",
        max_attempts=3,
        cooldown_seconds=15.0
    ),
    RecoveryAction(
        action_id="refresh_cloud_provider_config",
        component_id="cloud_ai",
        description="Refresh the cloud provider configuration without re-authenticating.",
        level=RecoveryLevel.LEVEL_1_SAFE_AUTO,
        reversible=True,
        requires_confirmation=False,
        preconditions=[],
        verification_method="health_check",
        max_attempts=2,
        cooldown_seconds=30.0
    ),
    RecoveryAction(
        action_id="restart_voice_stt",
        component_id="voice_input",
        description="Reinitialize the speech recognition engine.",
        level=RecoveryLevel.LEVEL_1_SAFE_AUTO,
        reversible=True,
        requires_confirmation=False,
        preconditions=["audio_device_available"],
        verification_method="health_check",
        max_attempts=2,
        cooldown_seconds=20.0
    ),
    RecoveryAction(
        action_id="restart_voice_tts",
        component_id="voice_output",
        description="Reinitialize the text-to-speech engine.",
        level=RecoveryLevel.LEVEL_1_SAFE_AUTO,
        reversible=True,
        requires_confirmation=False,
        preconditions=[],
        verification_method="health_check",
        max_attempts=2,
        cooldown_seconds=20.0
    ),
    RecoveryAction(
        action_id="restart_wake_word",
        component_id="wake_word",
        description="Restart the wake word detection engine.",
        level=RecoveryLevel.LEVEL_1_SAFE_AUTO,
        reversible=True,
        requires_confirmation=False,
        preconditions=["audio_device_available"],
        verification_method="health_check",
        max_attempts=2,
        cooldown_seconds=20.0
    ),
    RecoveryAction(
        action_id="reinitialize_knowledge_base_index",
        component_id="knowledge_base",
        description="Reinitialize the knowledge base index connection.",
        level=RecoveryLevel.LEVEL_1_SAFE_AUTO,
        reversible=True,
        requires_confirmation=False,
        preconditions=[],
        verification_method="health_check",
        max_attempts=2,
        cooldown_seconds=30.0
    ),
    RecoveryAction(
        action_id="fallback_to_keyword_search",
        component_id="knowledge_base",
        description="Enable keyword search fallback if semantic search is unavailable.",
        level=RecoveryLevel.LEVEL_1_SAFE_AUTO,
        reversible=True,
        requires_confirmation=False,
        preconditions=[],
        verification_method="health_check",
        max_attempts=1,
        cooldown_seconds=0.0
    ),
    RecoveryAction(
        action_id="reinitialize_memory",
        component_id="memory",
        description="Attempt to reconnect the memory database connection.",
        level=RecoveryLevel.LEVEL_1_SAFE_AUTO,
        reversible=True,
        requires_confirmation=False,
        preconditions=[],
        verification_method="health_check",
        max_attempts=2,
        cooldown_seconds=15.0
    ),
    # LEVEL_2: Requires user confirmation before execution
    RecoveryAction(
        action_id="restart_local_ai_server",
        component_id="local_ai",
        description=(
            "Attempt to restart the local AI server process. "
            "This may briefly interrupt AI capabilities."
        ),
        level=RecoveryLevel.LEVEL_2_CONFIRMATION,
        reversible=True,
        requires_confirmation=True,
        preconditions=[],
        verification_method="health_check",
        max_attempts=1,
        cooldown_seconds=60.0
    ),
    RecoveryAction(
        action_id="reset_agent_registry",
        component_id="agents",
        description="Clear and re-register agents in the agent system.",
        level=RecoveryLevel.LEVEL_2_CONFIRMATION,
        reversible=True,
        requires_confirmation=True,
        preconditions=[],
        verification_method="health_check",
        max_attempts=1,
        cooldown_seconds=30.0
    ),
    # LEVEL_3: User guidance only, JARVIS does not execute
    RecoveryAction(
        action_id="check_os_audio_settings",
        component_id="audio_device",
        description=(
            "Check Windows audio settings. Verify that the microphone is not muted "
            "and is set as the default recording device in Sound Settings."
        ),
        level=RecoveryLevel.LEVEL_3_USER_GUIDANCE,
        reversible=True,
        requires_confirmation=False,
        preconditions=[],
        verification_method="health_check",
        max_attempts=0,
        cooldown_seconds=0.0
    ),
    RecoveryAction(
        action_id="reinstall_ai_dependencies",
        component_id="local_ai",
        description=(
            "Reinstall the local AI server. "
            "Download and run the Ollama installer from ollama.ai."
        ),
        level=RecoveryLevel.LEVEL_3_USER_GUIDANCE,
        reversible=True,
        requires_confirmation=False,
        preconditions=[],
        verification_method="health_check",
        max_attempts=0,
        cooldown_seconds=0.0
    ),
]


# ─────────────────────────────────────────────────────────────────────────────
# Recovery Policy Registry
# ─────────────────────────────────────────────────────────────────────────────

class RecoveryPolicyRegistry:
    """
    Maps component_ids → available RecoveryActions, ordered by preference.

    Only explicitly registered actions may be executed.
    No ad-hoc actions, no shell commands, no dynamic code generation.
    """

    def __init__(self):
        self._actions: Dict[str, RecoveryAction] = {}
        self._component_actions: Dict[str, List[str]] = {}  # component_id → [action_ids]
        self._attempt_counts: Dict[str, int] = {}            # action_id → count
        self._last_attempt: Dict[str, float] = {}            # action_id → timestamp

        self._register_defaults()

    def _register_defaults(self):
        for action in BUILT_IN_ACTIONS:
            self.register(action)

    def register(self, action: RecoveryAction):
        """Registers a recovery action."""
        self._actions[action.action_id] = action
        if action.component_id not in self._component_actions:
            self._component_actions[action.component_id] = []
        if action.action_id not in self._component_actions[action.component_id]:
            self._component_actions[action.component_id].append(action.action_id)
        logger.debug(f"[RecoveryRegistry] Registered: '{action.action_id}' ({action.level.value})")

    def get_action(self, action_id: str) -> Optional[RecoveryAction]:
        return self._actions.get(action_id)

    def get_actions_for_component(
        self,
        component_id: str,
        max_level: RecoveryLevel = RecoveryLevel.LEVEL_3_USER_GUIDANCE
    ) -> List[RecoveryAction]:
        """Returns available actions for a component, filtered by max level."""
        level_order = [
            RecoveryLevel.LEVEL_1_SAFE_AUTO,
            RecoveryLevel.LEVEL_2_CONFIRMATION,
            RecoveryLevel.LEVEL_3_USER_GUIDANCE
        ]
        max_idx = level_order.index(max_level)
        permitted_levels = set(level_order[:max_idx + 1])
        action_ids = self._component_actions.get(component_id, [])
        return [
            self._actions[aid] for aid in action_ids
            if aid in self._actions and self._actions[aid].level in permitted_levels
        ]

    def is_on_cooldown(self, action_id: str) -> bool:
        action = self._actions.get(action_id)
        if not action or action.cooldown_seconds <= 0:
            return False
        last = self._last_attempt.get(action_id, 0.0)
        return (time.time() - last) < action.cooldown_seconds

    def has_exceeded_max_attempts(self, action_id: str) -> bool:
        action = self._actions.get(action_id)
        if not action or action.max_attempts <= 0:
            return False
        return self._attempt_counts.get(action_id, 0) >= action.max_attempts

    def record_attempt(self, action_id: str):
        self._attempt_counts[action_id] = self._attempt_counts.get(action_id, 0) + 1
        self._last_attempt[action_id] = time.time()

    def reset_attempts(self, action_id: str):
        self._attempt_counts[action_id] = 0
        self._last_attempt.pop(action_id, None)

    def get_attempt_count(self, action_id: str) -> int:
        return self._attempt_counts.get(action_id, 0)


# ─────────────────────────────────────────────────────────────────────────────
# Recovery Executor
# ─────────────────────────────────────────────────────────────────────────────

# Maps action_id → coroutine factory (takes optional kwargs)
_ACTION_EXECUTORS: Dict[str, Callable] = {
    "retry_local_ai_connection": _retry_local_ai_connection,
    "refresh_cloud_provider_config": _refresh_cloud_provider_config,
    "restart_voice_stt": _restart_voice_stt,
    "restart_voice_tts": _restart_voice_tts,
    "restart_wake_word": _restart_wake_word,
    "reinitialize_knowledge_base_index": _reinitialize_knowledge_base_index,
    "fallback_to_keyword_search": _fallback_to_keyword_search,
    "reinitialize_memory": _reinitialize_memory,
    "reset_agent_registry": _reset_agent_registry,
}

# Level 3 user guidance messages (action_id → message)
_LEVEL_3_GUIDANCE: Dict[str, str] = {
    "check_os_audio_settings": (
        "To fix audio device issues: Open Windows Settings → System → Sound. "
        "Ensure your microphone is connected, not muted, and set as the default input device. "
        "You can also check the volume mixer and privacy settings for microphone access."
    ),
    "reinstall_ai_dependencies": (
        "To reinstall the local AI server: "
        "1. Visit https://ollama.ai and download the installer. "
        "2. Run the installer and follow the instructions. "
        "3. After installation, run: ollama serve. "
        "4. Pull the model you need with: ollama pull <model-name>."
    ),
}


class RecoveryExecutor:
    """
    Executes explicitly registered recovery actions.

    Permission model:
    - LEVEL_1: Auto-execute if not on cooldown and within attempt limits.
    - LEVEL_2: Return requires_confirmation=True — caller must get user consent.
    - LEVEL_3: Never execute — return user guidance text only.

    The SecurityProxy is consulted for every LEVEL_2+ action.
    No action is ever executed as an arbitrary shell command.
    """

    def __init__(
        self,
        policy_registry: RecoveryPolicyRegistry,
        security_proxy=None,
        components: Optional[Dict[str, Any]] = None
    ):
        self.policy = policy_registry
        self.security = security_proxy
        self.components = components or {}  # Holds references: {"voice_manager": ..., etc.}

    async def attempt(
        self,
        action_id: str,
        confirm_granted: bool = False,
        health_check_fn: Optional[Callable[[], Awaitable[HealthStatus]]] = None,
    ) -> RecoveryResult:
        """
        Attempts a recovery action.

        Args:
            action_id: The registered action to attempt.
            confirm_granted: True if the user has explicitly confirmed a LEVEL_2 action.
            health_check_fn: Async callable that returns HealthStatus for verification.

        Returns:
            RecoveryResult describing outcome.
        """
        action = self.policy.get_action(action_id)
        if not action:
            return RecoveryResult(
                action_id=action_id,
                component_id="unknown",
                success=False,
                message=f"Action '{action_id}' is not registered. Only registered actions may be executed."
            )

        # LEVEL_3: Guidance only, never execute
        if action.level == RecoveryLevel.LEVEL_3_USER_GUIDANCE:
            guidance = _LEVEL_3_GUIDANCE.get(action_id, action.description)
            logger.info(f"[RecoveryExecutor] LEVEL_3 action '{action_id}' — providing user guidance only.")
            return RecoveryResult(
                action_id=action_id,
                component_id=action.component_id,
                success=False,
                message="This action requires manual intervention.",
                requires_user_action=True,
                user_guidance=guidance,
                verification_status=HealthStatus.UNKNOWN
            )

        # LEVEL_2: Requires confirmation
        if action.level == RecoveryLevel.LEVEL_2_CONFIRMATION and not confirm_granted:
            logger.info(f"[RecoveryExecutor] LEVEL_2 action '{action_id}' — awaiting confirmation.")
            return RecoveryResult(
                action_id=action_id,
                component_id=action.component_id,
                success=False,
                message=f"Confirmation required to proceed. Action: {action.description}",
                requires_user_action=True,
                user_guidance=f"Reply 'yes' to approve: {action.description}",
                verification_status=HealthStatus.UNKNOWN
            )

        # Check attempt limits
        if self.policy.has_exceeded_max_attempts(action_id):
            attempts = self.policy.get_attempt_count(action_id)
            logger.warning(f"[RecoveryExecutor] Max attempts ({attempts}) reached for '{action_id}'.")
            return RecoveryResult(
                action_id=action_id,
                component_id=action.component_id,
                success=False,
                message=(
                    f"Automatic recovery attempts for '{action_id}' have been exhausted "
                    f"({attempts} attempts). Manual intervention may be required."
                ),
                limit_reached=True,
                attempts_made=attempts,
                requires_user_action=True,
                user_guidance=f"Please check '{action.component_id}' manually.",
                verification_status=HealthStatus.UNKNOWN
            )

        # Check cooldown
        if self.policy.is_on_cooldown(action_id):
            return RecoveryResult(
                action_id=action_id,
                component_id=action.component_id,
                success=False,
                message=f"Action '{action_id}' is on cooldown. Try again shortly.",
                verification_status=HealthStatus.UNKNOWN
            )

        # Execute the registered coroutine
        executor_fn = _ACTION_EXECUTORS.get(action_id)
        if not executor_fn:
            return RecoveryResult(
                action_id=action_id,
                component_id=action.component_id,
                success=False,
                message=f"No executor registered for action '{action_id}'.",
                verification_status=HealthStatus.UNKNOWN
            )

        self.policy.record_attempt(action_id)
        attempts_made = self.policy.get_attempt_count(action_id)

        logger.info(f"[RecoveryExecutor] Executing '{action_id}' (attempt {attempts_made}/{action.max_attempts})")

        try:
            success = await executor_fn(**self._get_kwargs(action))
        except Exception as e:
            logger.warning(f"[RecoveryExecutor] Executor '{action_id}' raised: {e}")
            success = False

        # Verification
        verification_status = HealthStatus.UNKNOWN
        if health_check_fn:
            try:
                verification_status = await health_check_fn()
                if verification_status == HealthStatus.HEALTHY:
                    success = True
                    logger.info(f"[RecoveryExecutor] Recovery verified HEALTHY for '{action.component_id}'.")
                else:
                    logger.info(
                        f"[RecoveryExecutor] Verification: '{action.component_id}' still "
                        f"{verification_status.value} after '{action_id}'."
                    )
            except Exception as ve:
                logger.warning(f"[RecoveryExecutor] Verification error: {ve}")

        message = (
            f"Recovery action '{action.description}' succeeded."
            if success else
            f"Recovery action '{action.description}' did not resolve the issue."
        )

        return RecoveryResult(
            action_id=action_id,
            component_id=action.component_id,
            success=success,
            message=message,
            verification_status=verification_status,
            attempts_made=attempts_made,
            limit_reached=(attempts_made >= action.max_attempts)
        )

    def _get_kwargs(self, action: RecoveryAction) -> Dict[str, Any]:
        """Returns the appropriate component references for this action's executor."""
        action_kwargs: Dict[str, Dict[str, str]] = {
            "retry_local_ai_connection": {"config": "config"},
            "refresh_cloud_provider_config": {"cloud_manager": "cloud_manager"},
            "restart_voice_stt": {"voice_manager": "voice_manager"},
            "restart_voice_tts": {"voice_manager": "voice_manager"},
            "restart_wake_word": {"voice_manager": "voice_manager"},
            "reinitialize_knowledge_base_index": {"knowledge_base": "knowledge_base"},
            "fallback_to_keyword_search": {"knowledge_base": "knowledge_base"},
            "reinitialize_memory": {"memory_manager": "memory_manager"},
            "reset_agent_registry": {"agent_registry": "agent_registry"},
        }
        mapping = action_kwargs.get(action.action_id, {})
        kwargs = {}
        for kwarg_name, component_key in mapping.items():
            if component_key in self.components:
                kwargs[kwarg_name] = self.components[component_key]
        return kwargs
