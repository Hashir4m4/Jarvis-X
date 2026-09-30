"""
JARVIS DiagnosticsEngine Facade

Central entry point for all diagnostics operations.
Wires together ComponentRegistry, HealthCheckRegistry, DiagnosticEngine,
RecoveryPolicyRegistry, RecoveryExecutor, and ComponentHealthMonitor.

All external callers (DiagnosticSkill, Orchestrator, JarvisCore) use
this facade exclusively.
"""
import asyncio
import logging
import time
from typing import Dict, Any, List, Optional

from .models import (
    HealthStatus, HealthCheckResult, HealthReport,
    DiagnosticReport, RecoveryResult, CheckTrigger
)
from .component_registry import ComponentRegistry
from .health_checks import (
    HealthCheckRegistry,
    NetworkHealthCheck,
    LocalAIHealthCheck,
    CloudAIHealthCheck,
    VoiceInputHealthCheck,
    AudioDeviceHealthCheck,
    WakeWordHealthCheck,
    VoiceOutputHealthCheck,
    VisionHealthCheck,
    KnowledgeBaseHealthCheck,
    MemoryHealthCheck,
    OrchestratorHealthCheck,
    AgentHealthCheck,
    AutomationHealthCheck,
    PermissionSystemHealthCheck,
    HUDHealthCheck,
)
from .diagnostic_engine import DiagnosticEngine
from .recovery_policy import RecoveryPolicyRegistry, RecoveryExecutor
from .health_monitor import ComponentHealthMonitor

logger = logging.getLogger("JARVIS.DiagnosticsEngine")


