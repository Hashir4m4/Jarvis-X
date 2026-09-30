"""
JARVIS Self-Diagnostics System — Core Data Models

All typed enumerations and dataclasses for the health monitoring,
diagnostic engine, recovery policy, and health reporting system.

Design principles:
- All health states are explicit enums (no magic strings)
- HealthCheckResult always includes latency, error, and recommended_action
- DiagnosticHypothesis always includes confidence tier and evidence
- RecoveryAction always declares risk level and whether confirmation is needed
- Secrets are NEVER stored in any of these structures
"""
import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Core Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class HealthStatus(str, enum.Enum):
    """Standardized component health states."""
    HEALTHY = "HEALTHY"          # Operating normally
    DEGRADED = "DEGRADED"        # Working but limited (e.g., dependency unavailable)
    UNAVAILABLE = "UNAVAILABLE"  # Required service cannot be reached
    FAILING = "FAILING"          # Repeated errors detected
    RECOVERING = "RECOVERING"    # Recovery currently in progress
    UNKNOWN = "UNKNOWN"          # Health cannot be determined
    DISABLED = "DISABLED"        # Component intentionally disabled


class ComponentCategory(str, enum.Enum):
    """Functional category of a registered component."""
    CORE = "CORE"
    AI_MODEL = "AI_MODEL"
    VOICE = "VOICE"
    VISION = "VISION"
    AGENT = "AGENT"
    KNOWLEDGE = "KNOWLEDGE"
    AUTOMATION = "AUTOMATION"
    NETWORK = "NETWORK"
    STORAGE = "STORAGE"
    INTERFACE = "INTERFACE"


class ComponentCriticality(str, enum.Enum):
    """Criticality tier — affects startup behavior and recovery urgency."""
    CRITICAL = "CRITICAL"    # System cannot operate without this
    HIGH = "HIGH"            # Core feature degraded without this
    MEDIUM = "MEDIUM"        # Optional but important capability
    LOW = "LOW"              # Enhancement, nice-to-have


class FailureClass(str, enum.Enum):
    """Classification of failure type — influences recovery policy selection."""
    TRANSIENT = "TRANSIENT"              # Temporary glitch, retry likely helps
    CONFIGURATION = "CONFIGURATION"      # Config file / env var issue
    DEPENDENCY = "DEPENDENCY"            # Upstream service or library unavailable
    RESOURCE = "RESOURCE"                # Memory, disk, or CPU exhaustion
    NETWORK = "NETWORK"                  # Network connectivity or timeout
    PERMISSION = "PERMISSION"            # Access denied / insufficient privileges
    COMPATIBILITY = "COMPATIBILITY"      # Version mismatch or unsupported platform
    UNKNOWN = "UNKNOWN"                  # Cannot determine cause


class HypothesisConfidence(str, enum.Enum):
    """Confidence tier for a diagnostic hypothesis."""
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class RecoveryLevel(str, enum.Enum):
    """Recovery action risk/permission level."""
    LEVEL_1_SAFE_AUTO = "LEVEL_1_SAFE_AUTO"         # Auto-execute, safe & reversible
    LEVEL_2_CONFIRMATION = "LEVEL_2_CONFIRMATION"    # Ask user before executing
    LEVEL_3_USER_GUIDANCE = "LEVEL_3_USER_GUIDANCE"  # Explain to user, do not execute


class CheckTrigger(str, enum.Enum):
    """What triggered a health check."""
    MANUAL = "MANUAL"
    STARTUP = "STARTUP"
    PERIODIC = "PERIODIC"
    EVENT_TRIGGERED = "EVENT_TRIGGERED"
    ON_DEMAND = "ON_DEMAND"


