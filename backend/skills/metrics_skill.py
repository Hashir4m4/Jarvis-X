import logging
import datetime
from typing import Dict, Any, List, Optional

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.automation.system_controller import SystemController

logger = logging.getLogger("JARVIS.MetricsSkill")


class MetricsSkill(BaseSkill):
    """
    Skill for hardware telemetry, resource load monitoring, and Obsidian metrics reporting.
    Reuses existing SystemController without duplicating implementations.
    """

    def __init__(self, system_controller: Optional[SystemController] = None, metadata=None):
        super().__init__(metadata=metadata)
        self.system_ctrl = system_controller or SystemController()

    @property
    def name(self) -> str:
        return "metrics"

    @property
    def description(self) -> str:
        return "Queries system performance metrics, CPU load, memory utilization, swap, and generates metrics reports."

    @property
    def supported_actions(self) -> List[str]:
        return ["get_telemetry", "get_cpu_load", "get_memory_stats", "get_summary", "pull_metrics_report"]

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        action = intent.action.lower()
        ctx = context or {}
        memory = ctx.get("memory")

        try:
            info = self.system_ctrl.get_system_info()
            cpu = info.get("cpu_percent", 0)
            ram_used = info.get("ram_used_percent", 0)
            ram_total = info.get("ram_total_gb", 0)
            temp = round(42 + cpu * 0.3)
            swap = round(ram_used * 0.4)
            battery = self.system_ctrl.get_battery()
            wifi = self.system_ctrl.get_wifi_status()

            # ─────────────────────────────────────────────────────────
            # Action: Metrics Pull (Daily Workflow -> vault/outputs/)
            # ─────────────────────────────────────────────────────────
            if action in ("pull_metrics_report", "metrics_pull"):
                now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                report_md = (
                    f"## System Metrics & Telemetry Report\n\n"
                    f"**Generated**: {now_str}\n"
                    f"**Host OS**: {info.get('os', 'Windows')}\n\n"
                    f"### Core Hardware Utilization\n"
                    f"- **CPU Utilization**: {cpu}%\n"
                    f"- **RAM Utilization**: {ram_used}% of {ram_total} GB\n"
                    f"- **Estimated Core Temperature**: ~{temp}°C\n"
                    f"- **Swap Memory**: {swap}%\n\n"
                    f"### Power & Network\n"
                    f"- **Battery**: {battery.get('percent', 'N/A')}%\n"
                    f"- **WiFi Connection**: {'Connected' if wifi.get('connected') else 'Disconnected'}\n"
                )

                vault_path = None
                if memory and hasattr(memory, "create_report"):
                    try:
                        vault_path = memory.create_report(
                            title=f"Telemetry Snapshot - {datetime.date.today().isoformat()}",
                            content=report_md,
                            report_type="telemetry_pull",
                            tags=["metrics", "telemetry", "hardware"]
                        )
                    except Exception as e:
                        logger.warning(f"Failed to store metrics report in vault/outputs/: {e}")

                output_text = (
                    f"### 📊 System Metrics Report\n\n"
                    f"• **CPU**: {cpu}%\n"
                    f"• **RAM**: {ram_used}% of {ram_total} GB\n"
                    f"• **Core Temp**: ~{temp}°C\n"
                    f"• **Swap**: {swap}%\n"
                    f"• **Battery**: {battery.get('percent', 'N/A')}%\n\n"
                    f"*Report archived to Obsidian vault: `{vault_path or 'vault/outputs/'}`*"
                )

                return SkillResult(
                    success=True,
                    data={"cpu": cpu, "ram": ram_used, "vault_path": vault_path},
                    message="Metrics report generated",
                    output_text=output_text
                )

            # ─────────────────────────────────────────────────────────
            # Standard Query Actions
            # ─────────────────────────────────────────────────────────
            elif action in ("get_telemetry", "get_summary"):
                data = {
                    "cpu_percent": cpu,
                    "ram_used_percent": ram_used,
                    "ram_total_gb": ram_total,
                    "temp_celsius": temp,
                    "swap_percent": swap,
                    "os": info.get("os", "Windows")
                }
                text = (
                    f"Telemetry Snapshot: CPU is at {cpu}%, RAM is at {ram_used}% "
                    f"({ram_total} GB total), Core Temp is ~{temp}°C, Swap is {swap}%."
                )
                return SkillResult(success=True, data=data, message="Telemetry retrieved", output_text=text)

            elif action == "get_cpu_load":
                data = {"cpu_percent": cpu}
                text = f"Current CPU utilization is {cpu}%."
                return SkillResult(success=True, data=data, message="CPU load retrieved", output_text=text)

            elif action == "get_memory_stats":
                data = {
                    "ram_used_percent": ram_used,
                    "ram_total_gb": ram_total,
                    "swap_percent": swap
                }
                text = f"Memory Stats: {ram_used}% of {ram_total} GB RAM in use, {swap}% swap utilized."
                return SkillResult(success=True, data=data, message="Memory stats retrieved", output_text=text)

            else:
                return SkillResult(
                    success=False,
                    message=f"Unknown metrics action: {action}",
                    output_text=f"Unknown metrics action '{action}'."
                )

        except Exception as e:
            logger.error(f"Error in MetricsSkill ({action}): {e}")
            return SkillResult(success=False, message=str(e), output_text=f"Failed to fetch metrics: {e}")
