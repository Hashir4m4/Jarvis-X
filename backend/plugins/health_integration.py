"""
JARVIS Plugin Extensibility Ecosystem — Health Integration

Bridges plugin health states to the core Diagnostics Engine.
"""
from typing import Optional, Any

from backend.plugins.models import PluginStatus
from backend.plugins.base_plugin import JarvisPlugin
from backend.diagnostics.models import HealthStatus, HealthCheckResult, CheckTrigger
from backend.diagnostics.health_checks import ComponentHealthCheck


class PluginHealthCheck(ComponentHealthCheck):
    """
    A dynamic health check for an enabled plugin.
    Delegates to the plugin's own health_check() method if it is running,
    otherwise reports its current manager-tracked status.
    """

    def __init__(self, plugin_id: str, plugin_manager: Any):
        self._plugin_id = plugin_id
        self._manager = plugin_manager

    @property
    def component_id(self) -> str:
        return f"plugin_{self._plugin_id}"

    async def check(self, trigger=CheckTrigger.ON_DEMAND, dependency_status=None) -> HealthCheckResult:
        manifest, status, instance = self._manager.get_plugin_state(self._plugin_id)
        
        if not manifest:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.UNKNOWN,
                error_summary=f"Plugin '{self._plugin_id}' not found.",
                trigger=trigger
            )
            
        if status == PluginStatus.QUARANTINED:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.DISABLED,
                error_summary="Plugin is quarantined due to repeated failures.",
                trigger=trigger
            )
            
        if status == PluginStatus.DISABLED:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.DISABLED,
                evidence=["Plugin is intentionally disabled."],
                trigger=trigger
            )
            
        if status == PluginStatus.FAILED or status == PluginStatus.RUNTIME_FAILED:
            return HealthCheckResult(
                component_id=self.component_id,
                status=HealthStatus.FAILING,
                error_summary="Plugin encountered a fatal runtime error.",
                trigger=trigger
            )

        # If enabled/running, delegate to plugin's own health_check if possible
        if status in (PluginStatus.ENABLED, PluginStatus.RUNNING) and isinstance(instance, JarvisPlugin):
            try:
                plugin_status = instance.health_check()
                
                evidence = [f"Plugin {self._plugin_id} reports status: {plugin_status.value}"]
                
                return HealthCheckResult(
                    component_id=self.component_id,
                    status=plugin_status,
                    evidence=evidence,
                    trigger=trigger
                )
            except Exception as e:
                # Failure isolation: Plugin health check crash shouldn't crash the diagnostics
                return HealthCheckResult(
                    component_id=self.component_id,
                    status=HealthStatus.DEGRADED,
                    error_summary=f"Plugin health_check() raised an exception: {e}",
                    trigger=trigger
                )

        # Default fallback
        return HealthCheckResult(
            component_id=self.component_id,
            status=HealthStatus.UNKNOWN,
            evidence=[f"Plugin status is {status.value}"],
            trigger=trigger
        )
