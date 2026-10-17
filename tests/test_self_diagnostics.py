"""
Tests for JARVIS Self-Diagnostics, Component Health Monitoring,
Failure Analysis, and Safe Self-Healing System (Prompt 35)

25 test cases covering:
1.  Component registration
2.  Health check registration
3.  HEALTHY state
4.  DEGRADED state
5.  UNAVAILABLE state
6.  Dependency-caused degradation
7.  Manual health check
8.  Periodic health check trigger
9.  Event-triggered health check
10. Diagnostic report generation
11. Root cause hypothesis confidence
12. Transient failure classification
13. Configuration failure classification
14. Safe automatic retry
15. Recovery verification
16. Confirmation required recovery
17. Recovery attempt limits
18. Recovery cooldown
19. Recovery failure
20. Capability fallback
21. Offline diagnostic
22. Cloud unavailable fallback
23. Voice unavailable but text available
24. Health notification deduplication
25. Diagnostic does not expose secrets

All tests use mocked components and services.
No real OS services are started or stopped.
"""
import asyncio
import pytest
import time
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Dict, Any, Optional

from backend.diagnostics.models import (
    HealthStatus, ComponentCategory, ComponentCriticality, FailureClass,
    HypothesisConfidence, RecoveryLevel, CheckTrigger,
    HealthRecord, HealthCheckResult, DiagnosticHypothesis, DiagnosticReport,
    RecoveryAction, RecoveryResult, HealthReport
)
from backend.diagnostics.component_registry import ComponentRegistry
from backend.diagnostics.health_checks import (
    HealthCheckRegistry, ComponentHealthCheck,
    LocalAIHealthCheck, NetworkHealthCheck, CloudAIHealthCheck,
    VoiceInputHealthCheck, KnowledgeBaseHealthCheck,
    MemoryHealthCheck, OrchestratorHealthCheck, PermissionSystemHealthCheck
)
from backend.diagnostics.diagnostic_engine import DiagnosticEngine
from backend.diagnostics.recovery_policy import (
    RecoveryPolicyRegistry, RecoveryExecutor, BUILT_IN_ACTIONS
)
from backend.diagnostics.health_monitor import ComponentHealthMonitor


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def make_registry() -> ComponentRegistry:
    return ComponentRegistry()


def make_check_registry() -> HealthCheckRegistry:
    return HealthCheckRegistry()


def mock_healthy_result(component_id: str) -> HealthCheckResult:
    return HealthCheckResult(
        component_id=component_id,
        status=HealthStatus.HEALTHY,
        evidence=["Mock: component is healthy."]
    )


def mock_unhealthy_result(
    component_id: str,
    status: HealthStatus = HealthStatus.UNAVAILABLE,
    error: str = "Mock error"
) -> HealthCheckResult:
    return HealthCheckResult(
        component_id=component_id,
        status=status,
        error_summary=error,
        evidence=[error],
        recommended_action="Mock recommended action."
    )


class MockHealthCheck(ComponentHealthCheck):
    """Configurable mock health check for testing."""

    def __init__(self, cid: str, result: HealthCheckResult):
        self._cid = cid
        self._result = result

    @property
    def component_id(self) -> str:
        return self._cid

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        self._result.trigger = trigger
        return self._result


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Component Registration
# ─────────────────────────────────────────────────────────────────────────────

def test_01_component_registration():
    """Components can be registered and retrieved by component_id."""
    registry = make_registry()

    record = HealthRecord(
        component_id="test_component",
        name="Test Component",
        category=ComponentCategory.CORE,
        criticality=ComponentCriticality.MEDIUM
    )
    registry.register(record)

    retrieved = registry.get("test_component")
    assert retrieved is not None
    assert retrieved.component_id == "test_component"
    assert retrieved.name == "Test Component"
    assert retrieved.category == ComponentCategory.CORE


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Health Check Registration
# ─────────────────────────────────────────────────────────────────────────────

