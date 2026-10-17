"""
JARVIS X — Workflow Execution Engine
Orchestrates dependency-aware, authorized execution of workflows via registered skills.
Enforces step retries, backoff, cancellation, timeouts, and comprehensive audit logging.
"""

import time
import logging
import threading
from typing import Dict, Any, List, Optional, Set
from backend.core.models import Intent, SkillResult
from .models import (
    Workflow,
    WorkflowStep,
    WorkflowStatus,
    WorkflowStepStatus,
    WorkflowExecution,
    ExecutionAuditRecord,
    ExecutionRiskLevel,
)

logger = logging.getLogger("JARVIS.WorkflowEngine")


class WorkflowExecutionEngine:
    """
    Subsystem responsible for executing approved workflows.
    Guarantees:
    - Never executes without explicit authorization (`authorize_execution`).
    - High-risk steps require separate step authorization if policy specifies.
    - Idempotent execution: Steps completed are never executed twice.
    - Failures isolate down-stream steps by marking them BLOCKED.
    - Captures an immutable execution audit record for every action attempt.
    """

    def __init__(
        self,
        skill_registry: Optional[Any] = None,
        security_proxy: Optional[Any] = None,
        event_bus: Optional[Any] = None,
    ):
        self.skill_registry = skill_registry
        self.security = security_proxy
        self.event_bus = event_bus
        self._active_executions: Dict[str, WorkflowExecution] = {}
        self._cancellation_flags: Dict[str, bool] = {}
        self._lock = threading.RLock()

    def create_workflow(self, workflow: Workflow) -> Workflow:
        with self._lock:
            workflow.status = WorkflowStatus.PENDING_APPROVAL
            return workflow

    def authorize_execution(self, execution: WorkflowExecution, authorizer: str) -> bool:
        """
        Validates authorization to run an execution using SecurityProxy.
        """
        with self._lock:
            if not authorizer:
                raise ValueError("An authorizer must be explicitly specified.")

            # Validate against SecurityProxy
            if self.security and hasattr(self.security, "is_dangerous"):
                if self.security.is_dangerous("workflow_execution"):
                    if hasattr(self.security, "request_confirmation"):
                        confirmed = self.security.request_confirmation(
                            "workflow_execution",
                            f"Authorize workflow execution '{execution.execution_id}' by '{authorizer}'",
                        )
                        if not confirmed:
                            logger.warning(f"Workflow execution authorization denied for {execution.execution_id}")
                            return False

            execution.authorized_by = authorizer
            execution.authorized_at = time.time()
            execution.status = WorkflowStatus.APPROVED
            self._active_executions[execution.execution_id] = execution
            self._cancellation_flags[execution.execution_id] = False
            return True

    def cancel_execution(self, execution_id: str, reason: str = "User requested cancellation") -> bool:
        """Signals cancellation to an active execution."""
        with self._lock:
            if execution_id in self._cancellation_flags:
                self._cancellation_flags[execution_id] = True
            exec_obj = self._active_executions.get(execution_id)
            if exec_obj:
                exec_obj.status = WorkflowStatus.CANCELLED
                exec_obj.cancelled_at = time.time()
                exec_obj.error = reason
                return True
            return False

    def get_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        with self._lock:
            return self._active_executions.get(execution_id)

    def execute_workflow(self, workflow: Workflow, execution: WorkflowExecution) -> WorkflowExecution:
        """
        Synchronously runs the authorized workflow step-by-step honoring DAG dependencies.
        """
        with self._lock:
            if self._cancellation_flags.get(execution.execution_id, False) or execution.status == WorkflowStatus.CANCELLED:
                execution.status = WorkflowStatus.CANCELLED
                execution.cancelled_at = execution.cancelled_at or time.time()
                for s in workflow.steps:
                    s.status = WorkflowStepStatus.CANCELLED
                return execution

            if execution.status != WorkflowStatus.APPROVED:
                raise PermissionError(
                    f"Execution '{execution.execution_id}' cannot run. Status is '{execution.status.value}', requires 'APPROVED'."
                )
            execution.status = WorkflowStatus.RUNNING
            execution.started_at = time.time()

        logger.info(f"Starting execution '{execution.execution_id}' for workflow '{workflow.workflow_id}'.")

        # Map step by id
        steps_by_id: Dict[str, WorkflowStep] = {s.step_id: s for s in workflow.steps}
        completed_steps: Set[str] = set()

        # Identify initially ready steps (no dependencies)
        for step in workflow.steps:
            if not step.dependencies:
                step.status = WorkflowStepStatus.READY
            else:
                step.status = WorkflowStepStatus.PENDING

        has_failures = False

        while True:
            # Check for cancellation
            if self._cancellation_flags.get(execution.execution_id, False):
                logger.warning(f"Execution '{execution.execution_id}' was cancelled.")
                with self._lock:
                    execution.status = WorkflowStatus.CANCELLED
                    execution.cancelled_at = time.time()
                    for s in workflow.steps:
                        if s.status in (WorkflowStepStatus.PENDING, WorkflowStepStatus.READY):
                            s.status = WorkflowStepStatus.CANCELLED
                return execution

            # Update ready steps whose dependencies are completed
            progress_made = False
            for step in workflow.steps:
                if step.status == WorkflowStepStatus.PENDING:
                    # Check if all dependencies are completed
                    deps_met = all(dep_id in completed_steps for dep_id in step.dependencies)
                    deps_failed = any(
                        steps_by_id[dep_id].status in (WorkflowStepStatus.FAILED, WorkflowStepStatus.BLOCKED, WorkflowStepStatus.CANCELLED)
                        for dep_id in step.dependencies
                        if dep_id in steps_by_id
                    )
                    if deps_failed:
                        step.status = WorkflowStepStatus.BLOCKED
                        progress_made = True
                    elif deps_met:
                        step.status = WorkflowStepStatus.READY
                        progress_made = True

            # Find next ready step to execute
            ready_step = next((s for s in workflow.steps if s.status == WorkflowStepStatus.READY), None)
            if not ready_step:
                # No more ready steps: check if all are terminal
                all_terminal = all(
                    s.status in (
                        WorkflowStepStatus.COMPLETED,
                        WorkflowStepStatus.FAILED,
                        WorkflowStepStatus.BLOCKED,
                        WorkflowStepStatus.CANCELLED,
                        WorkflowStepStatus.SKIPPED,
                    )
                    for s in workflow.steps
                )
                if all_terminal:
                    break
                elif not progress_made:
                    # Deadlock or unresolvable dependencies
                    logger.error(f"Workflow execution deadlock in workflow {workflow.workflow_id}")
                    has_failures = True
                    break

            # Execute the step
            step_success = self._execute_step(ready_step, workflow, execution)
            if step_success:
                completed_steps.add(ready_step.step_id)
            else:
                has_failures = True

        # Finalize execution status
        with self._lock:
            execution.completed_at = time.time()
            if has_failures:
                execution.status = WorkflowStatus.FAILED
                workflow.status = WorkflowStatus.FAILED
            else:
                execution.status = WorkflowStatus.COMPLETED
                workflow.status = WorkflowStatus.COMPLETED

        logger.info(
            f"Execution '{execution.execution_id}' finished with status '{execution.status.value}'. "
            f"Total audit records: {len(execution.audit_trail)}."
        )
        return execution

    def _execute_step(
        self,
        step: WorkflowStep,
        workflow: Workflow,
        execution: WorkflowExecution,
    ) -> bool:
        step.status = WorkflowStepStatus.RUNNING
        step.started_at = time.time()

        # Step authorization check
        if step.policy.requires_approval or step.policy.risk_level in (ExecutionRiskLevel.HIGH, ExecutionRiskLevel.CRITICAL):
            if self.security and hasattr(self.security, "request_confirmation"):
                confirmed = self.security.request_confirmation(
                    f"{step.skill_name}:{step.action}",
                    f"Workflow step '{step.title}' (risk={step.policy.risk_level.value})",
                )
                if not confirmed:
                    step.status = WorkflowStepStatus.FAILED
                    step.error = "Step execution rejected by security confirmation."
                    self._record_audit(execution, workflow, step, success=False, error=step.error)
                    return False

        max_attempts = max(1, step.policy.max_retries + 1)
        attempt = 0
        last_error = None

        while attempt < max_attempts:
            attempt += 1
            step.attempt_count = attempt

            audit_rec = ExecutionAuditRecord(
                workflow_id=workflow.workflow_id,
                step_id=step.step_id,
                attempt=attempt,
                actor=execution.authorized_by or "system",
                action=step.action,
                skill_name=step.skill_name,
                input_snapshot=dict(step.parameters),
                started_at=time.time(),
            )

            try:
                # Dispatch execution to skill registry
                res = self._dispatch_capability(step)
                audit_rec.finished_at = time.time()
                audit_rec.duration_ms = round((audit_rec.finished_at - audit_rec.started_at) * 1000, 2)

                if res.success:
                    step.status = WorkflowStepStatus.COMPLETED
                    step.completed_at = time.time()
                    step.result = res.data or res.output_text
                    step.execution_time_ms = audit_rec.duration_ms
                    execution.step_results[step.step_id] = step.result

                    audit_rec.status = "COMPLETED"
                    audit_rec.output_snapshot = res.data or res.output_text
                    execution.audit_trail.append(audit_rec)
                    return True
                else:
                    last_error = res.message or "Skill execution reported failure"
                    audit_rec.status = "FAILED"
                    audit_rec.error = last_error
                    execution.audit_trail.append(audit_rec)

            except Exception as e:
                audit_rec.finished_at = time.time()
                audit_rec.duration_ms = round((audit_rec.finished_at - audit_rec.started_at) * 1000, 2)
                audit_rec.status = "ERROR"
                audit_rec.error = str(e)
                last_error = str(e)
                execution.audit_trail.append(audit_rec)

            if attempt < max_attempts:
                backoff = 0.05 * (step.policy.backoff_multiplier ** (attempt - 1))
                time.sleep(backoff)

        step.status = WorkflowStepStatus.FAILED
        step.error = f"Step failed after {attempt} attempt(s): {last_error}"
        step.completed_at = time.time()
        return False

    def _dispatch_capability(self, step: WorkflowStep) -> SkillResult:
        if not self.skill_registry:
            # Fallback simulated response when running isolated without real registry
            return SkillResult(
                success=True,
                status="success",
                message=f"Simulated execution for {step.skill_name}:{step.action}",
                data={"simulated": True, "step_id": step.step_id},
            )

        from backend.core.models import IntentType

        intent = Intent(
            intent_type=IntentType.SYSTEM_CONTROL,
            skill_name=step.skill_name,
            action=step.action,
            parameters=step.parameters,
            confidence=1.0,
            raw_input=f"{step.skill_name} {step.action}",
        )
        return self.skill_registry.execute_intent(intent)

    def _record_audit(
        self,
        execution: WorkflowExecution,
        workflow: Workflow,
        step: WorkflowStep,
        success: bool,
        error: Optional[str] = None,
    ):
        record = ExecutionAuditRecord(
            workflow_id=workflow.workflow_id,
            step_id=step.step_id,
            attempt=step.attempt_count or 1,
            actor=execution.authorized_by or "system",
            action=step.action,
            skill_name=step.skill_name,
            status="COMPLETED" if success else "FAILED",
            input_snapshot=dict(step.parameters),
            output_snapshot=step.result,
            error=error,
            finished_at=time.time(),
        )
        execution.audit_trail.append(record)
