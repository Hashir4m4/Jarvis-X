"""
JARVIS Plugin Extensibility Ecosystem — Plugin Interfaces

Defines the base classes for all JARVIS plugins.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

from backend.plugins.context import PluginContext
from backend.diagnostics.models import HealthStatus


class JarvisPlugin(ABC):
    """
    The base interface for all JARVIS plugins.
    Plugins must inherit from one of the specific subclasses (SkillPlugin, ToolPlugin, etc.)
    but they all share this base lifecycle.
    """

    def __init__(self):
        self.context: Optional[PluginContext] = None

    def initialize(self, context: PluginContext):
        """Called by the PluginManager during the ENABLE phase."""
        self.context = context

    def on_enable(self) -> bool:
        """
        Called when the plugin is transitioning to ENABLED.
        Return True if successful, False if the plugin fails to enable.
        """
        return True

    def on_disable(self):
        """Called when the plugin is transitioning to DISABLED. Clean up resources."""
        pass

    def health_check(self) -> HealthStatus:
        """
        Integrates with JARVIS Self-Diagnostics.
        Override to return a specific health status.
        """
        return HealthStatus.HEALTHY


class SkillPlugin(JarvisPlugin):
    """A plugin that provides one or more custom JARVIS Skills."""
    
    @abstractmethod
    def get_skills(self) -> List[Any]:
        """
        Returns a list of BaseSkill instances to be registered with the core SkillRegistry.
        """
        pass


class ToolPlugin(JarvisPlugin):
    """A plugin that provides one or more specific Tools for agents or planners."""
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Returns a list of tool definitions/instances to be registered.
        """
        pass


class AgentPlugin(JarvisPlugin):
    """A plugin that provides one or more specialized Agents."""
    
    @abstractmethod
    def get_agents(self) -> List[Any]:
        """
        Returns a list of Agent instances to be registered with the AgentRegistry.
        """
        pass


class KnowledgePlugin(JarvisPlugin):
    """A plugin that provides custom Knowledge Processors."""
    pass


class MonitorPlugin(JarvisPlugin):
    """A plugin that provides custom proactive Monitors."""
    pass


class AIProviderPlugin(JarvisPlugin):
    """A plugin that registers a new AI Provider with the Hybrid Model Router."""
    pass


class UIPlugin(JarvisPlugin):
    """A plugin that contributes to the HUD or user interface."""
    pass


class AutomationPlugin(JarvisPlugin):
    """A plugin that adds new desktop automation capabilities."""
    pass


# Backward compatibility alias
BasePlugin = JarvisPlugin