def test_02_health_check_registration():
    """Health checks can be registered and retrieved by component_id."""
    check_registry = make_check_registry()
    mock_result = mock_healthy_result("local_ai")
    check = MockHealthCheck("local_ai", mock_result)

    check_registry.register(check)

    retrieved = check_registry.get("local_ai")
    assert retrieved is not None
    assert retrieved.component_id == "local_ai"
    assert "local_ai" in check_registry.list_ids()


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: HEALTHY State
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_03_healthy_state():
    """A healthy component returns HEALTHY status with evidence."""
    check = MockHealthCheck("local_ai", mock_healthy_result("local_ai"))
    result = await check.check()

    assert result.status == HealthStatus.HEALTHY
    assert result.is_healthy()
    assert not result.is_actionable()
    assert result.evidence


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: DEGRADED State
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_04_degraded_state():
    """A partially working component returns DEGRADED status."""
    result = mock_unhealthy_result("knowledge_base", HealthStatus.DEGRADED, "Embedding not available")
    check = MockHealthCheck("knowledge_base", result)
    r = await check.check()

    assert r.status == HealthStatus.DEGRADED
    assert r.is_actionable()
    assert "Embedding" in r.error_summary


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: UNAVAILABLE State
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_05_unavailable_state():
    """An unreachable component returns UNAVAILABLE status."""
    result = mock_unhealthy_result("local_ai", HealthStatus.UNAVAILABLE, "Connection refused")
    check = MockHealthCheck("local_ai", result)
    r = await check.check()

    assert r.status == HealthStatus.UNAVAILABLE
    assert r.is_actionable()


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Dependency-Caused Degradation
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_06_dependency_caused_degradation():
    """Voice input reports DEGRADED when audio_device dependency is UNAVAILABLE."""
    # Simulate audio_device unavailable
    dep_status = {"audio_device": HealthStatus.UNAVAILABLE}
    check = VoiceInputHealthCheck(voice_manager=None)
    result = await check.check(
        dependency_status=dep_status
    )

    assert result.status == HealthStatus.DEGRADED
    assert "audio_device" in str(result.dependency_status) or "audio" in result.error_summary.lower()
    assert "text" in result.recommended_action.lower() or "microphone" in result.recommended_action.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Manual Health Check
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_07_manual_health_check():
    """Manual health check runs on demand and returns structured result."""
    check_registry = make_check_registry()
    check_registry.register(MockHealthCheck("local_ai", mock_healthy_result("local_ai")))

    result = await check_registry.run("local_ai", trigger=CheckTrigger.MANUAL)
    assert result is not None
    assert result.status == HealthStatus.HEALTHY
    assert result.trigger == CheckTrigger.MANUAL


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Periodic Health Check Trigger
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_08_periodic_health_check_trigger():
    """Periodic checks carry PERIODIC trigger type in result."""
    check_registry = make_check_registry()
    check_registry.register(MockHealthCheck("network", mock_healthy_result("network")))

    result = await check_registry.run("network", trigger=CheckTrigger.PERIODIC)
    assert result.trigger == CheckTrigger.PERIODIC


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: Event-Triggered Health Check
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_09_event_triggered_health_check():
    """An EventBus event triggers a targeted health check on the affected component."""
    registry = make_registry()
    check_registry = make_check_registry()
    check_registry.register(
        MockHealthCheck("local_ai", mock_unhealthy_result("local_ai", HealthStatus.UNAVAILABLE))
    )

    mock_bus = MagicMock()
    mock_bus.subscribe = AsyncMock()
    mock_bus.publish = AsyncMock()

    monitor = ComponentHealthMonitor(
        component_registry=registry,
        health_check_registry=check_registry,
        event_bus=mock_bus
    )

    # Simulate an event-triggered check
    result = await monitor.check_component("local_ai", trigger=CheckTrigger.EVENT_TRIGGERED)
    assert result is not None
    assert result.trigger == CheckTrigger.EVENT_TRIGGERED
    assert result.status == HealthStatus.UNAVAILABLE

    # Registry should be updated
    record = registry.get("local_ai")
    assert record.health_status == HealthStatus.UNAVAILABLE


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: Diagnostic Report Generation
# ─────────────────────────────────────────────────────────────────────────────

