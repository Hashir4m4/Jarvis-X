"""
JARVIS X — Autonomous Code Analysis & Intelligence Subsystem
Domain models for AST inspection, code metrics, findings, and architecture analysis.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class FindingSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FindingCategory(str, Enum):
    SYNTAX = "SYNTAX"
    SECURITY = "SECURITY"
    COMPLEXITY = "COMPLEXITY"
    DEAD_CODE = "DEAD_CODE"
    CIRCULAR_IMPORT = "CIRCULAR_IMPORT"
    STYLE = "STYLE"


@dataclass
class CodeAnalysisFinding:
    """Individual static analysis finding identified in code."""
    finding_id: str = field(default_factory=lambda: f"fnd_{uuid.uuid4().hex[:8]}")
    file_path: str = ""
    line_number: Optional[int] = None
    category: FindingCategory = FindingCategory.COMPLEXITY
    severity: FindingSeverity = FindingSeverity.MEDIUM
    message: str = ""
    suggested_correction: Optional[str] = None
    confidence: float = 1.0  # 0.0 to 1.0
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.message,
            "suggested_correction": self.suggested_correction,
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
        }


@dataclass
class ModuleSymbolInfo:
    """Structured symbol discovery data for a Python module."""
    module_path: str
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    loc: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_path": self.module_path,
            "classes": list(self.classes),
            "functions": list(self.functions),
            "imports": list(self.imports),
            "loc": self.loc,
        }


@dataclass
class CodebaseAnalysisReport:
    """Read-only static analysis report of a repository or module tree."""
    report_id: str = field(default_factory=lambda: f"rpt_{uuid.uuid4().hex[:8]}")
    root_path: str = ""
    total_files_analyzed: int = 0
    total_loc: int = 0
    symbols: List[ModuleSymbolInfo] = field(default_factory=list)
    findings: List[CodeAnalysisFinding] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "report_id": self.report_id,
            "root_path": self.root_path,
            "total_files_analyzed": self.total_files_analyzed,
            "total_loc": self.total_loc,
            "symbols": [s.to_dict() for s in self.symbols],
            "findings": [f.to_dict() for f in self.findings],
            "created_at": self.created_at,
        }
