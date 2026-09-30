"""
JARVIS Diagnostic Engine

Converts raw HealthCheckResult evidence into structured DiagnosticReports
with ranked hypotheses, dependency chain analysis, and failure classification.

Design principles:
- Never presents a hypothesis as a confirmed fact
- Evidence is always cited in each hypothesis
- Confidence is always stated (HIGH / MODERATE / LOW)
- Dependency-caused degradation is explicitly distinguished
- Never exposes secrets or stack traces in output
- Does not automatically execute any recovery actions
"""
import logging
import time
from typing import Dict, Any, List, Optional

from .models import (
    HealthCheckResult, HealthStatus, FailureClass,
    DiagnosticHypothesis, DiagnosticReport, HypothesisConfidence
)
from .component_registry import ComponentRegistry

logger = logging.getLogger("JARVIS.DiagnosticEngine")


# ─────────────────────────────────────────────────────────────────────────────
# Known Failure Patterns
# Maps component_id + error indicators → classified hypotheses
# ─────────────────────────────────────────────────────────────────────────────

_LOCAL_AI_HYPOTHESES = [
    {
        "indicator": ["refused", "connection refused", "connection error"],
        "hypothesis": "The local AI server process is not running.",
        "confidence": HypothesisConfidence.HIGH,
        "failure_class": FailureClass.DEPENDENCY,
        "evidence_key": "Connection to local AI server was refused.",
        "diagnostic_test": "Check if the Ollama process is running."
    },
    {
        "indicator": ["timeout", "timed out"],
        "hypothesis": "The local AI server is reachable but not responding (overloaded or starting up).",
        "confidence": HypothesisConfidence.MODERATE,
        "failure_class": FailureClass.TRANSIENT,
        "evidence_key": "Connection timed out.",
        "diagnostic_test": "Wait 10 seconds and retry the connection."
    },
    {
        "indicator": [],  # Default fallback hypothesis
        "hypothesis": "The configured local AI server endpoint may be incorrect or unreachable.",
        "confidence": HypothesisConfidence.LOW,
        "failure_class": FailureClass.CONFIGURATION,
        "evidence_key": "Local AI server could not be reached.",
        "diagnostic_test": "Verify the configured Ollama URL matches the running server."
    }
]

_VOICE_HYPOTHESES = [
    {
        "indicator": ["audio_device", "unavailable", "none"],
        "hypothesis": "Voice input is unavailable because the microphone or audio device is not connected.",
        "confidence": HypothesisConfidence.HIGH,
        "failure_class": FailureClass.DEPENDENCY,
        "evidence_key": "Audio device dependency is unavailable.",
        "diagnostic_test": "Check physical microphone connection and system audio settings."
    },
    {
        "indicator": ["stt", "not initialized"],
        "hypothesis": "The speech recognition engine failed to initialize.",
        "confidence": HypothesisConfidence.MODERATE,
        "failure_class": FailureClass.TRANSIENT,
        "evidence_key": "STT engine is not initialized.",
        "diagnostic_test": "Restart the JARVIS voice subsystem."
    }
]

_KNOWLEDGE_BASE_HYPOTHESES = [
    {
        "indicator": ["index", "not found", "does not exist"],
        "hypothesis": "The knowledge base index has not been created yet or the index file is missing.",
        "confidence": HypothesisConfidence.HIGH,
        "failure_class": FailureClass.CONFIGURATION,
        "evidence_key": "Knowledge base index not found.",
        "diagnostic_test": "Check if the index directory exists. Re-initialize if missing."
    },
    {
        "indicator": ["sentence", "embedding", "transformers"],
        "hypothesis": "The embedding library is not installed. Keyword search fallback is active.",
        "confidence": HypothesisConfidence.HIGH,
        "failure_class": FailureClass.DEPENDENCY,
        "evidence_key": "sentence-transformers not available.",
        "diagnostic_test": "Install with: pip install sentence-transformers"
    }
]