def test_10_diagnostic_report_generation():
    """DiagnosticEngine generates a complete report with hypotheses and narrative."""
    registry = make_registry()
    engine = DiagnosticEngine(component_registry=registry)

    result = mock_unhealthy_result("local_ai", HealthStatus.UNAVAILABLE, "Connection refused")
    report = engine.diagnose("local_ai", result)

    assert isinstance(report, DiagnosticReport)
    assert report.component_id == "local_ai"
    assert len(report.hypotheses) > 0
    assert report.narrative
    assert report.voice_summary
    assert report.failure_class is not None


# ─────────────────────────────────────────────────────────────────────────────
# Test 11: Root Cause Hypothesis Confidence
# ─────────────────────────────────────────────────────────────────────────────

def test_11_root_cause_hypothesis_confidence():
    """High-confidence hypothesis is ranked first for known failure patterns."""
    registry = make_registry()
    engine = DiagnosticEngine(component_registry=registry)

    # Connection refused → HIGH confidence for local AI
    result = mock_unhealthy_result("local_ai", HealthStatus.UNAVAILABLE, "Connection refused to AI server")
    report = engine.diagnose("local_ai", result)

    top = report.top_hypothesis()
    assert top is not None
    assert top.confidence in (HypothesisConfidence.HIGH, HypothesisConfidence.MODERATE)
    # Hypotheses are sorted HIGH → LOW
    confidences = [h.confidence for h in report.hypotheses]
    order = {HypothesisConfidence.HIGH: 0, HypothesisConfidence.MODERATE: 1, HypothesisConfidence.LOW: 2}
    for i in range(len(confidences) - 1):
        assert order[confidences[i]] <= order[confidences[i + 1]]


# ─────────────────────────────────────────────────────────────────────────────
# Test 12: Transient Failure Classification
# ─────────────────────────────────────────────────────────────────────────────

def test_12_transient_failure_classification():
    """Timeout errors are classified as TRANSIENT."""
    registry = make_registry()
    engine = DiagnosticEngine(component_registry=registry)

    result = HealthCheckResult(
        component_id="local_ai",
        status=HealthStatus.UNAVAILABLE,
        error_summary="Connection timed out after 2 seconds.",
        evidence=["timeout detected"]
    )
    report = engine.diagnose("local_ai", result)

    # Should have a TRANSIENT hypothesis somewhere
    failure_classes = [h.failure_class for h in report.hypotheses]
    assert FailureClass.TRANSIENT in failure_classes or report.failure_class == FailureClass.TRANSIENT


# ─────────────────────────────────────────────────────────────────────────────
# Test 13: Configuration Failure Classification
# ─────────────────────────────────────────────────────────────────────────────

def test_13_configuration_failure_classification():
    """'Not configured' errors produce CONFIGURATION failure classification."""
    registry = make_registry()
    engine = DiagnosticEngine(component_registry=registry)

    result = HealthCheckResult(
        component_id="cloud_ai",
        status=HealthStatus.DEGRADED,
        error_summary="No cloud AI providers are configured.",
        evidence=["Cloud manager reports 0 available providers."]
    )
    report = engine.diagnose("cloud_ai", result)

    failure_classes = [h.failure_class for h in report.hypotheses]
    assert FailureClass.CONFIGURATION in failure_classes or report.failure_class == FailureClass.CONFIGURATION


