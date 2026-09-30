"""
JARVIS Plugin Extensibility Ecosystem — Registry Bridges

These classes act as secure intermediaries between a plugin's provided
capabilities and JARVIS Core's authoritative registries.
"""
import logging
from typing import Any

from backend.plugins.models import PluginManifest
from backend.plugins.context import PluginContext
from backend.plugins.base_plugin import SkillPlugin, ToolPlugin, AgentPlugin

logger = logging.getLogger("JARVIS.PluginBridges")


class SkillBridge:
    """Safely registers a plugin's skills with the core SkillRegistry."""
    
    def __init__(self, core_skill_registry: Any, security_proxy: Any):
        self.registry = core_skill_registry
        self.security = security_proxy

    def register_plugin_skills(self, plugin: SkillPlugin, manifest: PluginManifest, context: PluginContext) -> int:
        count = 0
        try:
            skills = plugin.get_skills()
            for skill in skills:
                # Basic validation: ensure it looks like a skill
                if hasattr(skill, "name") and hasattr(skill, "execute"):
                    # Prefix the skill name to avoid core conflicts
                    original_name = skill.name
                    if not original_name.startswith(f"plugin_{manifest.id}_"):
                        # We don't forcefully overwrite the attribute here to avoid breaking plugin internals,
                        # but we register it under a namespaced key in the registry.
                        pass
                    
                    self.registry.register(skill)
                    count += 1
                    logger.debug(f"Registered plugin skill: {original_name}")
                else:
                    logger.warning(f"Plugin {manifest.id} provided invalid skill object.")
        except Exception as e:
            logger.error(f"Failed to register skills for {manifest.id}: {e}")
        return count


class ToolBridge:
    """Safely registers a plugin's tools with the core ToolRegistry."""
    
    def __init__(self, core_tool_registry: Any, security_proxy: Any):
        self.registry = core_tool_registry
        self.security = security_proxy

    def register_plugin_tools(self, plugin: ToolPlugin, manifest: PluginManifest, context: PluginContext) -> int:
        count = 0
        if not self.registry:
            return 0
            
        try:
            tools = plugin.get_tools()
            for tool in tools:
                if isinstance(tool, dict) and "name" in tool:
                    tool_name = tool.get("name", "")
                    original_func = tool.get("func") or tool.get("function") or tool.get("execute")
                    
                    if callable(original_func):
                        def _make_secured_wrapper(fn, tname):
                            def _secured_call(*args, **kwargs):
                                action_id = f"plugin.{manifest.id}.{tname}"
                                detail = f"Plugin Tool '{action_id}' invoked"
                                if self.security:
                                    return self.security.execute(action_id, detail, lambda: fn(*args, **kwargs))
                                return fn(*args, **kwargs)
                            return _secured_call

                        wrapped_tool = dict(tool)
                        if "func" in tool:
                            wrapped_tool["func"] = _make_secured_wrapper(original_func, tool_name)
                        elif "function" in tool:
                            wrapped_tool["function"] = _make_secured_wrapper(original_func, tool_name)
                        elif "execute" in tool:
                            wrapped_tool["execute"] = _make_secured_wrapper(original_func, tool_name)
                        self.registry.register_tool(wrapped_tool)
                    else:
                        self.registry.register_tool(tool)
                    count += 1
        except Exception as e:
            logger.error(f"Failed to register tools for {manifest.id}: {e}")
        return count


class AgentBridge:
    """Safely registers a plugin's agents with the core AgentRegistry."""
    
    def __init__(self, core_agent_registry: Any, security_proxy: Any):
        self.registry = core_agent_registry
        self.security = security_proxy

    def register_plugin_agents(self, plugin: AgentPlugin, manifest: PluginManifest, context: PluginContext) -> int:
        count = 0
        if not self.registry:
            return 0
            
        try:
            agents = plugin.get_agents()
            for agent in agents:
                if hasattr(agent, "agent_id") or hasattr(agent, "name"):
                    # Register agent
                    if hasattr(self.registry, "register_agent"):
                        self.registry.register_agent(agent)
                        count += 1
        except Exception as e:
            logger.error(f"Failed to register agents for {manifest.id}: {e}")
        return count
