import logging
import subprocess
from typing import Dict, Any, List, Optional

from .security_proxy import SecurityProxy, BLACKLISTED_PATTERNS

logger = logging.getLogger("JARVIS.TerminalExecutor")


import re

class CommandClassification(str):
    READ_ONLY = "terminal_read_only"
    SAFE_WRITE = "terminal_safe_write"
    CONFIRM_REQUIRED = "terminal_confirm"
    RESTRICTED = "terminal_restricted"


class TerminalExecutor:
    """
    Executes PowerShell and CMD commands with strict safety limits,
    subprocess timeouts, and blacklist enforcement.
    """

    # Safe read-only commands
    READ_ONLY_PATTERNS = [
        r"^python\s+--version$", r"^ipconfig.*", r"^dir.*", r"^ls.*",
        r"^echo.*", r"^ping\s+-n\s+\d+\s+.*", r"^whoami$", r"^systeminfo.*"
    ]
    
    # Destructive or system-altering commands
    RESTRICTED_PATTERNS = [
        r".*shutdown.*", r".*restart.*", r".*format.*",
        r".*rm\s+-rf.*", r".*del\s+/s.*", r".*reg\s+add.*",
        r".*net\s+user.*", r".*diskpart.*"
    ]

    def __init__(self, security_proxy: Optional[SecurityProxy] = None):
        self.security = security_proxy or SecurityProxy()

    def classify_command(self, command: str) -> str:
        cmd_lower = command.lower().strip()
        
        for pattern in self.RESTRICTED_PATTERNS:
            if re.match(pattern, cmd_lower):
                return CommandClassification.RESTRICTED
                
        for pattern in self.READ_ONLY_PATTERNS:
            if re.match(pattern, cmd_lower):
                return CommandClassification.READ_ONLY
                
        if "delete" in cmd_lower or "remove" in cmd_lower or "rm " in cmd_lower or "del " in cmd_lower:
            return CommandClassification.CONFIRM_REQUIRED
            
        # Default for unrecognized commands
        return CommandClassification.CONFIRM_REQUIRED

    def run_powershell(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Runs a command via PowerShell with timeout, blacklist checks, and security proxy gating."""
        if self._is_blacklisted(command):
            return {"status": "blocked", "message": f"Command is blacklisted: {command}"}
            
        classification = self.classify_command(command)
        exec_func = lambda: self._execute(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], timeout)
        return self.security.execute(classification, f"PowerShell: {command}", exec_func)

    def run_cmd(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Runs a command via CMD with timeout, blacklist checks, and security proxy gating."""
        if self._is_blacklisted(command):
            return {"status": "blocked", "message": f"Command is blacklisted: {command}"}
            
        classification = self.classify_command(command)
        exec_func = lambda: self._execute(["cmd", "/C", command], timeout)
        return self.security.execute(classification, f"CMD: {command}", exec_func)

    def _execute(self, cmd_list: List[str], timeout: int) -> Dict[str, Any]:
        """Executes subprocess safely with timeout and output capture limits."""
        try:
            result = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "status": "ok",
                "returncode": result.returncode,
                "stdout": result.stdout.strip()[:5000],
                "stderr": result.stderr.strip()[:2000]
            }
        except subprocess.TimeoutExpired:
            logger.warning(f"Subprocess timed out after {timeout}s: {' '.join(cmd_list)}")
            return {"status": "error", "message": f"Command timed out after {timeout}s."}
        except Exception as e:
            logger.error(f"Terminal execution error: {e}")
            return {"status": "error", "message": str(e)}

    def _is_blacklisted(self, command: str) -> bool:
        return self.security.is_blacklisted(command)