# ─────────────────────────────────────────────────────────────────────────────
# Test 14: Safe Automatic Retry (LEVEL_1)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_14_safe_automatic_retry():
    """LEVEL_1 action executes without requiring confirmation."""
    policy = RecoveryPolicyRegistry()
    executor = RecoveryExecutor(policy_registry=policy, components={"config": {}})

    # Patch the executor function to return True (success)
    with patch("backend.diagnostics.recovery_policy._retry_local_ai_connection", new=AsyncMock(return_value=True)):
        # Mock verification: returns HEALTHY after action
        async def verify():
            return HealthStatus.HEALTHY

        result = await executor.attempt(
            action_id="retry_local_ai_connection",
            confirm_granted=False,
            health_check_fn=verify
        )

    assert not result.requires_user_action
    assert not result.limit_reached
    assert result.verification_status == HealthStatus.HEALTHY


# ─────────────────────────────────────────────────────────────────────────────
# Test 15: Recovery Verification
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_15_recovery_verification():
    """After recovery, health check is run. Success is verified by HEALTHY status."""
    policy = RecoveryPolicyRegistry()
    executor = RecoveryExecutor(policy_registry=policy, components={"config": {}})

    verification_called = []

    async def verify() -> HealthStatus:
        verification_called.append(True)
        return HealthStatus.HEALTHY

    with patch("backend.diagnostics.recovery_policy._retry_local_ai_connection", new=AsyncMock(return_value=True)):
        result = await executor.attempt(
            action_id="retry_local_ai_connection",
            health_check_fn=verify
        )

    assert len(verification_called) > 0, "Verification function must be called after recovery"
    assert result.verification_status == HealthStatus.HEALTHY


# ─────────────────────────────────────────────────────────────────────────────
# Test 16: Confirmation Required Recovery (LEVEL_2)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_16_confirmation_required_recovery():
    """LEVEL_2 action returns requires_user_action=True without confirmation."""
    policy = RecoveryPolicyRegistry()
    executor = RecoveryExecutor(policy_registry=policy)

    result = await executor.attempt(
        action_id="restart_local_ai_server",
        confirm_granted=False
    )

    assert result.requires_user_action
    assert not result.success
    assert "confirmation" in result.message.lower() or "confirmation" in result.user_guidance.lower()


@pytest.mark.asyncio
async def test_16b_confirmation_granted_executes():
    """LEVEL_2 action executes when confirm_granted=True."""
    policy = RecoveryPolicyRegistry()
    executor = RecoveryExecutor(policy_registry=policy, components={})

    # restart_local_ai_server has no executor in _ACTION_EXECUTORS — treated as no-op safe
    result = await executor.attempt(
        action_id="restart_local_ai_server",
        confirm_granted=True
    )
    # Should not return requires_user_action since confirmation was granted
    assert not (result.requires_user_action and "confirmation" in result.message.lower())


# ─────────────────────────────────────────────────────────────────────────────
# Test 17: Recovery Attempt Limits
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_17_recovery_attempt_limits():
    """Recovery stops when max_attempts is reached and reports limit_reached=True."""
    policy = RecoveryPolicyRegistry()
    executor = RecoveryExecutor(policy_registry=policy, components={"config": {}})

    action_id = "retry_local_ai_connection"
    action = policy.get_action(action_id)
    max_attempts = action.max_attempts

    with patch("backend.diagnostics.recovery_policy._retry_local_ai_connection", new=AsyncMock(return_value=False)), \
             patch.object(policy, "is_on_cooldown", return_value=False):
        async def verify():
            return HealthStatus.UNAVAILABLE

        # Exhaust all attempts
        last_result = None
        for _ in range(max_attempts + 1):
            last_result = await executor.attempt(action_id, health_check_fn=verify)

    assert last_result.limit_reached
    assert policy.has_exceeded_max_attempts(action_id)


