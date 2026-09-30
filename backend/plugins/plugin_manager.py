"""
JARVIS Plugin Extensibility Ecosystem — Plugin Manager

Handles DISCOVER, VALIDATE, INSPECT, ENABLE, and DISABLE lifecycles.
Resolves dependencies, enforces compatibility, and integrates with JARVIS Core.
"""
import os
import json
import yaml
import logging
import importlib.util
import inspect
from typing import Dict, List, Any, Tuple, Optional

from backend.plugins.models import (
    PluginManifest, PluginStatus, PluginType, PluginError, PluginValidationError
)
from backend.plugins.base_plugin import (
    JarvisPlugin, SkillPlugin, ToolPlugin, AgentPlugin
)
from backend.plugins.sandbox import PluginSandbox
from backend.plugins.context import PluginContext
from backend.plugins.registry_bridges import SkillBridge, ToolBridge, AgentBridge

logger = logging.getLogger("JARVIS.PluginManager")

# Mock version of JARVIS core for testing/validation purposes
JARVIS_CORE_VERSION = "1.0.0"


class PluginManager:
    """
    Discovers, validates, safely loads, and manages JARVIS extensions.
    """

    def __init__(
        self, 
        plugins_dir: str = "plugins",
        core_config: Optional[Dict[str, Any]] = None,
        security_proxy: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        memory_api: Optional[Any] = None,
        skill_registry: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        agent_registry: Optional[Any] = None
    ):
        self.plugins_dir = os.path.abspath(plugins_dir)
        self.config = core_config or {}
        self.security = security_proxy
        self.event_bus = event_bus
        self.memory = memory_api
        
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry
        self.agent_registry = agent_registry

        # Bridges
        self.skill_bridge = SkillBridge(self.skill_registry, self.security)
        self.tool_bridge = ToolBridge(self.tool_registry, self.security)
        self.agent_bridge = AgentBridge(self.agent_registry, self.security)

        # State tracking
        self._manifests: Dict[str, PluginManifest] = {}
        self._statuses: Dict[str, PluginStatus] = {}
        self._instances: Dict[str, JarvisPlugin] = {}
        self._crash_counts: Dict[str, int] = {}

    def discover_and_load(self):
        """Standard boot sequence: Discover, Validate, Enable valid plugins."""
        self.discover()
        self.validate_all()
        # In a real system, you might have an approval gate here
        # For default trusted directories, we can attempt to enable them
        for pid, status in self._statuses.items():
            if status == PluginStatus.VALIDATED:
                self.enable(pid)

    def discover(self):
        """Scans the plugins directory and parses manifests without executing code."""
        if not os.path.exists(self.plugins_dir):
            logger.info(f"Plugins directory not found: {self.plugins_dir}, skipping discovery.")
            return

        for item in os.listdir(self.plugins_dir):
            plugin_path = os.path.join(self.plugins_dir, item)
            if not os.path.isdir(plugin_path):
                continue
                
            manifest = self._parse_manifest(plugin_path, item)
            if manifest:
                self._manifests[manifest.id] = manifest
                self._statuses[manifest.id] = PluginStatus.DISCOVERED
                logger.info(f"Discovered plugin: {manifest.id} (v{manifest.version})")

    def _parse_manifest(self, path: str, folder_name: str) -> Optional[PluginManifest]:
        """Looks for plugin.yaml or plugin.json."""
        yaml_path = os.path.join(path, "plugin.yaml")
        json_path = os.path.join(path, "plugin.json")
        
        data = None
        if os.path.exists(yaml_path):
            try:
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
            except Exception as e:
                logger.error(f"Error parsing yaml manifest in {folder_name}: {e}")
                return None
        elif os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                logger.error(f"Error parsing json manifest in {folder_name}: {e}")
                return None
        else:
            return None
            
        try:
            # Enforce required fields
            if "id" not in data:
                data["id"] = folder_name
            return PluginManifest.from_dict(data)
        except Exception as e:
            logger.error(f"Malformed manifest in {folder_name}: {e}")
            return None

    def validate_all(self):
        """Validates all discovered plugins."""
        # Simple two-pass to handle dependencies
        for pid in list(self._statuses.keys()):
            if self._statuses[pid] == PluginStatus.DISCOVERED:
                self.validate(pid)

    def validate(self, plugin_id: str) -> bool:
        """
        Validates compatibility, resolves dependencies, and checks the sandbox.
        Transitions to VALIDATED, INCOMPATIBLE, or VALIDATION_FAILED.
        """
        if plugin_id not in self._manifests:
            return False
            
        manifest = self._manifests[plugin_id]
        self._statuses[plugin_id] = PluginStatus.VALIDATING
        
        # 1. Check compatibility
        min_ver = manifest.compatibility.minimum_core_version
        # Extremely simplified version check
        if min_ver > JARVIS_CORE_VERSION:
            logger.warning(f"Plugin {plugin_id} is INCOMPATIBLE (requires core >= {min_ver})")
            self._statuses[plugin_id] = PluginStatus.INCOMPATIBLE
            return False
            
        # 2. Check dependencies
        for dep_id in manifest.dependencies:
            if dep_id not in self._manifests:
                logger.error(f"Plugin {plugin_id} missing dependency: {dep_id}")
                self._statuses[plugin_id] = PluginStatus.VALIDATION_FAILED
                return False
            # Check for circular deps would go here in a robust system

        # 3. Security Sandbox (Static AST check)
        plugin_path = os.path.join(self.plugins_dir, manifest.id) # assuming folder == id for simplicity
        main_file_path = os.path.join(plugin_path, "main.py")
        
        if os.path.exists(main_file_path):
            try:
                with open(main_file_path, 'r', encoding='utf-8') as f:
                    source = f.read()
                PluginSandbox.check_source(source)
            except ValueError as e:
                logger.error(f"Plugin {plugin_id} failed sandbox validation: {e}")
                self._statuses[plugin_id] = PluginStatus.VALIDATION_FAILED
                return False
            except Exception as e:
                logger.error(f"Plugin {plugin_id} source read error: {e}")
                self._statuses[plugin_id] = PluginStatus.VALIDATION_FAILED
                return False
        
        self._statuses[plugin_id] = PluginStatus.VALIDATED
        return True

    def enable(self, plugin_id: str) -> bool:
        """
        Loads the plugin code, injects PluginContext, calls on_enable, 
        and registers capabilities.
        Transitions to ENABLED, LOAD_FAILED, or RUNTIME_FAILED.
        """
        if self._statuses.get(plugin_id) not in (PluginStatus.VALIDATED, PluginStatus.DISABLED):
            logger.warning(f"Cannot enable plugin {plugin_id} from state {self._statuses.get(plugin_id)}")
            return False

        # Enforce Quarantine
        if self._crash_counts.get(plugin_id, 0) >= 3:
            logger.error(f"Plugin {plugin_id} is QUARANTINED and cannot be enabled.")
            self._statuses[plugin_id] = PluginStatus.QUARANTINED
            return False

        manifest = self._manifests[plugin_id]
        
        # Dependency check: ensure dependencies are ENABLED
        for dep_id in manifest.dependencies:
            if self._statuses.get(dep_id) != PluginStatus.ENABLED:
                logger.error(f"Cannot enable {plugin_id}: Dependency {dep_id} is not ENABLED.")
                self._statuses[plugin_id] = PluginStatus.LOAD_FAILED
                return False

        plugin_path = os.path.join(self.plugins_dir, manifest.id)
        main_file_path = os.path.join(plugin_path, "main.py")
        
        if not os.path.exists(main_file_path):
            self._statuses[plugin_id] = PluginStatus.LOAD_FAILED
            return False

        # Dynamic Load
        try:
            spec = importlib.util.spec_from_file_location(f"jarvis_plugin_{manifest.id}", main_file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Find Plugin Class
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if inspect.isclass(attr) and issubclass(attr, JarvisPlugin) and attr is not JarvisPlugin:
                    plugin_class = attr
                    break
                    
            if not plugin_class:
                logger.error(f"Plugin {plugin_id} has no class inheriting from JarvisPlugin")
                self._statuses[plugin_id] = PluginStatus.LOAD_FAILED
                return False
                
            instance = plugin_class()
            
            # Build and Inject Context
            context = PluginContext(
                manifest=manifest,
                config=self.config,
                security_proxy=self.security,
                event_bus=self.event_bus,
                memory_api=self.memory
            )
            instance.initialize(context)
            
            # Trigger Enable Lifecycle
            success = instance.on_enable()
            if not success:
                logger.error(f"Plugin {plugin_id} returned False during on_enable()")
                self._statuses[plugin_id] = PluginStatus.RUNTIME_FAILED
                self._record_crash(plugin_id)
                return False
                
            self._instances[plugin_id] = instance
            
            # Register Capabilities
            if isinstance(instance, SkillPlugin):
                self.skill_bridge.register_plugin_skills(instance, manifest, context)
            if isinstance(instance, ToolPlugin):
                self.tool_bridge.register_plugin_tools(instance, manifest, context)
            if isinstance(instance, AgentPlugin):
                self.agent_bridge.register_plugin_agents(instance, manifest, context)
                
            self._statuses[plugin_id] = PluginStatus.ENABLED
            self._crash_counts[plugin_id] = 0  # Reset crash count on successful enable
            logger.info(f"Successfully enabled plugin: {manifest.id}")
            return True
            
        except Exception as e:
            logger.error(f"Exception enabling plugin {plugin_id}: {e}", exc_info=True)
            self._statuses[plugin_id] = PluginStatus.LOAD_FAILED
            self._record_crash(plugin_id)
            return False

    def disable(self, plugin_id: str) -> bool:
        """
        Calls on_disable, cleans up instances.
        Transitions to DISABLED.
        """
        if plugin_id not in self._instances:
            if plugin_id in self._statuses:
                self._statuses[plugin_id] = PluginStatus.DISABLED
            return True
            
        instance = self._instances[plugin_id]
        
        try:
            instance.on_disable()
        except Exception as e:
            logger.error(f"Error disabling plugin {plugin_id}: {e}")
            
        del self._instances[plugin_id]
        self._statuses[plugin_id] = PluginStatus.DISABLED
        logger.info(f"Disabled plugin: {plugin_id}")
        
        # A real implementation would also unregister the capabilities from the bridges
        # (e.g. self.skill_bridge.unregister_plugin_skills(plugin_id))
        
        return True
        
    def stop(self):
        """Safely stops all running plugins. Called during JARVIS core shutdown."""
        for pid in list(self._instances.keys()):
            self.disable(pid)

    def _record_crash(self, plugin_id: str):
        """Records a plugin failure for isolation/quarantine purposes."""
        count = self._crash_counts.get(plugin_id, 0) + 1
        self._crash_counts[plugin_id] = count
        if count >= 3:
            self._statuses[plugin_id] = PluginStatus.QUARANTINED
            logger.warning(f"Plugin {plugin_id} has been QUARANTINED due to {count} consecutive failures.")

    def get_plugin_state(self, plugin_id: str) -> Tuple[Optional[PluginManifest], Optional[PluginStatus], Optional[JarvisPlugin]]:
        """Used by Diagnostics (PluginHealthCheck)."""
        return (
            self._manifests.get(plugin_id),
            self._statuses.get(plugin_id),
            self._instances.get(plugin_id)
        )

    @property
    def loaded_plugins(self) -> Dict[str, Any]:
        """Backward-compatible mapping of active plugin instances."""
        return self._instances

    def get_all_tools(self) -> List[Any]:
        """Aggregates all tools exposed across loaded plugins."""
        tools = []
        for instance in self._instances.values():
            if hasattr(instance, "get_tools"):
                tools.extend(instance.get_tools())
        return tools

    def execute_tool(self, tool_name: str, params: Dict[str, Any] = None) -> Any:
        """Executes a tool exposed by loaded plugins with SecurityProxy protection."""
        params = params or {}
        for instance in self._instances.values():
            if hasattr(instance, "get_tools"):
                for t in instance.get_tools():
                    if t.get("name") == tool_name:
                        func = t.get("func") or t.get("function") or t.get("execute")
                        if callable(func):
                            if self.security:
                                return self.security.execute(
                                    f"plugin.tool.{tool_name}",
                                    f"execute_tool {tool_name}",
                                    lambda: func(**params) if params else func()
                                )
                            return func(**params) if params else func()
            if hasattr(instance, "execute"):
                if self.security:
                    return self.security.execute(
                        f"plugin.tool.{tool_name}",
                        f"execute_tool {tool_name}",
                        lambda: instance.execute(tool_name, params)
                    )
                return instance.execute(tool_name, params)
        return None