_CLOUD_AI_HYPOTHESES = [
    {
        "indicator": ["network", "offline"],
        "hypothesis": "Cloud AI is unavailable because internet connectivity is offline.",
        "confidence": HypothesisConfidence.HIGH,
        "failure_class": FailureClass.NETWORK,
        "evidence_key": "Network dependency is UNAVAILABLE.",
        "diagnostic_test": "Check internet connection. Local AI remains available."
    },
    {
        "indicator": ["0 providers", "no providers", "not configured"],
        "hypothesis": "No cloud AI providers are configured. An API key may be missing.",
        "confidence": HypothesisConfidence.MODERATE,
        "failure_class": FailureClass.CONFIGURATION,
        "evidence_key": "Cloud manager reports 0 available providers.",
        "diagnostic_test": "Check cloud provider configuration in JARVIS settings."
    }
]

_COMPONENT_PATTERNS: Dict[str, List[Dict]] = {
    "local_ai": _LOCAL_AI_HYPOTHESES,
    "voice_input": _VOICE_HYPOTHESES,
    "audio_device": [
        {
            "indicator": ["0 audio", "no audio", "not found"],
            "hypothesis": "No microphone or audio input device is connected to the system.",
            "confidence": HypothesisConfidence.HIGH,
            "failure_class": FailureClass.DEPENDENCY,
            "evidence_key": "No audio input devices found.",
            "diagnostic_test": "Connect a microphone and check system audio settings."
        }
    ],
    "knowledge_base": _KNOWLEDGE_BASE_HYPOTHESES,
    "cloud_ai": _CLOUD_AI_HYPOTHESES,
    "memory": [
        {
            "indicator": ["sqlite", "not active", "none"],
            "hypothesis": "Memory database connection is not active. May need reinitialization.",
            "confidence": HypothesisConfidence.MODERATE,
            "failure_class": FailureClass.RESOURCE,
            "evidence_key": "Memory SQLite connection is not active.",
            "diagnostic_test": "Restart JARVIS to reinitialize the memory system."
        }
    ],
    "vision": [
        {
            "indicator": ["pil", "mss", "no screen"],
            "hypothesis": "Screen capture library is not installed.",
            "confidence": HypothesisConfidence.HIGH,
            "failure_class": FailureClass.DEPENDENCY,
            "evidence_key": "No screen capture library available.",
            "diagnostic_test": "Install with: pip install Pillow mss"
        },
        {
            "indicator": ["pytesseract", "ocr"],
            "hypothesis": "OCR engine (pytesseract) is not installed.",
            "confidence": HypothesisConfidence.HIGH,
            "failure_class": FailureClass.DEPENDENCY,
            "evidence_key": "pytesseract not available.",
            "diagnostic_test": "Install with: pip install pytesseract and install Tesseract-OCR binary."
        }
    ],
}

# Default hypothesis when no specific pattern is matched
_DEFAULT_HYPOTHESIS = DiagnosticHypothesis(
    hypothesis="The component may be temporarily unavailable due to an unclassified issue.",
    confidence=HypothesisConfidence.LOW,
    failure_class=FailureClass.UNKNOWN,
    supporting_evidence=["No known error patterns matched."],
    diagnostic_test="Run a targeted health check after a short wait."
)


# ─────────────────────────────────────────────────────────────────────────────
# Failure Class Classifier
# ─────────────────────────────────────────────────────────────────────────────

def _classify_failure(
    component_id: str,
    check_result: HealthCheckResult,
    dependency_statuses: Dict[str, HealthStatus]
) -> FailureClass:
    """Determines the most likely FailureClass from available evidence."""
    error_lower = check_result.error_summary.lower()
    evidence_lower = " ".join(check_result.evidence).lower()
    combined = error_lower + " " + evidence_lower

    # Dependency failures first
    if any(s in (HealthStatus.UNAVAILABLE, HealthStatus.FAILING)
           for s in dependency_statuses.values()):
        return FailureClass.DEPENDENCY

    # Common pattern matching
    if any(w in combined for w in ("network", "internet", "offline", "connectivity")):
        return FailureClass.NETWORK
    if any(w in combined for w in ("timeout", "timed out", "overloaded")):
        return FailureClass.TRANSIENT
    if any(w in combined for w in ("configuration", "config", "not configured", "api key", "endpoint")):
        return FailureClass.CONFIGURATION
    if any(w in combined for w in ("permission", "denied", "access")):
        return FailureClass.PERMISSION
    if any(w in combined for w in ("memory", "disk", "cpu", "resource", "space")):
        return FailureClass.RESOURCE
    if any(w in combined for w in ("version", "incompatible", "not supported")):
        return FailureClass.COMPATIBILITY
    if any(w in combined for w in ("not installed", "import", "library", "module")):
        return FailureClass.DEPENDENCY

    return FailureClass.UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