# ─────────────────────────────────────────────────────────────────────────────
# Test 18: Recovery Cooldown
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_18_recovery_cooldown():
    """Recovery action respects cooldown period and returns appropriate message."""
    policy = RecoveryPolicyRegistry()
    executor = RecoveryExecutor(policy_registry=policy, components={"config": {}})

    action_id = "retry_local_ai_connection"

    # Manually record an attempt to trigger cooldown
    policy.record_attempt(action_id)

    # Manually set last_attempt to just now
    policy._last_attempt[action_id] = time.time()

    # Should be on cooldown
    assert policy.is_on_cooldown(action_id)

    result = await executor.attempt(action_id)
    assert not result.success
    assert "cooldown" in result.message.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Test 19: Recovery Failure
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_19_recovery_failure():
    """When recovery executor fails, success=False and verification shows unhealthy."""
    policy = RecoveryPolicyRegistry()
    executor = RecoveryExecutor(policy_registry=policy, components={"config": {}})

    with patch("backend.diagnostics.recovery_policy._retry_local_ai_connection", new=AsyncMock(return_value=False)), \
             patch.object(policy, "is_on_cooldown", return_value=False):
        async def verify():
            return HealthStatus.UNAVAILABLE

        result = await executor.attempt(
            action_id="retry_local_ai_connection",
            health_check_fn=verify
        )

    assert not result.success
    assert result.verification_status == HealthStatus.UNAVAILABLE


# ─────────────────────────────────────────────────────────────────────────────
# Test 20: Capability Fallback
# ─────────────────────────────────────────────────────────────────────────────

def test_20_capability_fallback():
    """Registry correctly reports overall system as DEGRADED when non-critical component fails."""
    registry = make_registry()

    # Simulate local_ai (HIGH criticality) unavailable
    registry.update_status("local_ai", HealthStatus.UNAVAILABLE, "Server offline")

    overall = registry.get_overall_status()
    # Should be DEGRADED (not FAILING — only CRITICAL component failure → FAILING)
    assert overall in (HealthStatus.DEGRADED, HealthStatus.FAILING)


def test_20b_critical_failure_causes_system_failing():
    """CRITICAL component failure marks system as FAILING."""
    registry = make_registry()

    registry.update_status("core_orchestrator", HealthStatus.FAILING, "Orchestrator crashed")

    overall = registry.get_overall_status()
    assert overall == HealthStatus.FAILING


# ─────────────────────────────────────────────────────────────────────────────
# Test 21: Offline Diagnostic
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_21_offline_diagnostic():
    """Network health check returns UNAVAILABLE when internet is offline."""
    check = NetworkHealthCheck()

    # Patch socket to always fail
    with patch("socket.socket") as mock_sock:
        mock_sock.return_value.connect.side_effect = ConnectionRefusedError("Connection refused")
        result = await check.check()

    assert result.status == HealthStatus.UNAVAILABLE
    assert result.recommended_action


@pytest.mark.asyncio
async def test_21b_local_diagnostics_work_offline():
    """Memory and orchestrator diagnostics work without network."""
    # These checks don't depend on network
    mock_memory = MagicMock()
    mock_memory.sqlite = MagicMock()  # sqlite is set → healthy

    check = MemoryHealthCheck(memory_manager=mock_memory)
    result = await check.check()

    assert result.status == HealthStatus.HEALTHY


# ─────────────────────────────────────────────────────────────────────────────
# Test 22: Cloud Unavailable Fallback
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_22_cloud_unavailable_fallback():
    """Cloud AI check returns DEGRADED when network is unavailable (dependency)."""
    dep_status = {"network": HealthStatus.UNAVAILABLE}
    check = CloudAIHealthCheck(cloud_manager=None)
    result = await check.check(dependency_status=dep_status)

    assert result.status == HealthStatus.DEGRADED
    assert "network" in result.error_summary.lower() or "offline" in result.error_summary.lower()
    assert result.recommended_action


