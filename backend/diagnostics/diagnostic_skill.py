"""
JARVIS Diagnostic Skill

Exposes the Self-Diagnostics system to the JARVIS Orchestrator and Skill Registry.

Supported user queries:
- "Are all systems operational?"
- "Run a diagnostic."
- "Check JARVIS health."
- "Check the AI model."
- "Why is voice unavailable?"
- "Diagnose the knowledge base."
- "Check all components."
- "Fix the local model connection."

Design:
- Routes all actions through DiagnosticsEngine (never bypasses it)
- All recovery actions go through RecoveryExecutor permission gates
- Output is channel-adapted via the Personality/Interaction system
- Never exposes stack traces, API keys, or internal error details
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional

from backend.skills.base_skill import BaseSkill
from backend.core.models import Intent, SkillResult, UserInput
from backend.diagnostics.models import HealthStatus

logger = logging.getLogger("JARVIS.DiagnosticSkill")

# Natural language → component_id mapping
_COMPONENT_ALIASES: Dict[str, str] = {
    "ai": "local_ai",
    "local ai": "local_ai",
    "local model": "local_ai",
    "ollama": "local_ai",
    "model": "local_ai",
    "cloud ai": "cloud_ai",
    "cloud model": "cloud_ai",
    "voice": "voice_input",
    "speech": "voice_input",
    "microphone": "audio_device",
    "mic": "audio_device",
    "wake word": "wake_word",
    "tts": "voice_output",
    "text to speech": "voice_output",
    "vision": "vision",
    "screen": "vision",
    "ocr": "vision",
    "browser": "browser",
    "knowledge": "knowledge_base",
    "knowledge base": "knowledge_base",
    "rag": "knowledge_base",
    "memory": "memory",
    "agents": "agents",
    "automation": "automation",
    "desktop": "automation",
    "hud": "hud",
    "network": "network",
    "internet": "network",
    "permissions": "permission_system",
    "security": "permission_system",
    "orchestrator": "core_orchestrator",
}


def _resolve_component(user_text: str) -> Optional[str]:
    """Resolves natural language to a component_id."""
    lower = user_text.lower()
    for alias, cid in _COMPONENT_ALIASES.items():
        if alias in lower:
            return cid
    return None


class DiagnosticSkill(BaseSkill):
    """
    JARVIS self-diagnostics skill.

    Provides structured, user-facing health reports, diagnostic analysis,
    and safe self-healing actions.
    """

    def __init__(self, diagnostics_engine=None):
        super().__init__()
        self._engine = diagnostics_engine

    @property
    def name(self) -> str:
        return "diagnostics"

    @property
    def description(self) -> str:
        return (
            "Checks system health, diagnoses failures, and attempts safe recovery. "
            "Handles: 'Are all systems operational?', 'Diagnose local AI', 'Fix voice recognition'."
        )

    @property
    def supported_actions(self) -> List[str]:
        return [
            "system_health_check",
            "component_diagnostic",
            "run_recovery",
            "health_summary",
        ]

    def match_custom_intent(self, user_input: UserInput) -> Optional[Intent]:
        """Intercepts natural language health/diagnostic queries."""
        text = user_input.content.lower()

        # All systems check
        if any(p in text for p in [
            "all systems", "systems operational", "system status",
            "jarvis health", "check health", "how are you doing",
            "status report", "run diagnostic", "full diagnostic",
            "check all", "everything working"
        ]):
            return Intent(
                intent_type="diagnostics",
                skill_name="diagnostics",
                action="system_health_check",
                confidence=0.95,
                raw_input=user_input.content
            )

        # Component-specific diagnostic
        if any(p in text for p in [
            "diagnose", "why is", "what's wrong with", "check the",
            "why isn't", "why won't", "not working", "unavailable",
            "not responding", "not connecting", "broken", "failed"
        ]):
            component_id = _resolve_component(text)
            return Intent(
                intent_type="diagnostics",
                skill_name="diagnostics",
                action="component_diagnostic",
                confidence=0.88,
                parameters={"component_id": component_id or "local_ai"},
                raw_input=user_input.content
            )

        # Recovery / fix
        if any(p in text for p in [
            "fix", "repair", "recover", "restart", "reconnect",
            "try again", "retry", "reinitialize", "restore"
        ]):
            component_id = _resolve_component(text)
            return Intent(
                intent_type="diagnostics",
                skill_name="diagnostics",
                action="run_recovery",
                confidence=0.85,
                parameters={"component_id": component_id or "local_ai"},
                raw_input=user_input.content
            )

        # Voice summary
        if any(p in text for p in ["health summary", "brief status", "quick status"]):
            return Intent(
                intent_type="diagnostics",
                skill_name="diagnostics",
                action="health_summary",
                confidence=0.90,
                raw_input=user_input.content
            )

        return None

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        """Synchronous dispatch — schedules async execution and blocks briefly."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an async context — create a task and return pending
                # In practice, the Orchestrator will call execute_async if available
                import concurrent.futures
                future = asyncio.ensure_future(self._execute_async(intent, context))
                # Return a pending result; the orchestrator will await the task
                return SkillResult(
                    success=True,
                    message="Diagnostic running...",
                    output_text="Running system diagnostic...",
                    data={"pending_task": True}
                )
            else:
                return loop.run_until_complete(self._execute_async(intent, context))
        except Exception as e:
            logger.error(f"[DiagnosticSkill] Execute error: {e}", exc_info=True)
            return SkillResult(
                success=False,
                message="Diagnostic failed to run.",
                output_text="I encountered an issue running the diagnostic. Please try again."
            )

    async def execute_async(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        """Async execution path used by orchestrators that support it."""
        return await self._execute_async(intent, context)

    async def _execute_async(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        """Core async execution dispatcher."""
        context = context or {}
        engine = self._engine or context.get("diagnostics_engine")

        if not engine:
            return SkillResult(
                success=False,
                message="Diagnostics system not available.",
                output_text=(
                    "The diagnostics system is not currently available. "
                    "Core systems should still be operational."
                )
            )

        action = intent.action
        params = intent.parameters or {}

        try:
            if action == "system_health_check":
                return await self._system_health_check(engine)
            elif action == "component_diagnostic":
                return await self._component_diagnostic(engine, params, intent.raw_input or "")
            elif action == "run_recovery":
                return await self._run_recovery(engine, params, intent.raw_input or "")
            elif action == "health_summary":
                return await self._health_summary(engine)
            else:
                return await self._system_health_check(engine)
        except Exception as e:
            logger.error(f"[DiagnosticSkill] Action '{action}' error: {e}", exc_info=True)
            return SkillResult(
                success=False,
                message="Diagnostic action failed.",
                output_text="The diagnostic encountered an unexpected issue."
            )

    async def _system_health_check(self, engine) -> SkillResult:
        """Runs a full system health check and formats the report."""
        report = await engine.check_all()

        # Build formatted text report
        lines = ["**JARVIS System Health**", ""]
        for cid, result in report.results.items():
            icon = _status_icon(result.status)
            name = cid.replace("_", " ").title()
            lines.append(f"{icon} **{name}**: {result.status.value}")
            if result.recommended_action and not result.is_healthy():
                lines.append(f"  → {result.recommended_action}")

        lines.append("")
        lines.append(f"**Overall**: {report.overall_status.value}")

        voice = report.to_voice_summary()

        return SkillResult(
            success=True,
            message=f"System health: {report.overall_status.value}",
            output_text="\n".join(lines),
            data={
                "overall_status": report.overall_status.value,
                "hud_payload": report.to_hud_payload(),
                "voice_summary": voice,
                "results": {cid: r.to_dict() for cid, r in report.results.items()}
            }
        )

    async def _component_diagnostic(
        self, engine, params: Dict[str, Any], raw_input: str
    ) -> SkillResult:
        """Runs a targeted diagnostic on a specific component."""
        component_id = params.get("component_id") or _resolve_component(raw_input) or "local_ai"

        report = await engine.diagnose(component_id)

        lines = [
            f"**Diagnostic: {report.component_name}**",
            f"Status: {report.check_result.status.value if report.check_result else 'Unknown'}",
            f"Failure type: {report.failure_class.value}",
            ""
        ]

        if report.hypotheses:
            lines.append("**Possible causes:**")
            for i, h in enumerate(report.hypotheses[:3], 1):
                lines.append(f"{i}. [{h.confidence.value}] {h.hypothesis}")
                if h.diagnostic_test:
                    lines.append(f"   *Diagnostic test:* {h.diagnostic_test}")
            lines.append("")

        if report.recovery_options:
            actions = self._format_recovery_options(report.recovery_options, engine)
            if actions:
                lines.append(f"**Available recovery:** {actions}")

        return SkillResult(
            success=True,
            message=f"Diagnostic complete for {report.component_name}",
            output_text="\n".join(lines),
            data={
                "report": report.to_dict(),
                "voice_summary": report.voice_summary
            }
        )

    async def _run_recovery(
        self, engine, params: Dict[str, Any], raw_input: str
    ) -> SkillResult:
        """Attempts recovery for a component."""
        component_id = params.get("component_id") or _resolve_component(raw_input) or "local_ai"
        action_id = params.get("action_id")
        confirm = params.get("confirm_granted", False)

        result = await engine.attempt_recovery(
            component_id=component_id,
            action_id=action_id,
            confirm_granted=confirm
        )

        if result.requires_user_action and not result.limit_reached:
            # Confirmation required — surface the request
            return SkillResult(
                success=True,
                message="Confirmation required",
                output_text=(
                    f"To attempt recovery for {component_id.replace('_', ' ')}, "
                    f"I need your approval: {result.user_guidance}"
                ),
                data={"recovery_result": result.to_dict(), "awaiting_confirmation": True}
            )

        if result.limit_reached:
            return SkillResult(
                success=False,
                message="Recovery limit reached",
                output_text=(
                    f"Automatic recovery attempts for {component_id.replace('_', ' ')} have been exhausted. "
                    f"{result.user_guidance}"
                ),
                data={"recovery_result": result.to_dict()}
            )

        if result.success:
            return SkillResult(
                success=True,
                message=f"Recovery successful for {component_id}",
                output_text=f"{result.message} {component_id.replace('_', ' ').title()} is now {result.verification_status.value.lower()}.",
                data={"recovery_result": result.to_dict()}
            )

        return SkillResult(
            success=False,
            message=f"Recovery did not succeed for {component_id}",
            output_text=f"{result.message}",
            data={"recovery_result": result.to_dict()}
        )

    async def _health_summary(self, engine) -> SkillResult:
        """Returns a voice-optimized health summary."""
        summary = await engine.get_health_summary()
        return SkillResult(
            success=True,
            message="Health summary",
            output_text=summary,
            data={"hud_payload": engine.get_hud_payload()}
        )

    @staticmethod
    def _format_recovery_options(action_ids: List[str], engine) -> str:
        """Formats available recovery actions as a readable list."""
        actions = []
        for aid in action_ids[:3]:
            action = engine.policy_registry.get_action(aid)
            if action:
                actions.append(f"'{action.description}'")
        return "; ".join(actions)


def _status_icon(status: HealthStatus) -> str:
    """Returns a text icon for a health status."""
    return {
        HealthStatus.HEALTHY: "●",
        HealthStatus.DEGRADED: "▲",
        HealthStatus.UNAVAILABLE: "✗",
        HealthStatus.FAILING: "✗",
        HealthStatus.RECOVERING: "↺",
        HealthStatus.UNKNOWN: "?",
        HealthStatus.DISABLED: "○",
    }.get(status, "?")
