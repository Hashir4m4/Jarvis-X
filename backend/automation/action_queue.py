import logging
import time
from typing import List, Dict, Any, Optional, Callable
from .desktop_models import (
    DesktopAction, DesktopActionResult, ActionType,
    RiskLevel, ActionStatus
)
from .desktop_controller import DesktopController
from .security_proxy import SecurityProxy, PermissionLevel

logger = logging.getLogger("JARVIS.ActionQueue")


class ActionQueueManager:
    """
    Manages structured sequential execution of desktop actions.
    Enforces:
      PLAN -> VALIDATE -> PERMISSION CHECK -> EXECUTE STEP -> VERIFY RESULT -> NEXT STEP
    Integrates emergency stop and early abort on verification failure or cancellation.
    """

    def __init__(
        self,
        controller: DesktopController,
        security_proxy: Optional[SecurityProxy] = None,
        state_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.controller = controller
        self.security = security_proxy or SecurityProxy()
        self.state_callback = state_callback
        self._emergency_stop_triggered = False
        self._current_queue: List[DesktopAction] = []
        self._active_action: Optional[DesktopAction] = None

    def trigger_emergency_stop(self):
        """
        Emergency Stop! Cancels all queued actions and aborts immediately.
        Can be triggered by voice commands ('stop', 'abort', 'cancel that').
        """
        self._emergency_stop_triggered = True
        logger.critical("[EMERGENCY STOP] Desktop automation emergency stop activated!")
        if self._active_action:
            self._active_action.status = ActionStatus.CANCELLED
            self._active_action.error = "Emergency stop triggered"
        for act in self._current_queue:
            act.status = ActionStatus.CANCELLED
            act.error = "Cancelled due to emergency stop"
        self._notify_state("emergency_stop", {"message": "Emergency stop triggered."})

    def reset_emergency_stop(self):
        """Resets the emergency stop flag to allow future executions."""
        self._emergency_stop_triggered = False

    def _notify_state(self, event: str, data: Dict[str, Any]):
        if self.state_callback:
            try:
                self.state_callback({"event": event, "data": data, "timestamp": time.time()})
            except Exception as e:
                logger.debug(f"State callback error: {e}")

    def execute_single(self, action: DesktopAction) -> DesktopActionResult:
        """Executes a single desktop action with permission check and verification."""
        return self.execute_plan([action])[0]

    def execute_plan(self, actions: List[DesktopAction]) -> List[DesktopActionResult]:
        """
        Executes an action plan step-by-step.
        Halts safely upon:
          - Emergency stop
          - Permission denial
          - Execution failure
          - Verification failure
        """
        self._current_queue = list(actions)
        results: List[DesktopActionResult] = []

        for idx, action in enumerate(self._current_queue):
            # Check emergency stop
            if self._emergency_stop_triggered:
                action.status = ActionStatus.CANCELLED
                action.error = "Emergency stop active"
                results.append(DesktopActionResult(
                    success=False,
                    action_id=action.action_id,
                    action_type=action.action_type,
                    message="Action cancelled due to Emergency Stop.",
                    status=ActionStatus.CANCELLED,
                    risk_level=action.risk_level
                ))
                break

            self._active_action = action
            action.status = ActionStatus.EXECUTING

            # 1. Validation & Permission Check
            action_name = action.action_type.value.lower()
            details = f"Target: {action.target}, Params: {action.parameters}"

            # High risk or bulk confirmation required
            if action.risk_level == RiskLevel.RESTRICTED or action.requires_confirmation:
                action.status = ActionStatus.CONFIRMING
                self._notify_state("PERMISSION_REQUIRED", {
                    "action_id": action.action_id,
                    "action_type": action.action_type.value,
                    "target": action.target,
                    "risk_level": action.risk_level.value,
                    "details": details
                })

                confirmed = self.security.request_confirmation(action_name, details)
                if not confirmed:
                    action.status = ActionStatus.DENIED
                    action.error = "User denied confirmation"
                    results.append(DesktopActionResult(
                        success=False,
                        action_id=action.action_id,
                        action_type=action.action_type,
                        message=f"Action '{action_name}' on '{action.target}' was denied by user.",
                        status=ActionStatus.DENIED,
                        risk_level=action.risk_level
                    ))
                    logger.info(f"Action '{action.action_id}' was denied by user.")
                    break  # Stop execution queue on confirmation denial

            # 2. Execute Step
            action.status = ActionStatus.EXECUTING
            self._notify_state("ACTION_EXECUTING", {"action_id": action.action_id, "action_type": action.action_type.value})
            res = self._dispatch(action)

            # Check if emergency stop fired during dispatch
            if self._emergency_stop_triggered:
                res.success = False
                res.status = ActionStatus.CANCELLED
                res.message = "Execution aborted by emergency stop."
                results.append(res)
                break

            # 3. Verify Result
            if res.success:
                verified = self.controller.verify_action(action)
                res.verified = verified
                action.verified = verified
                if not verified:
                    res.success = False
                    res.status = ActionStatus.FAILED
                    res.message = f"Action execution succeeded but post-verification failed for '{action.target}'."
                    action.status = ActionStatus.FAILED
                    action.error = "Verification failed"
                    logger.warning(f"Verification failed for action {action.action_id}")
                    results.append(res)
                    break  # Stop pipeline on verification failure
                else:
                    action.status = ActionStatus.VERIFIED
            else:
                action.status = ActionStatus.FAILED
                action.error = res.message
                results.append(res)
                break  # Stop pipeline on step failure

            results.append(res)

        self._active_action = None
        self._current_queue.clear()
        return results

    def _dispatch(self, action: DesktopAction) -> DesktopActionResult:
        """Dispatches an action to the concrete controller."""
        act_type = action.action_type
        tgt = action.target
        params = action.parameters

        try:
            if act_type == ActionType.OPEN_APPLICATION:
                return self.controller.open_application(tgt, params.get("parameters"))
            elif act_type == ActionType.CLOSE_APPLICATION:
                return self.controller.close_application(tgt)
            elif act_type == ActionType.OPEN_FILE:
                return self.controller.open_file(tgt)
            elif act_type == ActionType.OPEN_FOLDER:
                return self.controller.open_folder(tgt)
            elif act_type == ActionType.CREATE_FOLDER:
                return self.controller.create_folder(tgt)
            elif act_type == ActionType.CREATE_FILE:
                return self.controller.create_file(tgt, params.get("content", ""))
            elif act_type == ActionType.RENAME_FILE:
                return self.controller.rename_file(tgt, params.get("destination", ""))
            elif act_type == ActionType.MOVE_FILE:
                return self.controller.move_file(tgt, params.get("destination", ""))
            elif act_type == ActionType.COPY_FILE:
                return self.controller.copy_file(tgt, params.get("destination", ""))
            elif act_type == ActionType.DELETE_FILE:
                return self.controller.delete_file(tgt)
            elif act_type == ActionType.LIST_DIRECTORY:
                return self.controller.list_directory(tgt)
            elif act_type == ActionType.ORGANIZE_FILES:
                return self.controller.organize_directory(tgt, params.get("rules"))
            elif act_type == ActionType.GET_SYSTEM_INFO:
                return self.controller.get_system_info()
            elif act_type == ActionType.WINDOW_ACTION:
                win_act = params.get("window_action")
                return self.controller.window_action(win_act, tgt)
            elif act_type == ActionType.GUI_ACTION:
                return self.controller.gui_action(tgt, params)
            else:
                return DesktopActionResult(
                    success=False,
                    action_id=action.action_id,
                    action_type=act_type,
                    message=f"Unsupported action type: {act_type}",
                    status=ActionStatus.FAILED
                )
        except Exception as e:
            logger.error(f"Error executing action {action.action_id}: {e}")
            return DesktopActionResult(
                success=False,
                action_id=action.action_id,
                action_type=act_type,
                message=str(e),
                status=ActionStatus.FAILED
            )
