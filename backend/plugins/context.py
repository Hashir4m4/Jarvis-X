"""
JARVIS Plugin Context

Provides a strictly controlled boundary for plugins to interact with the
JARVIS Core. Plugins receive a PluginContext instead of direct references
to core registries or the orchestrator.
"""
import logging
from typing import Dict, Any, Optional

from backend.plugins.models import PluginManifest


class RestrictedLogger:
    """A logger wrapper that forces a plugin-specific prefix."""
    def __init__(self, plugin_id: str):
        self._logger = logging.getLogger(f"JARVIS.Plugin.{plugin_id}")

    def debug(self, msg: str, *args, **kwargs):
        self._logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        self._logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        self._logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs):
        self._logger.error(msg, *args, **kwargs)


class PluginContext:
    """
    The controlled interface provided to a plugin when it is initialized.
    It exposes safe, permission-bound methods to interact with JARVIS.
    """

    def __init__(
        self,
        manifest: PluginManifest,
        config: Dict[str, Any],
        security_proxy: Any,
        event_bus: Any,
        memory_api: Any
    ):
        self._manifest = manifest
        self._config = config
        self._security = security_proxy
        self._event_bus = event_bus
        self._memory = memory_api
        
        self.logger = RestrictedLogger(manifest.id)
        
        # Extract plugin-specific configuration if any
        plugin_config_key = f"plugin_{manifest.id}"
        self.plugin_config = config.get(plugin_config_key, {})

    @property
    def plugin_id(self) -> str:
        return self._manifest.id

    def has_permission(self, permission: str) -> bool:
        """
        Checks if the plugin was granted a specific permission.
        (This checks the manifest declaration + core granting policy).
        """
        # A real implementation would check with SecurityProxy
        # For now, we assume if it's in the validated manifest, it's granted
        return permission in self._manifest.required_permissions

    async def publish_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """Publishes an event to the JARVIS EventBus safely."""
        if not self._event_bus:
            return False
            
        # Prefix the event type to isolate plugin events
        safe_event_type = f"plugin.{self.plugin_id}.{event_type}"
        
        # Wrap data to identify source
        payload = {
            "source_plugin": self.plugin_id,
            "data": data
        }
        
        try:
            await self._event_bus.publish(safe_event_type, payload)
            return True
        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")
            return False

    def request_permission(self, permission: str, reason: str) -> bool:
        """
        Requests a permission elevation at runtime.
        (Always returns False for now — plugins cannot elevate dynamically).
        """
        self.logger.warning(f"Dynamic permission elevation denied: {permission}")
        return False