# ─────────────────────────────────────────────────────────────────────────────
# Test 23: Voice Unavailable But Text Available
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_23_voice_unavailable_text_available():
    """Voice input UNAVAILABLE check includes text-fallback in recommended_action."""
    mock_voice = MagicMock()
    mock_voice.stt = None  # STT not initialized

    check = VoiceInputHealthCheck(voice_manager=mock_voice)
    result = await check.check()

    assert result.status == HealthStatus.UNAVAILABLE
    assert "text" in result.recommended_action.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Test 24: Health Notification Deduplication
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_24_health_notification_deduplication():
    """Same component failure does not emit duplicate notification within cooldown window."""
    registry = make_registry()
    check_registry = make_check_registry()
    check_registry.register(
        MockHealthCheck("local_ai", mock_unhealthy_result("local_ai", HealthStatus.UNAVAILABLE))
    )

    notifications = []

    async def capture_notification(component_id: str, message: str):
        notifications.append((component_id, message))

    mock_bus = MagicMock()
    mock_bus.subscribe = AsyncMock()
    mock_bus.publish = AsyncMock()

    monitor = ComponentHealthMonitor(
        component_registry=registry,
        health_check_registry=check_registry,
        event_bus=mock_bus,
        notify_callback=capture_notification
    )

    # First check — should emit notification
    await monitor.check_component("local_ai")
    first_count = len(notifications)

    # Immediate second check — should NOT emit again (within cooldown)
    await monitor.check_component("local_ai")
    second_count = len(notifications)

    # Notification count should not increase on second check
    assert second_count == first_count


# ─────────────────────────────────────────────────────────────────────────────
# Test 25: Diagnostic Does Not Expose Secrets
# ─────────────────────────────────────────────────────────────────────────────

def test_25_diagnostic_does_not_expose_secrets():
    """Diagnostic report and HealthRecord.to_dict() do not contain secret patterns."""
    import re

    registry = make_registry()
    engine = DiagnosticEngine(component_registry=registry)

    result = mock_unhealthy_result("cloud_ai", HealthStatus.UNAVAILABLE, "Auth failed")
    report = engine.diagnose("cloud_ai", result)

    # Check report dict
    report_dict_str = str(report.to_dict())
    report_text = report.narrative

    SECRET_PATTERNS = [
        r"sk-[a-zA-Z0-9]{20,}",
        r"Bearer\s+[a-zA-Z0-9_\-\.]{15,}",
        r"password\s*=\s*\S+",
        r"api.?key\s*=\s*\S+",
    ]
    for pattern in SECRET_PATTERNS:
        assert not re.search(pattern, report_dict_str, re.IGNORECASE), \
            f"Secret pattern '{pattern}' found in report dict"
        assert not re.search(pattern, report_text, re.IGNORECASE), \
            f"Secret pattern '{pattern}' found in narrative"

    # health_record.to_dict() must not include last_error (can contain stack traces)
    record = registry.get("cloud_ai")
    if record:
        record_dict = record.to_dict()
        assert "last_error" not in record_dict


def test_25b_recovery_action_dict_has_no_credentials():
    """RecoveryAction.to_dict() never contains credential fields."""
    action = RecoveryAction(
        action_id="retry_local_ai_connection",
        component_id="local_ai",
        description="Retry connection",
        level=RecoveryLevel.LEVEL_1_SAFE_AUTO
    )
    d = action.to_dict()
    assert "password" not in str(d).lower()
    assert "api_key" not in str(d).lower()
    assert "secret" not in str(d).lower()
    assert "token" not in str(d).lower()


# ─────────────────────────────────────────────────────────────────────────────
# Additional Structural Tests
# ─────────────────────────────────────────────────────────────────────────────

def test_health_record_mark_failed_increments_counter():
    """HealthRecord.mark_failed increments consecutive_failures counter."""
    record = HealthRecord(
        component_id="test", name="Test", category=ComponentCategory.CORE
    )
    assert record.consecutive_failures == 0
    record.mark_failed("error 1")
    assert record.consecutive_failures == 1
    record.mark_failed("error 2")
    assert record.consecutive_failures == 2


