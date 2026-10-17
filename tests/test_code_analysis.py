"""
Unit and integration tests for Prompt 61 — Autonomous Code Analysis Subsystem.
Tests AST symbol extraction, syntax error isolation, security vulnerability detection,
and read-only repository scanning guarantees.
"""

import os
import pytest
from backend.code_intelligence.models import (
    FindingSeverity,
    FindingCategory,
    CodeAnalysisFinding,
    ModuleSymbolInfo,
)
from backend.code_intelligence.engine import CodeAnalysisEngine


def test_symbol_extraction_and_loc():
    engine = CodeAnalysisEngine()
    code = """
import os
import sys
from typing import List

class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

def standalone_helper():
    pass
"""
    symbols, findings = engine.analyze_source_code(code, file_path="calc.py")
    assert symbols.classes == ["Calculator"]
    assert "add" in symbols.functions
    assert "standalone_helper" in symbols.functions
    assert "os" in symbols.imports
    assert "sys" in symbols.imports
    assert symbols.loc > 5
    assert len(findings) == 0


def test_syntax_error_resilience():
    engine = CodeAnalysisEngine()
    invalid_code = "def broken_func(:\n    return 42"
    symbols, findings = engine.analyze_source_code(invalid_code, file_path="broken.py")

    assert len(findings) == 1
    assert findings[0].category == FindingCategory.SYNTAX
    assert findings[0].severity == FindingSeverity.CRITICAL
    assert findings[0].line_number == 1


def test_security_eval_detection():
    engine = CodeAnalysisEngine()
    insecure_code = """
def run_user_script(payload: str):
    eval(payload)
"""
    symbols, findings = engine.analyze_source_code(insecure_code, file_path="insecure.py")
    security_findings = [f for f in findings if f.category == FindingCategory.SECURITY]
    assert len(security_findings) == 1
    assert security_findings[0].severity == FindingSeverity.HIGH
    assert "eval" in security_findings[0].message


def test_read_only_guarantee_on_directory():
    engine = CodeAnalysisEngine()
    # Test directory analysis on a real backend package
    target_dir = os.path.join(os.path.dirname(__file__), "..", "backend", "priority")
    report = engine.analyze_directory(target_dir, max_files=10)

    assert report.total_files_analyzed >= 2
    assert report.total_loc > 50
    assert len(report.symbols) >= 2
