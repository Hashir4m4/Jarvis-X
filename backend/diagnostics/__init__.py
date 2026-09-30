"""
JARVIS Self-Diagnostics Package

Public API for the Self-Diagnostics, Component Health Monitoring,
Failure Analysis, and Safe Self-Healing System.
"""
from .engine import DiagnosticsEngine
from .models import (
    HealthStatus,
    ComponentCategory,
    ComponentCriticality,
    FailureClass,
    HypothesisConfidence,
    RecoveryLevel,
    CheckTrigger,
    HealthRecord,
    HealthCheckResult,
    DiagnosticHypothesis,
    DiagnosticReport,
    RecoveryAction,
    RecoveryResult,
    HealthReport,
)
from .component_registry import ComponentRegistry
from .health_checks import HealthCheckRegistry, ComponentHealthCheck
from .diagnostic_engine import DiagnosticEngine
from .recovery_policy import RecoveryPolicyRegistry, RecoveryExecutor
from .health_monitor import ComponentHealthMonitor
from .diagnostic_skill import DiagnosticSkill

__all__ = [
    # Facade
    "DiagnosticsEngine",
    # Models
    "HealthStatus",
    "ComponentCategory",
    "ComponentCriticality",
    "FailureClass",
    "HypothesisConfidence",
    "RecoveryLevel",
    "CheckTrigger",
    "HealthRecord",
    "HealthCheckResult",
    "DiagnosticHypothesis",
    "DiagnosticReport",
    "RecoveryAction",
    "RecoveryResult",
    "HealthReport",
    # Registry
    "ComponentRegistry",
    # Health Checks
    "HealthCheckRegistry",
    "ComponentHealthCheck",
    # Diagnostic Engine
    "DiagnosticEngine",
    # Recovery
    "RecoveryPolicyRegistry",
    "RecoveryExecutor",
    # Monitor
    "ComponentHealthMonitor",
    # Skill
    "DiagnosticSkill",
]
