import logging
import os
import time
from typing import Dict, Any, List, Optional, Callable

from ..llm_client import LLMClient
from ..automation.security_proxy import SecurityProxy
from .planner import Planner
from .coder import Coder
from .reviewer import Reviewer
from .executor import Executor
from . import code_tools

logger = logging.getLogger("JARVIS.AgentManager")


class AgentManager:
    """
    Orchestrates the multi-agent coding pipeline:
    Planner -> Coder -> Reviewer -> Executor
    With real-time HUD telemetry, cancellation support, timeout guard, and execution policies.
    """

    def __init__(
        self,
        llm: LLMClient,
        security: SecurityProxy,
        working_dir: str = ".",
        state_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.llm = llm
        self.security = security
        self.working_dir = working_dir
        self.state_callback = state_callback

        self.planner = Planner(llm)
        self.coder = Coder(llm)
        self.reviewer = Reviewer(llm)
        self.executor = Executor(working_dir, security_proxy=self.security)

        self._cancelled = False
        self.current_state = "IDLE"
        self.active_agent = "none"
        self.current_task = ""
        self.current_step = 0
        self.total_steps = 0

    def cancel(self):
        """Signals the running multi-agent pipeline to cancel execution."""
        self._cancelled = True
        self._emit_state("system", "CANCELLED", {"message": "Agent execution cancelled by user."})
        logger.warning("Cancellation requested for AgentManager pipeline.")

    def _emit_state(self, agent: str, state: str, details: Optional[Dict[str, Any]] = None):
        """Emits telemetry state updates for the HUD."""
        self.active_agent = agent
        self.current_state = state
        payload = {
            "agent": agent,
            "state": state,
            "task": self.current_task,
            "step": self.current_step,
            "total_steps": self.total_steps,
            "details": details or {},
            "timestamp": time.time()
        }
        if self.state_callback:
            try:
                self.state_callback(payload)
            except Exception as e:
                logger.debug(f"State callback error: {e}")

    def run_task(
        self,
        task: str,
        repo_path: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Runs the full coding pipeline for a given task:
        Planner -> Coder -> Reviewer -> Executor -> Output Deliverables
        """
        self._cancelled = False
        self.current_task = task
        self.current_step = 0
        self.total_steps = 0
        start_time = time.time()

        report = {
            "task": task,
            "steps": [],
            "status": "ok",
            "execution_time_seconds": 0.0
        }

        # ── 1. Scan repo for context ─────────────────────────────
        repo_context = ""
        if repo_path and os.path.isdir(repo_path):
            repo_context = code_tools.build_repo_tree(repo_path, max_depth=3)
            logger.info(f"Scanned repository: {repo_path}")

        # ── 2. Plan ──────────────────────────────────────────────
        self._emit_state("planner", "PLANNING", {"task": task})
        logger.info(f"[Planner] Decomposing task: {task}")
        steps = self.planner.plan(task, repo_context)

        if not steps:
            self._emit_state("planner", "FAILED", {"message": "Planner could not decompose task."})
            report["status"] = "error"
            report["message"] = "Planner could not decompose the task into steps."
            return report

        self.total_steps = len(steps)
        self._emit_state("planner", "PLAN_READY", {"step_count": len(steps)})
        logger.info(f"[Planner] Generated {len(steps)} steps.")

        # ── 3. Execute each step ─────────────────────────────────
        for i, step in enumerate(steps):
            if self._cancelled:
                logger.warning("[AgentManager] Pipeline cancelled before step execution.")
                report["status"] = "cancelled"
                report["message"] = "Task was cancelled by user."
                self._emit_state("system", "CANCELLED", {"step": i + 1})
                break

            # Timeout check
            if timeout and (time.time() - start_time) > timeout:
                logger.error(f"[AgentManager] Pipeline timed out after {timeout} seconds.")
                report["status"] = "timeout"
                report["message"] = f"Execution exceeded maximum timeout of {timeout}s."
                self._emit_state("system", "TIMEOUT", {"elapsed": time.time() - start_time})
                break

            self.current_step = i + 1
            step_report = {
                "step_num": step["step_num"],
                "action": step["action"],
                "file": step["file"],
                "description": step["description"],
                "code_review": None,
                "execution": None,
                "status": "pending",
            }

            filepath = step["file"]
            if repo_path:
                filepath = os.path.join(repo_path, step["file"])

            action = step["action"].upper()

            if action in ("CREATE", "MODIFY"):
                # ── Code generation ──────────────────────────────
                self._emit_state("coder", "CODING", {"file": step["file"], "step": i + 1})
                existing = None
                if action == "MODIFY" and os.path.isfile(filepath):
                    existing = code_tools.read_file_content(filepath)

                logger.info(f"[Coder] Generating code for: {step['file']}")
                code = self.coder.generate(step, existing)

                # Error recovery: retry once if code is empty
                if not code:
                    logger.warning(f"[Coder] Empty code output for {step['file']}. Attempting error recovery retry...")
                    code = self.coder.generate(step, existing)

                if not code:
                    step_report["status"] = "error"
                    step_report["message"] = "Coder returned empty output."
                    report["steps"].append(step_report)
                    self._emit_state("coder", "ERROR", {"file": step["file"]})
                    continue

                # ── Review ───────────────────────────────────────
                self._emit_state("reviewer", "REVIEWING", {"file": step["file"], "step": i + 1})
                logger.info(f"[Reviewer] Reviewing: {step['file']}")
                review = self.reviewer.review(step["file"], code, step["description"])
                step_report["code_review"] = review

                # Write file safely through security proxy
                detail = f"Write file: {filepath}"
                write_func = lambda: code_tools.write_file_content(filepath, code)
                write_res = self.security.execute("write_file", detail, write_func)
                if isinstance(write_res, dict) and write_res.get("status") in ("denied", "blocked"):
                    step_report["status"] = write_res.get("status")
                    step_report["message"] = write_res.get("message", "File write denied")
                    report["steps"].append(step_report)
                    continue
                step_report["status"] = "written"

                # ── Lint check ───────────────────────────────────
                lang = code_tools.detect_language(filepath)
                lint_result = self.executor.lint(filepath, lang)
                if lint_result.get("status") == "error":
                    step_report["lint"] = lint_result
                    logger.warning(f"[Lint] Issues found in {filepath}")

            elif action == "DELETE":
                detail = f"Delete file: {filepath}"
                delete_func = lambda: os.remove(filepath) if os.path.isfile(filepath) else None
                del_res = self.security.execute("delete_file", detail, delete_func)
                if isinstance(del_res, dict) and del_res.get("status") in ("denied", "blocked"):
                    step_report["status"] = del_res.get("status")
                    step_report["message"] = del_res.get("message", "File deletion denied")
                else:
                    step_report["status"] = "deleted"

            elif action == "TEST":
                self._emit_state("executor", "TESTING", {"file": step["file"], "step": i + 1})
                logger.info(f"[Executor] Running tests: {filepath}")
                lang = code_tools.detect_language(filepath)
                test_result = self.executor.run_tests(lang, filepath)
                step_report["execution"] = test_result
                step_report["status"] = "tested"

            elif action == "RUN":
                self._emit_state("executor", "EXECUTING", {"file": step["file"], "step": i + 1})
                logger.info(f"[Executor] Running: {filepath}")
                lang = code_tools.detect_language(filepath)
                run_result = self.executor.run_file(filepath, lang)
                step_report["execution"] = run_result
                step_report["status"] = "executed"

            else:
                step_report["status"] = "skipped"
                step_report["message"] = f"Unknown action: {action}"

            report["steps"].append(step_report)

        report["execution_time_seconds"] = round(time.time() - start_time, 2)
        final_state = "COMPLETED" if report["status"] == "ok" else report["status"].upper()
        self._emit_state("system", final_state, {"steps_executed": len(report["steps"])})
        return report

    def explain_code(self, filepath: str) -> str:
        """Asks the LLM to explain a given file."""
        content = code_tools.read_file_content(filepath)
        if not content:
            return f"Could not read file: {filepath}"

        messages = [
            {"role": "system", "content": "You are a senior developer. Explain the code below clearly and concisely."},
            {"role": "user", "content": f"File: {filepath}\n\n```\n{content}\n```"},
        ]
        return self.llm.chat_sync(messages)

    def generate_docs(self, filepath: str) -> str:
        """Asks the LLM to generate documentation for a file."""
        content = code_tools.read_file_content(filepath)
        if not content:
            return f"Could not read file: {filepath}"

        messages = [
            {
                "role": "system",
                "content": "You are a technical writer. Generate clear, comprehensive documentation for the code below. Include function signatures, parameters, return values, and usage examples."
            },
            {"role": "user", "content": f"File: {filepath}\n\n```\n{content}\n```"},
        ]
        return self.llm.chat_sync(messages)

    def git_status(self, repo_path: str) -> str:
        return code_tools.git_status(repo_path)

    def git_diff(self, repo_path: str) -> str:
        return code_tools.git_diff(repo_path)

    def git_commit(self, repo_path: str, message: str) -> str:
        return code_tools.git_commit(repo_path, message)
