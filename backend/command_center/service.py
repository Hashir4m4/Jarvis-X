"""
Desktop Command Center Execution Service.
Prompt 67 — Desktop Command Center.
"""
import logging
import time
import re
from typing import Dict, Any, List, Optional
import uuid

from backend.command_center.models import (
    CommandExecutionState, DesktopCommandRequest, DesktopCommandResult
)
from backend.core.models import UserInput, InputChannel

logger = logging.getLogger("JARVIS.CommandCenter")

# Blacklisted dangerous patterns for natural-language / command entry safety
FORBIDDEN_PATTERNS = [
    r"rm\s+-rf",
    r"del\s+/[sfq]",
    r"format\s+[c-z]:",
    r"__import__",
    r"eval\(",
    r"exec\(",
    r"os\.system\(",
    r"subprocess\.Popen\("
]


class DesktopCommandCenter:
    """
    Unified Desktop Command Center Controller.
    Enforces the secure command boundary:
    UI -> Command Center -> Safety Validation -> IntentRouter -> Control/Security -> Execution -> Result
    """

    def __init__(
        self,
        jarvis_core: Optional[Any] = None,
        control_framework: Optional[Any] = None,
        security_proxy: Optional[Any] = None,
        history_limit: int = 50
    ):
        self.core = jarvis_core
        self.control_framework = control_framework or (getattr(jarvis_core, "control_framework", None) if jarvis_core else None)
        self.security = security_proxy or (getattr(jarvis_core, "security", None) if jarvis_core else None)
        self.history_limit = history_limit
        self._history: List[DesktopCommandResult] = []
        self._active_requests: Dict[str, DesktopCommandRequest] = {}

    def get_history(self) -> List[Dict[str, Any]]:
        # Redact any passwords/tokens before returning history to UI
        res = []
        for item in self._history:
            d = item.to_dict()
            # Sanitize output text
            d["output_text"] = re.sub(r"(?i)(key|token|password|secret)[=:\s]+[A-Za-z0-9_\-\.]{8,}", r"\1=***", d["output_text"])
            res.append(d)
        return res

    def get_suggestions(self, prefix: str) -> List[str]:
        prefix_lower = prefix.lower().strip()
        common = [
            "show active goals",
            "show critical path",
            "get system telemetry",
            "create a long horizon plan",
            "pause emergency execution",
            "list active workflows",
            "check component health",
            "open application",
            "get weather",
            "take a screenshot"
        ]
        if not prefix_lower:
            return common[:5]
        return [c for c in common if c.startswith(prefix_lower) or prefix_lower in c][:5]

    def cancel_command(self, request_id: str) -> bool:
        if request_id in self._active_requests:
            del self._active_requests[request_id]
            logger.info(f"Command request {request_id} cancelled.")
            return True
        return False

    async def execute_command(self, request: DesktopCommandRequest) -> DesktopCommandResult:
        start_time = time.time()
        self._active_requests[request.request_id] = request

        # 1. Safety Validation against arbitrary expressions / destructive scripts
        raw = request.raw_input.strip()
        for pat in FORBIDDEN_PATTERNS:
            if re.search(pat, raw, re.IGNORECASE):
                result = DesktopCommandResult(
                    request_id=request.request_id,
                    state=CommandExecutionState.REJECTED,
                    output_text="Command blocked by safety boundary: potentially destructive or arbitrary execution detected.",
                    error_message="Security Policy Violation: Unrestricted expression rejected.",
                    execution_time_ms=round((time.time() - start_time) * 1000, 2)
                )
                self._record_history(result)
                self._active_requests.pop(request.request_id, None)
                return result

        if not self.core:
            result = DesktopCommandResult(
                request_id=request.request_id,
                state=CommandExecutionState.FAILED,
                output_text="JARVIS Core is uninitialized.",
                error_message="JARVIS Core unavailable.",
                execution_time_ms=round((time.time() - start_time) * 1000, 2)
            )
            self._record_history(result)
            self._active_requests.pop(request.request_id, None)
            return result

        # 2. Check Emergency Stop Status in Control Framework
        if self.control_framework and hasattr(self.control_framework, "is_emergency_stop_active"):
            if self.control_framework.is_emergency_stop_active():
                result = DesktopCommandResult(
                    request_id=request.request_id,
                    state=CommandExecutionState.REJECTED,
                    output_text="Command rejected: Emergency Stop is currently ACTIVE in JARVIS OS.",
                    error_message="Emergency Stop Active.",
                    execution_time_ms=round((time.time() - start_time) * 1000, 2)
                )
                self._record_history(result)
                self._active_requests.pop(request.request_id, None)
                return result

        # 3. Route & Process through JARVIS Core
        try:
            meta = dict(request.metadata)
            meta["user_id"] = request.user_id
            user_input = UserInput(
                content=raw,
                channel=InputChannel.UI,
                session_id=request.session_id,
                request_id=request.request_id,
                metadata=meta
            )
            core_resp = await self.core.process_input(user_input)

            # Check if execution was cancelled mid-flight
            if request.request_id not in self._active_requests:
                result = DesktopCommandResult(
                    request_id=request.request_id,
                    state=CommandExecutionState.CANCELLED,
                    output_text="Operation cancelled by user.",
                    execution_time_ms=round((time.time() - start_time) * 1000, 2)
                )
                self._record_history(result)
                return result

            # Map Core Response
            skill_name = core_resp.intent.skill_name if core_resp.intent else None
            action_name = core_resp.intent.action if core_resp.intent else None
            
            result = DesktopCommandResult(
                request_id=request.request_id,
                state=CommandExecutionState.COMPLETED,
                output_text=core_resp.text,
                intent_skill=skill_name,
                intent_action=action_name,
                data=core_resp.data or {},
                execution_time_ms=round((time.time() - start_time) * 1000, 2)
            )
            self._record_history(result)
            self._active_requests.pop(request.request_id, None)
            return result

        except Exception as e:
            logger.error(f"Error executing desktop command: {e}")
            result = DesktopCommandResult(
                request_id=request.request_id,
                state=CommandExecutionState.FAILED,
                output_text=f"Command execution error: {str(e)}",
                error_message=str(e),
                execution_time_ms=round((time.time() - start_time) * 1000, 2)
            )
            self._record_history(result)
            self._active_requests.pop(request.request_id, None)
            return result

    def _record_history(self, result: DesktopCommandResult):
        self._history.append(result)
        if len(self._history) > self.history_limit:
            self._history.pop(0)
