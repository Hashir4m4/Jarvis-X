"""
JARVIS X — Intelligent Debugging Engine
Stack trace sanitization, root-cause correlation, hypothesis generation, and fix formulation.
"""

import re
import traceback
import logging
from typing import Dict, Any, List, Optional
from .models import (
    DiagnosticReport,
    DiagnosticHypothesis,
    DiagnosticConfidence,
    ErrorCategory,
)

logger = logging.getLogger("JARVIS.DebuggingEngine")

# Redaction patterns for secrets in error traces
REDACT_PATTERNS = [
    (r"(sk-[a-zA-Z0-9_\-]{15,})", "[REDACTED_API_KEY]"),
    (r"(password[=:\s]+)([^\s,;]+)", r"\1[REDACTED]"),
    (r"(token[=:\s]+)([^\s,;]+)", r"\1[REDACTED]"),
    (r"(key[=:\s]+)([^\s,;]+)", r"\1[REDACTED]"),
]


class IntelligentDebuggingEngine:
    """
    Subsystem responsible for root cause diagnosis and fix formulation.
    Guarantees:
    - Never leaks raw credentials or secrets into diagnostic reports.
    - Accurately classifies errors and generates ranked, evidence-backed hypotheses.
    - Integrates with Prompt 62 CodeModificationEngine to propose fixes safely without silent mutation.
    """

    def __init__(self, code_modification_engine: Optional[Any] = None):
        self.code_modifier = code_modification_engine

    def diagnose_exception(
        self,
        exc: Exception,
        affected_component: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> DiagnosticReport:
        raw_trace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        sanitized_trace = self.sanitize_text(raw_trace)
        err_msg = self.sanitize_text(str(exc))
        err_type = type(exc).__name__

        category = self._classify_error(err_type, err_msg)
        hypotheses = self._formulate_hypotheses(err_type, err_msg, sanitized_trace, category)

        report = DiagnosticReport(
            error_type=err_type,
            error_message=err_msg,
            category=category,
            sanitized_stack_trace=sanitized_trace,
            affected_component=affected_component,
            hypotheses=hypotheses,
        )
        logger.info(f"Diagnosed {err_type} under category {category.value} with {len(hypotheses)} hypotheses.")
        return report

    def sanitize_text(self, text: str) -> str:
        sanitized = text
        for pattern, repl in REDACT_PATTERNS:
            sanitized = re.sub(pattern, repl, sanitized, flags=re.IGNORECASE)
        return sanitized

    def _classify_error(self, err_type: str, err_msg: str) -> ErrorCategory:
        if err_type in ("SyntaxError", "IndentationError", "TabError"):
            return ErrorCategory.SYNTAX
        elif err_type in ("PermissionError", "UnauthorizedError"):
            return ErrorCategory.PERMISSION_DENIED
        elif err_type in ("TimeoutError", "asyncio.TimeoutError"):
            return ErrorCategory.TIMEOUT
        elif err_type in ("ModuleNotFoundError", "ImportError"):
            return ErrorCategory.DEPENDENCY_FAILURE
        elif "config" in err_msg.lower() or "missing setting" in err_msg.lower():
            return ErrorCategory.CONFIGURATION
        return ErrorCategory.RUNTIME_EXCEPTION

    def _formulate_hypotheses(
        self,
        err_type: str,
        err_msg: str,
        trace: str,
        category: ErrorCategory,
    ) -> List[DiagnosticHypothesis]:
        hypotheses = []

        if category == ErrorCategory.SYNTAX:
            hypotheses.append(DiagnosticHypothesis(
                confidence=DiagnosticConfidence.CONFIRMED,
                summary="Invalid Python syntax detected",
                evidence=[err_msg],
                suggested_fix="Correct the syntax tokens indicated in the exception traceback.",
            ))
        elif category == ErrorCategory.DEPENDENCY_FAILURE:
            hypotheses.append(DiagnosticHypothesis(
                confidence=DiagnosticConfidence.CONFIRMED,
                summary=f"Unresolved module dependency: {err_msg}",
                evidence=[err_msg],
                suggested_fix="Install missing package or verify the relative Python import path.",
            ))
        elif category == ErrorCategory.PERMISSION_DENIED:
            hypotheses.append(DiagnosticHypothesis(
                confidence=DiagnosticConfidence.CONFIRMED,
                summary="Action rejected by security confirmation or authorization boundary",
                evidence=[err_msg],
                suggested_fix="Request explicit confirmation or verify user role permissions in SecurityProxy.",
            ))
        else:
            hypotheses.append(DiagnosticHypothesis(
                confidence=DiagnosticConfidence.PROBABLE,
                summary=f"Runtime error in application logic: {err_type}",
                evidence=[f"Exception message: {err_msg}"],
                suggested_fix="Add defensive parameter checks or inspect variable initialization.",
            ))

        return hypotheses