# DiagnosticEngine
# ─────────────────────────────────────────────────────────────────────────────

class DiagnosticEngine:
    """
    Evidence-based diagnostic engine.

    Flow:
    1. Receive component_id + HealthCheckResult
    2. Inspect dependency health chain
    3. Match error patterns to known failure signatures
    4. Generate ranked DiagnosticHypothesis list (HIGH → LOW confidence)
    5. Classify failure type
    6. Build human-readable narrative
    7. Return DiagnosticReport

    This engine does NOT execute any recovery. It only diagnoses.
    """

    def __init__(self, component_registry: ComponentRegistry):
        self.registry = component_registry

    def diagnose(
        self,
        component_id: str,
        check_result: HealthCheckResult,
        extra_context: Optional[Dict[str, Any]] = None
    ) -> DiagnosticReport:
        """
        Produces a full DiagnosticReport from a HealthCheckResult.

        Args:
            component_id: The component being diagnosed
            check_result: The raw health check result
            extra_context: Optional additional evidence (e.g., from error logs)

        Returns:
            DiagnosticReport with hypotheses, failure class, and narrative.
        """
        record = self.registry.get(component_id)
        component_name = record.name if record else component_id.replace("_", " ").title()

        # 1. Inspect dependency chain
        dep_chain = self.registry.get_dependency_chain(component_id)
        dependency_statuses = {}
        for dep_id in dep_chain:
            dep_record = self.registry.get(dep_id)
            if dep_record:
                dependency_statuses[dep_id] = dep_record.health_status

        # 2. Generate hypotheses
        hypotheses = self._generate_hypotheses(
            component_id, check_result, dependency_statuses, extra_context
        )

        # 3. Classify failure
        failure_class = _classify_failure(component_id, check_result, dependency_statuses)
        if hypotheses and hypotheses[0].confidence == HypothesisConfidence.HIGH:
            failure_class = hypotheses[0].failure_class

        # 4. Build narrative
        narrative = self._build_narrative(
            component_name, check_result, failure_class, hypotheses, dep_chain, dependency_statuses
        )
        voice_summary = self._build_voice_summary(component_name, check_result, hypotheses)

        # 5. Recovery options from registry
        recovery_options = []
        if record:
            recovery_options = list(record.recovery_capabilities)

        report = DiagnosticReport(
            component_id=component_id,
            component_name=component_name,
            failure_class=failure_class,
            check_result=check_result,
            hypotheses=hypotheses,
            dependency_chain=dep_chain,
            recovery_options=recovery_options,
            narrative=narrative,
            voice_summary=voice_summary
        )

        logger.info(
            f"[DiagnosticEngine] Diagnosed '{component_id}': "
            f"class={failure_class.value} top_hypothesis_confidence="
            f"{hypotheses[0].confidence.value if hypotheses else 'none'}"
        )
        return report

    def _generate_hypotheses(
        self,
        component_id: str,
        check_result: HealthCheckResult,
        dependency_statuses: Dict[str, HealthStatus],
        extra_context: Optional[Dict] = None
    ) -> List[DiagnosticHypothesis]:
        """Generates ranked hypotheses from pattern matching and dependency analysis."""
        hypotheses = []
        error_combined = (
            check_result.error_summary.lower() + " " +
            " ".join(check_result.evidence).lower()
        )

        # Step 1: Dependency-caused failures (highest priority)
        failing_deps = [
            dep_id for dep_id, status in dependency_statuses.items()
            if status in (HealthStatus.UNAVAILABLE, HealthStatus.FAILING)
        ]
        if failing_deps:
            dep_names = ", ".join(dep_id.replace("_", " ") for dep_id in failing_deps)
            hypotheses.append(DiagnosticHypothesis(
                hypothesis=(
                    f"{check_result.component_id.replace('_', ' ').title()} is affected because "
                    f"its {'dependency' if len(failing_deps) == 1 else 'dependencies'} "
                    f"({dep_names}) {'is' if len(failing_deps) == 1 else 'are'} unavailable."
                ),
                confidence=HypothesisConfidence.HIGH,
                failure_class=FailureClass.DEPENDENCY,
                supporting_evidence=[f"Dependency '{dep_id}' status: {dependency_statuses[dep_id].value}"
                                     for dep_id in failing_deps],
                diagnostic_test=f"Check health of: {dep_names}"
            ))

        # Step 2: Component-specific pattern matching
        patterns = _COMPONENT_PATTERNS.get(component_id, [])
        for pattern in patterns:
            indicators = pattern.get("indicator", [])
            matches = not indicators or any(ind in error_combined for ind in indicators)
            if matches:
                evidence = [pattern["evidence_key"]] + check_result.evidence[:2]
                hypotheses.append(DiagnosticHypothesis(
                    hypothesis=pattern["hypothesis"],
                    confidence=pattern["confidence"],
                    failure_class=pattern["failure_class"],
                    supporting_evidence=evidence,
                    diagnostic_test=pattern.get("diagnostic_test", "")
                ))

        # Step 3: Generic fallback
        if not hypotheses:
            generic = DiagnosticHypothesis(
                hypothesis=f"{component_id.replace('_', ' ').title()} is currently unavailable.",
                confidence=HypothesisConfidence.LOW,
                failure_class=FailureClass.UNKNOWN,
                supporting_evidence=check_result.evidence[:3],
                diagnostic_test="Run a targeted health check after a short wait."
            )
            hypotheses.append(generic)

        # Sort: HIGH → MODERATE → LOW
        order = {
            HypothesisConfidence.HIGH: 0,
            HypothesisConfidence.MODERATE: 1,
            HypothesisConfidence.LOW: 2
        }
        hypotheses.sort(key=lambda h: order.get(h.confidence, 9))
        return hypotheses

    @staticmethod
    def _build_narrative(
        component_name: str,
        check_result: HealthCheckResult,
        failure_class: FailureClass,
        hypotheses: List[DiagnosticHypothesis],
        dep_chain: List[str],
        dependency_statuses: Dict[str, HealthStatus]
    ) -> str:
        """Constructs a human-readable diagnostic narrative. No secrets included."""
        lines = [
            f"DIAGNOSTIC REPORT: {component_name}",
            f"Status: {check_result.status.value}",
            f"Failure classification: {failure_class.value}",
            ""
        ]

        if dep_chain:
            failing_deps = [d for d, s in dependency_statuses.items()
                            if s in (HealthStatus.UNAVAILABLE, HealthStatus.FAILING)]
            if failing_deps:
                lines.append(
                    f"Dependency analysis: {', '.join(failing_deps)} "
                    f"{'is' if len(failing_deps) == 1 else 'are'} unavailable, "
                    f"which may be causing this component to fail."
                )
                lines.append("")

        if hypotheses:
            lines.append("Possible causes (ranked by confidence):")
            for i, h in enumerate(hypotheses[:3], 1):
                lines.append(
                    f"  {i}. [{h.confidence.value}] {h.hypothesis}"
                )
                if h.diagnostic_test:
                    lines.append(f"     Diagnostic test: {h.diagnostic_test}")
            lines.append("")

        if check_result.recommended_action:
            lines.append(f"Recommended action: {check_result.recommended_action}")

        return "\n".join(lines)

    @staticmethod
    def _build_voice_summary(
        component_name: str,
        check_result: HealthCheckResult,
        hypotheses: List[DiagnosticHypothesis]
    ) -> str:
        """Produces a 1-2 sentence spoken summary."""
        status = check_result.status.value.lower()
        if hypotheses and hypotheses[0].confidence == HypothesisConfidence.HIGH:
            return (
                f"{component_name} is {status}. "
                f"{hypotheses[0].hypothesis}"
            )
        elif check_result.error_summary:
            return f"{component_name} is {status}. {check_result.error_summary}"
        else:
            return f"{component_name} is currently {status}."