# ─────────────────────────────────────────────────────────────────────────────
# Health Record (Component Registration)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HealthRecord:
    """
    Registered component descriptor in the Component Health Registry.

    Each component declares its health capabilities, dependencies, and criticality.
    Recovery capabilities must be explicitly listed — nothing is assumed.
    """
    component_id: str
    name: str
    category: ComponentCategory
    criticality: ComponentCriticality = ComponentCriticality.MEDIUM
    version: str = "unknown"
    health_status: HealthStatus = HealthStatus.UNKNOWN
    dependencies: List[str] = field(default_factory=list)    # component_id list
    recovery_capabilities: List[str] = field(default_factory=list)  # action_id list
    last_check: float = 0.0
    last_healthy: float = 0.0
    consecutive_failures: int = 0
    error_count: int = 0
    last_error: str = ""
    enabled: bool = True

    def mark_healthy(self):
        self.health_status = HealthStatus.HEALTHY
        self.last_healthy = time.time()
        self.consecutive_failures = 0
        self.last_check = time.time()
        self.last_error = ""

    def mark_failed(self, error: str = ""):
        self.consecutive_failures += 1
        self.error_count += 1
        self.last_check = time.time()
        self.last_error = error[:200]  # Cap to avoid huge error blobs
        if self.consecutive_failures >= 3:
            self.health_status = HealthStatus.FAILING
        elif self.consecutive_failures >= 1:
            self.health_status = HealthStatus.UNAVAILABLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "name": self.name,
            "category": self.category.value,
            "criticality": self.criticality.value,
            "health_status": self.health_status.value,
            "dependencies": self.dependencies,
            "recovery_capabilities": self.recovery_capabilities,
            "last_check": self.last_check,
            "last_healthy": self.last_healthy,
            "consecutive_failures": self.consecutive_failures,
            "error_count": self.error_count,
            "enabled": self.enabled
            # last_error intentionally omitted to avoid leaking in HUD payloads
        }

    def to_hud_entry(self) -> Dict[str, Any]:
        """Safe compact entry for HUD display."""
        return {
            "id": self.component_id,
            "name": self.name,
            "status": self.health_status.value,
            "criticality": self.criticality.value
        }


# ─────────────────────────────────────────────────────────────────────────────
# Health Check Result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HealthCheckResult:
    """
    Structured result from a component health check.

    Always includes: status, latency, error_summary, dependency_status,
    recommended_action, and evidence. Never exposes secrets or full stack traces.
    """
    component_id: str
    status: HealthStatus = HealthStatus.UNKNOWN
    latency_ms: float = 0.0
    error_summary: str = ""       # Human-readable, no stack traces or secrets
    dependency_status: Dict[str, HealthStatus] = field(default_factory=dict)
    recommended_action: str = ""
    evidence: List[str] = field(default_factory=list)
    trigger: CheckTrigger = CheckTrigger.ON_DEMAND
    timestamp: float = field(default_factory=time.time)

    def is_healthy(self) -> bool:
        return self.status == HealthStatus.HEALTHY

    def is_actionable(self) -> bool:
        """Returns True if action is needed."""
        return self.status not in (HealthStatus.HEALTHY, HealthStatus.DISABLED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "error_summary": self.error_summary,
            "dependency_status": {k: v.value for k, v in self.dependency_status.items()},
            "recommended_action": self.recommended_action,
            "evidence": self.evidence,
            "trigger": self.trigger.value,
            "timestamp": self.timestamp
        }


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostic Hypothesis
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DiagnosticHypothesis:
    """
    A structured, confidence-annotated hypothesis about a failure cause.

    Hypotheses are always presented as possibilities, never confirmed facts.
    Supporting evidence must be cited. A diagnostic test is suggested where available.
    """
    hypothesis: str
    confidence: HypothesisConfidence
    failure_class: FailureClass
    supporting_evidence: List[str] = field(default_factory=list)
    diagnostic_test: str = ""     # Safe test to further confirm/deny this hypothesis

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis": self.hypothesis,
            "confidence": self.confidence.value,
            "failure_class": self.failure_class.value,
            "supporting_evidence": self.supporting_evidence,
            "diagnostic_test": self.diagnostic_test
        }


# ─────────────────────────────────────────────────────────────────────────────
# Diagnostic Report
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class DiagnosticReport:
    """
    Full structured diagnostic result for a component failure.

    Includes: failure classification, ranked hypotheses, available recovery options,
    dependency chain analysis, and a human-readable narrative.
    """
    report_id: str = field(default_factory=lambda: f"diag_{uuid.uuid4().hex[:8]}")
    component_id: str = ""
    component_name: str = ""
    failure_class: FailureClass = FailureClass.UNKNOWN
    check_result: Optional[HealthCheckResult] = None
    hypotheses: List[DiagnosticHypothesis] = field(default_factory=list)
    dependency_chain: List[str] = field(default_factory=list)  # Dependency component IDs
    recovery_options: List[str] = field(default_factory=list)  # action_ids ordered by preference
    narrative: str = ""           # Human-readable summary (no secrets)
    voice_summary: str = ""       # Short version for TTS
    timestamp: float = field(default_factory=time.time)

    def top_hypothesis(self) -> Optional[DiagnosticHypothesis]:
        if self.hypotheses:
            return self.hypotheses[0]
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "component_id": self.component_id,
            "component_name": self.component_name,
            "failure_class": self.failure_class.value,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "dependency_chain": self.dependency_chain,
            "recovery_options": self.recovery_options,
            "narrative": self.narrative,
            "timestamp": self.timestamp
        }


