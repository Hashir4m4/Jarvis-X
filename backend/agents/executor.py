import logging
import subprocess
import os
from typing import Dict, Optional, Any
from ..automation.security_proxy import SecurityProxy, PermissionLevel

logger = logging.getLogger(__name__)

# Map of language to test runner commands
TEST_RUNNERS = {
    "python": ["python", "-m", "pytest"],
    "javascript": ["npx", "jest"],
    "typescript": ["npx", "jest"],
    "go": ["go", "test", "./..."],
    "rust": ["cargo", "test"],
    "java": ["mvn", "test"],
}

# Map of language to run commands
RUN_COMMANDS = {
    "python": ["python"],
    "javascript": ["node"],
    "typescript": ["npx", "ts-node"],
    "go": ["go", "run"],
    "rust": ["cargo", "run"],
}


class Executor:
    """Runs scripts, tests, and commands for the coding pipeline under SecurityProxy governance."""

    def __init__(self, working_dir: str = ".", security_proxy: Optional[Any] = None):
        self.working_dir = working_dir
        self.security = security_proxy or SecurityProxy()

    def run_file(self, filepath: str, language: str = "python") -> Dict:
        """Runs a single file safely."""
        cmd = RUN_COMMANDS.get(language, ["python"])
        full_cmd = cmd + [filepath]
        detail = f"run_file: {filepath} ({language})"
        return self.security.execute("agent.executor", detail, lambda: self._execute(full_cmd))

    def run_tests(self, language: str = "python", test_path: str = None) -> Dict:
        """Runs the test suite for a given language."""
        cmd = TEST_RUNNERS.get(language, ["python", "-m", "pytest"])
        if test_path:
            cmd = cmd + [test_path]
        detail = f"run_tests: {test_path or language}"
        return self.security.execute("agent.executor", detail, lambda: self._execute(cmd))

    def run_command(self, command: str) -> Dict:
        """Runs a shell command gated by SecurityProxy and blacklist verification."""
        if self.security.is_blacklisted(command):
            return {"status": "blocked", "message": f"Command '{command}' contains blacklisted instructions."}
        return self.security.execute("run_cmd", command, lambda: self._execute(command, shell=True))

    def install_dependencies(self, language: str = "python") -> Dict:
        """Installs dependencies based on the language."""
        commands = {
            "python": ["pip", "install", "-r", "requirements.txt"],
            "javascript": ["npm", "install"],
            "typescript": ["npm", "install"],
            "go": ["go", "mod", "download"],
            "rust": ["cargo", "build"],
        }
        cmd = commands.get(language)
        if not cmd:
            return {"status": "error", "message": f"No install command for {language}"}
        return self._execute(cmd)

    def lint(self, filepath: str, language: str = "python") -> Dict:
        """Runs a linter on a file."""
        linters = {
            "python": ["python", "-m", "py_compile", filepath],
            "javascript": ["npx", "eslint", filepath],
            "typescript": ["npx", "eslint", filepath],
        }
        cmd = linters.get(language)
        if not cmd:
            return {"status": "ok", "message": f"No linter configured for {language}"}
        return self._execute(cmd)

    def _execute(self, cmd, shell=False, timeout=60) -> Dict:
        """Executes a command and captures output."""
        try:
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=shell,
            )
            return {
                "status": "ok" if result.returncode == 0 else "error",
                "returncode": result.returncode,
                "stdout": result.stdout.strip()[:5000],
                "stderr": result.stderr.strip()[:2000],
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "message": f"Command timed out after {timeout}s."}
        except FileNotFoundError as e:
            return {"status": "error", "message": f"Command not found: {e}"}
        except Exception as e:
            logger.error(f"Executor error: {e}")
            return {"status": "error", "message": str(e)}