class DiagnosticsEngine:
    """
    JARVIS Self-Diagnostics, Health Monitoring, and Safe Self-Healing Facade.

    Single entry point for:
    - Component registration and health check wiring
    - Startup diagnostics
    - On-demand and targeted health checks
    - Failure diagnosis with root cause hypotheses
    - Safe recovery execution (permission-checked, attempt-limited)
    - HUD payload generation
    - Voice-friendly health summaries
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        # JARVIS component references (all optional — graceful degradation)
        orchestrator=None,
        voice_manager=None,
        memory_manager=None,
        cloud_manager=None,
        knowledge_base=None,
        agent_registry=None,
        agent_manager=None,
        security_proxy=None,
        execution_engine=None,
        event_bus=None,
    ):
        self.config = config or {}

        # ── Component Registry ─────────────────────────────────────
        self.component_registry = ComponentRegistry()

        # ── Health Check Registry ──────────────────────────────────
        self.health_checks = HealthCheckRegistry()
        self._register_health_checks(
            orchestrator=orchestrator,
            voice_manager=voice_manager,
            memory_manager=memory_manager,
            cloud_manager=cloud_manager,
            knowledge_base=knowledge_base,
            agent_registry=agent_registry,
            agent_manager=agent_manager,
            security_proxy=security_proxy,
            execution_engine=execution_engine,
            event_bus=event_bus,
        )

        # ── Diagnostic Engine ──────────────────────────────────────
        self.diagnostic_engine = DiagnosticEngine(
            component_registry=self.component_registry
        )

        # ── Recovery Policy ────────────────────────────────────────
        self.policy_registry = RecoveryPolicyRegistry()
        self.recovery_executor = RecoveryExecutor(
            policy_registry=self.policy_registry,
            security_proxy=security_proxy,
            components={
                "config": self.config,
                "voice_manager": voice_manager,
                "memory_manager": memory_manager,
                "cloud_manager": cloud_manager,
                "knowledge_base": knowledge_base,
                "agent_registry": agent_registry,
            }
        )

        # ── Health Monitor ─────────────────────────────────────────
        self.health_monitor = ComponentHealthMonitor(
            component_registry=self.component_registry,
            health_check_registry=self.health_checks,
            event_bus=event_bus,
            config=self.config
        )

        logger.info("[DiagnosticsEngine] Initialized.")

    def _register_health_checks(self, **components):
        """Wires component references into health check implementations."""
        orch = components.get("orchestrator")
        vm = components.get("voice_manager")
        mm = components.get("memory_manager")
        cm = components.get("cloud_manager")
        kb = components.get("knowledge_base")
        ar = components.get("agent_registry")
        am = components.get("agent_manager")
        sp = components.get("security_proxy")
        ee = components.get("execution_engine")
        eb = components.get("event_bus")

        checks = [
            NetworkHealthCheck(),
            LocalAIHealthCheck(config=self.config),
            CloudAIHealthCheck(cloud_manager=cm),
            AudioDeviceHealthCheck(),
            VoiceInputHealthCheck(voice_manager=vm),
            WakeWordHealthCheck(voice_manager=vm),
            VoiceOutputHealthCheck(voice_manager=vm),
            VisionHealthCheck(),
            KnowledgeBaseHealthCheck(knowledge_base=kb, config=self.config),
            MemoryHealthCheck(memory_manager=mm),
            OrchestratorHealthCheck(orchestrator=orch),
            AgentHealthCheck(agent_registry=ar, agent_manager=am),
            AutomationHealthCheck(security_proxy=sp, execution_engine=ee),
            PermissionSystemHealthCheck(security_proxy=sp),
            HUDHealthCheck(event_bus=eb),
        ]

        for check in checks:
            self.health_checks.register(check)

        logger.debug(f"[DiagnosticsEngine] Registered {len(checks)} health checks.")

    # ── Startup ────────────────────────────────────────────────────

    async def run_startup_diagnostics(self) -> HealthReport:
        """
        Runs health checks on all components at startup.
        Non-critical failures do not block operation.
        Returns a HealthReport.
        """
        report = await self.health_monitor.run_startup_diagnostics(
            critical_only=False,
            trigger=CheckTrigger.STARTUP
        )
        logger.info(
            f"[DiagnosticsEngine] Startup: {report.healthy_count()}/{len(report.results)} "
            f"healthy. Overall: {report.overall_status.value}"
        )
        return report

    # ── Check Operations ───────────────────────────────────────────

    async def check_component(
        self,
        component_id: str,
        trigger: CheckTrigger = CheckTrigger.ON_DEMAND
    ) -> Optional[HealthCheckResult]:
        """Runs a targeted health check on one component."""
        return await self.health_monitor.check_component(component_id, trigger=trigger)

    async def check_all(
        self,
        trigger: CheckTrigger = CheckTrigger.ON_DEMAND
    ) -> HealthReport:
        """Runs health checks on all registered components."""
        return await self.health_monitor.check_all(trigger=trigger)

    # ── Diagnosis ──────────────────────────────────────────────────

    async def diagnose(self, component_id: str) -> DiagnosticReport:
        """
        Runs a health check then produces a full diagnostic report.

        Steps:
        1. Run targeted health check
        2. Update registry
        3. Inspect dependency chain
        4. Generate hypotheses
        5. Return DiagnosticReport
        """
        result = await self.check_component(component_id)
        if not result:
            # Component not registered or no health check available
            from .models import DiagnosticReport, FailureClass
            return DiagnosticReport(
                component_id=component_id,
                component_name=component_id.replace("_", " ").title(),
                failure_class=FailureClass.UNKNOWN,
                narrative=f"Component '{component_id}' is not registered in the diagnostics system.",
                voice_summary=f"I don't have a health check registered for {component_id.replace('_', ' ')}."
            )

        return self.diagnostic_engine.diagnose(component_id, result)

    # ── Recovery ───────────────────────────────────────────────────

    async def attempt_recovery(
        self,
        component_id: str,
        action_id: Optional[str] = None,
        confirm_granted: bool = False
    ) -> RecoveryResult:
        """
        Attempts recovery for a component.

        If action_id is specified, attempts that action.
        Otherwise, tries the first available LEVEL_1 action.
        """
        if action_id:
            return await self._attempt_action(action_id, confirm_granted, component_id)

        # Auto-select best available LEVEL_1 action
        from .models import RecoveryLevel
        actions = self.policy_registry.get_actions_for_component(
            component_id,
            max_level=RecoveryLevel.LEVEL_1_SAFE_AUTO
        )
        if not actions:
            return RecoveryResult(
                action_id="none",
                component_id=component_id,
                success=False,
                message=(
                    f"No automatic recovery actions are registered for '{component_id}'. "
                    f"Manual intervention may be required."
                ),
                requires_user_action=True,
                user_guidance=f"Please check '{component_id}' manually."
            )

        for action in actions:
            result = await self._attempt_action(action.action_id, False, component_id)
            if result.success:
                return result

        return RecoveryResult(
            action_id="auto",
            component_id=component_id,
            success=False,
            message=f"All automatic recovery actions for '{component_id}' were attempted without success.",
            requires_user_action=True,
            user_guidance=f"Automatic recovery exhausted for '{component_id}'. Please inspect manually."
        )

    async def _attempt_action(
        self,
        action_id: str,
        confirm_granted: bool,
        component_id: str
    ) -> RecoveryResult:
        """Runs a specific recovery action with health check verification."""
        async def verify() -> HealthStatus:
            result = await self.check_component(component_id)
            return result.status if result else HealthStatus.UNKNOWN

        return await self.recovery_executor.attempt(
            action_id=action_id,
            confirm_granted=confirm_granted,
            health_check_fn=verify
        )

    # ── Summaries ──────────────────────────────────────────────────

    async def get_health_summary(self) -> str:
        """Returns a voice-friendly system health summary."""
        report = await self.check_all(trigger=CheckTrigger.ON_DEMAND)
        return report.to_voice_summary()

    def get_hud_payload(self) -> Dict[str, Any]:
        """Returns a compact HUD payload with current component statuses."""
        return self.health_monitor.get_hud_payload()

    def get_component_list(self) -> List[Dict[str, Any]]:
        """Returns all registered component descriptors."""
        return [r.to_dict() for r in self.component_registry.get_all().values()]

    # ── EventBus Wiring ────────────────────────────────────────────

    async def start(self):
        """Starts event subscriptions for proactive health monitoring."""
        await self.health_monitor.start()

    async def stop(self):
        """Stops health monitoring."""
        await self.health_monitor.stop()
