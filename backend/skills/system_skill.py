import logging
from typing import Dict, Any, List

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.automation.system_controller import SystemController
from backend.automation.security_proxy import SecurityProxy, PermissionLevel

logger = logging.getLogger(__name__)


class SystemSkill(BaseSkill):
    """
    Skill for PC hardware settings, telemetry, and OS control.
    Wraps the existing SystemController with SecurityProxy permission gating.
    """

    def __init__(self, system_controller: SystemController = None, security_proxy: SecurityProxy = None, metadata=None):
        super().__init__(metadata=metadata)
        self.system_ctrl = system_controller or SystemController()
        self.security = security_proxy or SecurityProxy()

    @property
    def name(self) -> str:
        return "system"

    @property
    def description(self) -> str:
        return "Controls PC volume, brightness, battery, WiFi, system info, and processes."

    @property
    def supported_actions(self) -> List[str]:
        return [
            "get_system_info",
            "get_volume",
            "set_volume",
            "mute_volume",
            "unmute_volume",
            "get_brightness",
            "set_brightness",
            "get_battery",
            "get_wifi_status",
            "list_processes",
            "kill_process"
        ]

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        """Executes hardware / OS action and produces structured SkillResult."""
        action = intent.action.lower()
        params = intent.parameters or {}

        try:
            if action == "get_system_info":
                info = self.system_ctrl.get_system_info()
                cpu = info.get("cpu_percent", 0)
                ram = info.get("ram_used_percent", 0)
                total_ram = info.get("ram_total_gb", 0)
                text = f"System Status: CPU usage is {cpu}%, RAM usage is {ram}% of {total_ram} GB on {info.get('os', 'Windows')}."
                return SkillResult(success=True, data=info, message="System info retrieved", output_text=text)

            elif action == "get_volume":
                vol = self.system_ctrl.get_volume()
                if vol.get("status") == "ok":
                    text = f"Master volume is at {vol.get('volume')}%, {'muted' if vol.get('muted') else 'unmuted'}."
                    return SkillResult(success=True, data=vol, message="Volume retrieved", output_text=text)
                return SkillResult(success=False, data=vol, message=vol.get("message", "Failed to get volume"), output_text="Could not access audio device.")

            elif action == "set_volume":
                level = params.get("level", 50)
                vol = self.system_ctrl.set_volume(int(level))
                text = f"Volume set to {level}%."
                return SkillResult(success=True, data=vol, message=text, output_text=text)

            elif action == "mute_volume":
                vol = self.system_ctrl.mute_volume()
                text = "Audio muted."
                return SkillResult(success=True, data=vol, message=text, output_text=text)

            elif action == "unmute_volume":
                vol = self.system_ctrl.unmute_volume()
                text = "Audio unmuted."
                return SkillResult(success=True, data=vol, message=text, output_text=text)

            elif action == "get_brightness":
                bright = self.system_ctrl.get_brightness()
                if bright.get("status") == "ok":
                    text = f"Display brightness is at {bright.get('brightness')}%."
                    return SkillResult(success=True, data=bright, message="Brightness retrieved", output_text=text)
                return SkillResult(success=False, data=bright, message="Failed to get brightness", output_text="Could not get brightness.")

            elif action == "set_brightness":
                level = params.get("level", 50)
                bright = self.system_ctrl.set_brightness(int(level))
                text = f"Display brightness set to {level}%."
                return SkillResult(success=True, data=bright, message=text, output_text=text)

            elif action == "get_battery":
                batt = self.system_ctrl.get_battery()
                if "percent" in batt:
                    text = f"Battery is at {batt['percent']}%, {'plugged in' if batt.get('plugged_in') else 'on battery'}."
                else:
                    text = batt.get("message", "No battery detected.")
                return SkillResult(success=True, data=batt, message="Battery retrieved", output_text=text)

            elif action == "get_wifi_status":
                wifi = self.system_ctrl.get_wifi_status()
                connected = wifi.get("wifi_connected", False)
                text = f"WiFi is {'connected' if connected else 'disconnected'}."
                return SkillResult(success=True, data=wifi, message="WiFi status retrieved", output_text=text)

            elif action == "list_processes":
                procs = self.system_ctrl.list_processes(top_n=5)
                proc_list = [f"{p.get('name')} ({p.get('cpu_percent', 0)}% CPU)" for p in procs.get("processes", [])]
                text = f"Top running processes: {', '.join(proc_list)}."
                return SkillResult(success=True, data=procs, message="Processes listed", output_text=text)

            elif action == "kill_process":
                pid_val = params.get("pid")
                if pid_val is None or pid_val == "":
                    return SkillResult(success=False, message="No PID specified. Please specify an integer process ID.", output_text="Please specify a process ID to terminate.")
                try:
                    pid = int(pid_val)
                except (ValueError, TypeError):
                    return SkillResult(success=False, message="Invalid PID: PID must be an integer.", output_text="Process ID must be a valid integer.")
                detail = f"kill_process PID {pid}"
                kill_func = lambda: self.system_ctrl.kill_process(pid)
                exec_result = self.security.execute("kill_process", detail, kill_func)
                
                if isinstance(exec_result, dict) and exec_result.get("status") in ("denied", "blocked"):
                    return SkillResult(
                        success=False,
                        data=exec_result,
                        message=exec_result.get("message", "Action denied"),
                        output_text=f"Process termination blocked or denied: {exec_result.get('message', 'Action denied')}"
                    )
                
                res = exec_result if isinstance(exec_result, dict) else {"status": "ok", "message": f"Process {pid} terminated"}
                return SkillResult(success=res.get("status") == "ok", data=res, message=res.get("message", ""), output_text=res.get("message", ""))

            else:
                return SkillResult(
                    success=False,
                    message=f"Unknown system action: {action}",
                    output_text=f"I don't know how to perform the system action '{action}'."
                )

        except Exception as e:
            logger.error(f"Error executing SystemSkill ({action}): {e}")
            return SkillResult(success=False, message=str(e), output_text=f"Encountered an error executing system action: {e}")