# ─────────────────────────────────────────────────────────────────────────────
# Recovery Action
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RecoveryAction:
    """
    An explicitly registered, permission-checked recovery action.

    IMPORTANT:
    - No arbitrary shell commands are permitted.
    - risk_level and requires_confirmation are declared up-front.
    - Preconditions must be satisfied before execution.
    - verification_method specifies what to check after execution.
    """
    action_id: str
    component_id: str
    description: str
    level: RecoveryLevel
    reversible: bool = True
    requires_confirmation: bool = False
    preconditions: List[str] = field(default_factory=list)
    verification_method: str = "health_check"  # What to run to verify success
    max_attempts: int = 3
    cooldown_seconds: float = 30.0

    @property
    def risk_level(self) -> str:
        """Human-readable risk level derived from RecoveryLevel."""
        return {
            RecoveryLevel.LEVEL_1_SAFE_AUTO: "LOW",
            RecoveryLevel.LEVEL_2_CONFIRMATION: "MEDIUM",
            RecoveryLevel.LEVEL_3_USER_GUIDANCE: "HIGH"
        }.get(self.level, "UNKNOWN")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "component_id": self.component_id,
            "description": self.description,
            "level": self.level.value,
            "risk_level": self.risk_level,
            "reversible": self.reversible,
            "requires_confirmation": self.requires_confirmation,
            "preconditions": self.preconditions,
            "verification_method": self.verification_method,
            "max_attempts": self.max_attempts,
            "cooldown_seconds": self.cooldown_seconds
        }


# ─────────────────────────────────────────────────────────────────────────────
# Recovery Result
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RecoveryResult:
    """Result of an attempted recovery action."""
    action_id: str
    component_id: str
    success: bool
    message: str = ""
    verification_status: HealthStatus = HealthStatus.UNKNOWN
    attempts_made: int = 0
    limit_reached: bool = False
    requires_user_action: bool = False
    user_guidance: str = ""        # Only populated for LEVEL_3 actions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "component_id": self.component_id,
            "success": self.success,
            "message": self.message,
            "verification_status": self.verification_status.value,
            "attempts_made": self.attempts_made,
            "limit_reached": self.limit_reached,
            "requires_user_action": self.requires_user_action,
            "user_guidance": self.user_guidance
        }


# ─────────────────────────────────────────────────────────────────────────────
# Full Health Report (all components)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class HealthReport:
    """
    Full system health report — a snapshot of all component statuses.
    Produced by DiagnosticsEngine.check_all() or run_startup_diagnostics().
    """
    report_id: str = field(default_factory=lambda: f"hrpt_{uuid.uuid4().hex[:8]}")
    results: Dict[str, HealthCheckResult] = field(default_factory=dict)
    overall_status: HealthStatus = HealthStatus.UNKNOWN
    trigger: CheckTrigger = CheckTrigger.ON_DEMAND
    timestamp: float = field(default_factory=time.time)

    def healthy_count(self) -> int:
        return sum(1 for r in self.results.values() if r.status == HealthStatus.HEALTHY)

    def unhealthy_count(self) -> int:
        return sum(1 for r in self.results.values() if r.status not in (
            HealthStatus.HEALTHY, HealthStatus.DISABLED, HealthStatus.UNKNOWN
        ))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "overall_status": self.overall_status.value,
            "trigger": self.trigger.value,
            "timestamp": self.timestamp,
            "healthy_count": self.healthy_count(),
            "unhealthy_count": self.unhealthy_count(),
            "results": {cid: r.to_dict() for cid, r in self.results.items()}
        }

    def to_voice_summary(self) -> str:
        """Concise spoken summary."""
        total = len(self.results)
        healthy = self.healthy_count()
        unhealthy = self.unhealthy_count()

        if unhealthy == 0:
            return f"All {healthy} components are operational."

        failing = [
            cid for cid, r in self.results.items()
            if r.status not in (HealthStatus.HEALTHY, HealthStatus.DISABLED, HealthStatus.UNKNOWN)
        ]
        if len(failing) == 1:
            name = failing[0].replace("_", " ")
            return (
                f"{healthy} of {total} components are operational. "
                f"{name} is currently {self.results[failing[0]].status.value.lower()}."
            )
        names = ", ".join(f.replace("_", " ") for f in failing[:3])
        return (
            f"{healthy} of {total} components are operational. "
            f"Issues detected in: {names}."
        )

    def to_hud_payload(self) -> Dict[str, Any]:
        """Safe compact payload for HUD overlay."""
        return {
            "overall": self.overall_status.value,
            "components": {
                cid: r.status.value
                for cid, r in self.results.items()
            }
        }