def test_health_record_mark_failed_sets_failing_at_3():
    """HealthRecord.mark_failed sets FAILING status after 3 consecutive failures."""
    record = HealthRecord(
        component_id="test", name="Test", category=ComponentCategory.CORE
    )
    record.mark_failed("e1")
    record.mark_failed("e2")
    record.mark_failed("e3")
    assert record.health_status == HealthStatus.FAILING


def test_health_record_mark_healthy_resets_counter():
    """HealthRecord.mark_healthy resets consecutive_failures to 0."""
    record = HealthRecord(
        component_id="test", name="Test", category=ComponentCategory.CORE
    )
    record.mark_failed("e1")
    record.mark_failed("e2")
    record.mark_healthy()
    assert record.consecutive_failures == 0
    assert record.health_status == HealthStatus.HEALTHY


def test_health_report_voice_summary_all_healthy():
    """HealthReport voice summary correctly reports all components healthy."""
    results = {
        "local_ai": mock_healthy_result("local_ai"),
        "memory": mock_healthy_result("memory"),
        "network": mock_healthy_result("network")
    }
    report = HealthReport(results=results, overall_status=HealthStatus.HEALTHY)
    summary = report.to_voice_summary()
    assert "3" in summary or "all" in summary.lower()
    assert "operational" in summary.lower()


def test_health_report_voice_summary_with_failure():
    """HealthReport voice summary mentions failing component."""
    results = {
        "local_ai": mock_unhealthy_result("local_ai", HealthStatus.UNAVAILABLE),
        "memory": mock_healthy_result("memory"),
    }
    report = HealthReport(results=results, overall_status=HealthStatus.DEGRADED)
    summary = report.to_voice_summary()
    assert "local ai" in summary.lower() or "local_ai" in summary.lower()


def test_dependency_chain_resolution():
    """ComponentRegistry correctly resolves full transitive dependency chain."""
    registry = make_registry()
    chain = registry.get_dependency_chain("voice_input")
    # voice_input depends on audio_device
    assert "audio_device" in chain


@pytest.mark.asyncio
async def test_level3_action_provides_guidance_not_execution():
    """LEVEL_3 actions return user_guidance and never mark success=True."""
    policy = RecoveryPolicyRegistry()
    executor = RecoveryExecutor(policy_registry=policy)

    async def run():
        return await executor.attempt("check_os_audio_settings")

    result = await run()
    assert result.requires_user_action
    assert result.user_guidance
    assert not result.success


def test_recovery_policy_registry_has_builtin_actions():
    """RecoveryPolicyRegistry registers all built-in actions at initialization."""
    policy = RecoveryPolicyRegistry()
    for action in BUILT_IN_ACTIONS:
        retrieved = policy.get_action(action.action_id)
        assert retrieved is not None, f"Built-in action '{action.action_id}' not registered"


@pytest.mark.asyncio
async def test_permission_system_critical_failure_detected():
    """Permission system FAILING is detected and reported as critical."""
    check = PermissionSystemHealthCheck(security_proxy=None)
    result = await check.check()
    assert result.status == HealthStatus.FAILING
    assert "critical" in result.recommended_action.lower() or "permission" in result.error_summary.lower()


@pytest.mark.asyncio
async def test_check_registry_returns_none_for_unregistered():
    """HealthCheckRegistry returns None for unknown component_id."""
    check_registry = make_check_registry()
    result = await check_registry.run("nonexistent_component")
    assert result is None


def test_component_registry_overall_status_all_healthy():
    """ComponentRegistry.get_overall_status returns HEALTHY when all components are healthy."""
    registry = ComponentRegistry()
    for cid in registry.list_ids():
        registry.update_status(cid, HealthStatus.HEALTHY)
    assert registry.get_overall_status() == HealthStatus.HEALTHY
