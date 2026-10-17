"""
Unit and integration tests for Prompt 63 — Intelligent Debugging Subsystem.
Tests error classification, secret redaction in stack traces, diagnostic hypothesis generation,
and safe diagnostic reporting.
"""

import pytest
from backend.debugging.models import (
    DiagnosticConfidence,
    ErrorCategory,
    DiagnosticReport,
)
from backend.debugging.engine import IntelligentDebuggingEngine


def test_error_classification_and_hypothesis():
    engine = IntelligentDebuggingEngine()

    # 1. Dependency Error
    try:
        raise ModuleNotFoundError("No module named 'non_existent_pkg'")
    except Exception as e:
        report = engine.diagnose_exception(e, affected_component="core")

    assert report.error_type == "ModuleNotFoundError"
    assert report.category == ErrorCategory.DEPENDENCY_FAILURE
    assert len(report.hypotheses) == 1
    assert report.hypotheses[0].confidence == DiagnosticConfidence.CONFIRMED
    assert "Install missing package" in report.hypotheses[0].suggested_fix

    # 2. Permission Error
    try:
        raise PermissionError("Action 'delete_file' was not authorized by SecurityProxy.")
    except Exception as e:
        report_perm = engine.diagnose_exception(e)

    assert report_perm.category == ErrorCategory.PERMISSION_DENIED
    assert report_perm.hypotheses[0].confidence == DiagnosticConfidence.CONFIRMED


def test_secret_redaction_in_stack_traces():
    engine = IntelligentDebuggingEngine()
    sensitive_msg = "Failed with token=sk-ant-1234567890abcdef and password=SuperSecretPassword123"

    try:
        raise ValueError(sensitive_msg)
    except Exception as e:
        report = engine.diagnose_exception(e)

    # Verify credentials are redacted
    assert "SuperSecretPassword123" not in report.error_message
    assert "sk-ant-1234567890abcdef" not in report.error_message
    assert "[REDACTED" in report.error_message
    assert "SuperSecretPassword123" not in report.sanitized_stack_trace


def test_diagnostic_report_serialization():
    engine = IntelligentDebuggingEngine()
    try:
        1 / 0
    except ZeroDivisionError as e:
        report = engine.diagnose_exception(e, affected_component="math_module")

    data = report.to_dict()
    assert data["error_type"] == "ZeroDivisionError"
    assert data["category"] == ErrorCategory.RUNTIME_EXCEPTION.value
    assert data["affected_component"] == "math_module"
    assert len(data["hypotheses"]) >= 1
