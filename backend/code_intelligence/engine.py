"""
JARVIS X — Autonomous Code Analysis Engine
Read-only AST parser, symbol extractor, and static issue detector.
"""

import ast
import os
import logging
from typing import List, Dict, Any, Optional
from .models import (
    CodeAnalysisFinding,
    FindingCategory,
    FindingSeverity,
    ModuleSymbolInfo,
    CodebaseAnalysisReport,
)

logger = logging.getLogger("JARVIS.CodeAnalyzer")


class CodeAnalysisEngine:
    """
    Subsystem responsible for autonomous, read-only static code analysis.
    Guarantees:
    - Strictly READ-ONLY: Never modifies files or directories.
    - Handles parsing errors and syntax exceptions gracefully without crashing.
    - Distinguishes confirmed syntax/security issues from stylistic recommendations.
    """

    def analyze_source_code(self, source_code: str, file_path: str = "<memory>") -> tuple[ModuleSymbolInfo, List[CodeAnalysisFinding]]:
        findings: List[CodeAnalysisFinding] = []
        loc = len(source_code.splitlines())

        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as e:
            findings.append(CodeAnalysisFinding(
                file_path=file_path,
                line_number=e.lineno,
                category=FindingCategory.SYNTAX,
                severity=FindingSeverity.CRITICAL,
                message=f"Syntax Error: {e.msg}",
                suggested_correction="Correct Python syntax at the indicated line.",
                confidence=1.0,
                evidence=str(e.text or "").strip(),
            ))
            return ModuleSymbolInfo(module_path=file_path, loc=loc), findings

        classes = []
        functions = []
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(node.name)
                # Check for high cyclomatic complexity / nesting
                complexity = len([n for n in ast.walk(node) if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler))])
                if complexity > 12:
                    findings.append(CodeAnalysisFinding(
                        file_path=file_path,
                        line_number=node.lineno,
                        category=FindingCategory.COMPLEXITY,
                        severity=FindingSeverity.MEDIUM,
                        message=f"High complexity in function '{node.name}' (branch count: {complexity})",
                        suggested_correction="Refactor large branching logic into smaller helper functions.",
                        confidence=0.85,
                        evidence=f"def {node.name}(...)",
                    ))

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

            # Security check: eval or exec usage
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in ("eval", "exec"):
                    findings.append(CodeAnalysisFinding(
                        file_path=file_path,
                        line_number=node.lineno,
                        category=FindingCategory.SECURITY,
                        severity=FindingSeverity.HIGH,
                        message=f"Use of dangerous built-in '{node.func.id}' detected.",
                        suggested_correction="Replace dynamic code execution with safe structured dispatch or ast.literal_eval.",
                        confidence=0.95,
                        evidence=f"{node.func.id}(...)",
                    ))

        symbols = ModuleSymbolInfo(
            module_path=file_path,
            classes=classes,
            functions=functions,
            imports=imports,
            loc=loc,
        )
        return symbols, findings

    def analyze_file(self, file_path: str) -> tuple[Optional[ModuleSymbolInfo], List[CodeAnalysisFinding]]:
        if not os.path.exists(file_path):
            return None, [CodeAnalysisFinding(
                file_path=file_path,
                category=FindingCategory.SYNTAX,
                severity=FindingSeverity.HIGH,
                message=f"File not found: {file_path}",
            )]

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return self.analyze_source_code(content, file_path=file_path)
        except Exception as e:
            return None, [CodeAnalysisFinding(
                file_path=file_path,
                category=FindingCategory.SYNTAX,
                severity=FindingSeverity.HIGH,
                message=f"Failed to read file: {e}",
            )]

    def analyze_directory(self, root_dir: str, max_files: int = 50) -> CodebaseAnalysisReport:
        report = CodebaseAnalysisReport(root_path=root_dir)
        total_loc = 0
        analyzed_count = 0

        for root, _, files in os.walk(root_dir):
            if any(p in root for p in ("__pycache__", ".git", ".pytest_cache", "venv")):
                continue
            for file in files:
                if file.endswith(".py"):
                    if analyzed_count >= max_files:
                        break
                    full_path = os.path.join(root, file)
                    symbols, findings = self.analyze_file(full_path)
                    if symbols:
                        report.symbols.append(symbols)
                        total_loc += symbols.loc
                    report.findings.extend(findings)
                    analyzed_count += 1

        report.total_files_analyzed = analyzed_count
        report.total_loc = total_loc
        return report
