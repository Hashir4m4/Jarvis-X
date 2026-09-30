"""
JARVIS Plugin Extensibility Ecosystem — Data Models

Defines all enumerations and typed structures for the plugin architecture.
"""
import enum
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


class PluginStatus(str, enum.Enum):
    """The lifecycle state of a plugin."""
    DISCOVERED = "DISCOVERED"          # Found on disk, manifest read
    VALIDATING = "VALIDATING"          # Currently checking compatibility/deps
    VALIDATED = "VALIDATED"            # Ready to be enabled
    AWAITING_APPROVAL = "AWAITING_APPROVAL" # Needs explicit user approval
    ENABLED = "ENABLED"                # Active and registered
    RUNNING = "RUNNING"                # (For plugins with background tasks)
    DISABLED = "DISABLED"              # Intentionally turned off
    VALIDATION_FAILED = "VALIDATION_FAILED" # Manifest/AST check failed
    LOAD_FAILED = "LOAD_FAILED"        # Python import failed
    RUNTIME_FAILED = "RUNTIME_FAILED"  # Crashed during operation
    QUARANTINED = "QUARANTINED"        # Disabled due to repeated failures
    INCOMPATIBLE = "INCOMPATIBLE"      # Requires different JARVIS version


class PluginType(str, enum.Enum):
    """Category of plugin extension."""
    SKILL = "SKILL"
    TOOL = "TOOL"
    AGENT = "AGENT"
    INTEGRATION = "INTEGRATION"
    KNOWLEDGE = "KNOWLEDGE"
    MONITOR = "MONITOR"
    AI_PROVIDER = "AI_PROVIDER"
    UI = "UI"
    AUTOMATION = "AUTOMATION"
    MIXED = "MIXED"  # Provides multiple types


@dataclass
class PluginPrivacy:
    """Privacy requirements declared by the plugin."""
    network_access: bool = False
    cloud_access: bool = False
    local_data_access: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginPrivacy':
        return cls(
            network_access=bool(data.get("network_access", False)),
            cloud_access=bool(data.get("cloud_access", False)),
            local_data_access=bool(data.get("local_data_access", False))
        )


@dataclass
class PluginCompatibility:
    """Version constraints for this plugin."""
    minimum_core_version: str = "1.0.0"
    maximum_core_version: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginCompatibility':
        return cls(
            minimum_core_version=str(data.get("minimum_core_version", "1.0.0")),
            maximum_core_version=data.get("maximum_core_version")
        )


@dataclass
class PluginCapabilityMetadata:
    """Metadata for a capability exposed by the plugin (e.g., a specific Tool)."""
    capability_id: str
    description: str
    risk_level: str = "LOW"
    required_permissions: List[str] = field(default_factory=list)


@dataclass
class PluginManifest:
    """
    Structured manifest loaded from a plugin's plugin.yaml or plugin.json.
    """
    id: str
    name: str
    version: str
    description: str
    author: str = "Unknown"
    plugin_type: PluginType = PluginType.MIXED
    compatibility: PluginCompatibility = field(default_factory=PluginCompatibility)
    privacy: PluginPrivacy = field(default_factory=PluginPrivacy)
    dependencies: List[str] = field(default_factory=list)      # other plugin_ids
    required_permissions: List[str] = field(default_factory=list)
    capabilities: List[PluginCapabilityMetadata] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginManifest':
        try:
            ptype = PluginType(data.get("plugin_type", "MIXED").upper())
        except ValueError:
            ptype = PluginType.MIXED

        capabilities = []
        for c in data.get("capabilities", []):
            capabilities.append(PluginCapabilityMetadata(
                capability_id=c.get("capability_id", ""),
                description=c.get("description", ""),
                risk_level=c.get("risk_level", "LOW"),
                required_permissions=c.get("required_permissions", [])
            ))

        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", "1.0.0"),
            description=data.get("description", ""),
            author=data.get("author", "Unknown"),
            plugin_type=ptype,
            compatibility=PluginCompatibility.from_dict(data.get("compatibility", {})),
            privacy=PluginPrivacy.from_dict(data.get("privacy", {})),
            dependencies=data.get("dependencies", []),
            required_permissions=data.get("required_permissions", []),
            capabilities=capabilities
        )


class PluginError(Exception):
    """Base exception for plugin-related errors."""
    pass


class PluginValidationError(PluginError):
    """Raised when a plugin manifest or source fails static validation."""
    pass
