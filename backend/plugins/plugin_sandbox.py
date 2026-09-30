import ast
import logging
from typing import List

logger = logging.getLogger(__name__)

# Modules that a dynamic plugin is absolutely NOT allowed to import
BLACKLISTED_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "urllib", "requests", 
    "ctypes", "pty", "commands", "importlib", "eval", "exec", "open", "builtins",
    "__builtin__", "pickle", "shelve", "marshal", "webbrowser", "http",
    "ftplib", "telnetlib", "posix", "nt"
}

FORBIDDEN_CALLS = {
    "eval", "exec", "open", "__import__", "compile", "globals", "locals"
}

FORBIDDEN_ATTRIBUTES = {
    "__subclasses__", "__globals__", "__code__", "__closure__", "__bases__"
}

class PluginSandbox(ast.NodeVisitor):
    """
    Statically analyzes plugin source code to ensure it doesn't 
    import dangerous modules or use forbidden functions.
    """

    def __init__(self):
        self.violations: List[str] = []

    def visit_Import(self, node):
        for alias in node.names:
            base_module = alias.name.split('.')[0]
            if base_module in BLACKLISTED_MODULES:
                self.violations.append(f"Blacklisted import detected: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            base_module = node.module.split('.')[0]
            if base_module in BLACKLISTED_MODULES:
                self.violations.append(f"Blacklisted from-import detected: {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                self.violations.append(f"Forbidden built-in function detected: {node.func.id}")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr in FORBIDDEN_ATTRIBUTES:
            self.violations.append(f"Forbidden dunder attribute access detected: {node.attr}")
        self.generic_visit(node)

    @classmethod
    def check_source(cls, source_code: str) -> bool:
        """
        Returns True if the source is safe, raises ValueError if unsafe.
        """
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            raise ValueError(f"Plugin syntax error: {e}")

        sandbox = cls()
        sandbox.visit(tree)

        if sandbox.violations:
            violation_str = "; ".join(sandbox.violations)
            logger.error(f"Plugin Sandbox Violation: {violation_str}")
            raise ValueError(f"Plugin rejected due to security violations: {violation_str}")

        return True
