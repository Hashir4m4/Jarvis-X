import os
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

try:
    import yaml
    _YAML = True
except ImportError:
    _YAML = False

logger = logging.getLogger(__name__)


class SkillValidationError(Exception):
    """Raised when a SKILL.md file has invalid or missing metadata."""
    pass


@dataclass
class ActionMetadata:
    """Metadata for a single action declared in a SKILL.md."""
    name: str
    description: str
    required_inputs: List[str] = field(default_factory=list)
    output_format: str = "text"
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillMetadata:
    """Parsed metadata and documentation for a JARVIS OS Skill."""
    name: str
    description: str
    version: str = "1.0.0"
    permissions: List[str] = field(default_factory=list)
    actions: List[ActionMetadata] = field(default_factory=list)
    doc_body: str = ""
    file_path: str = ""
    dependencies: List[str] = field(default_factory=list)
    supported_modes: List[str] = field(default_factory=list)
    category: str = "uncategorized"

    def get_action(self, action_name: str) -> Optional[ActionMetadata]:
        """Looks up an action by name."""
        for act in self.actions:
            if act.name.lower() == action_name.lower():
                return act
        return None

    @property
    def action_names(self) -> List[str]:
        return [act.name for act in self.actions]


class SkillMetadataParser:
    """
    Parses SKILL.md markdown files containing YAML frontmatter.
    Extracts metadata, actions, required inputs, permissions, and documentation.
    """

    @classmethod
    def parse_file(cls, file_path: str) -> SkillMetadata:
        """Reads and parses a SKILL.md file from disk."""
        if not os.path.isfile(file_path):
            raise SkillValidationError(f"SKILL.md file not found at: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return cls.parse_content(content, file_path=file_path)
        except Exception as e:
            if isinstance(e, SkillValidationError):
                raise
            raise SkillValidationError(f"Failed to read SKILL.md at {file_path}: {e}")

    @classmethod
    def parse_content(cls, content: str, file_path: str = "") -> SkillMetadata:
        """Parses SKILL.md text content."""
        if not content.strip():
            raise SkillValidationError("SKILL.md content is empty.")

        # Match YAML frontmatter between leading --- delimiters
        frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n?(.*)$"
        match = re.search(frontmatter_pattern, content.strip(), re.DOTALL)

        if not match:
            raise SkillValidationError("SKILL.md is missing YAML frontmatter (enclosed by '---').")

        frontmatter_raw = match.group(1)
        doc_body = match.group(2).strip()

        # Parse YAML frontmatter
        data = cls._parse_yaml(frontmatter_raw)
        if not isinstance(data, dict):
            raise SkillValidationError("YAML frontmatter must be a key-value mapping.")

        # Validate mandatory fields
        name = data.get("name")
        if not name or not isinstance(name, str):
            raise SkillValidationError("SKILL.md frontmatter missing required string field 'name'.")

        description = data.get("description", "")
        if not description or not isinstance(description, str):
            raise SkillValidationError(f"Skill '{name}' missing required string field 'description'.")

        version = str(data.get("version", "1.0.0"))
        category = str(data.get("category", "uncategorized")).lower()
        
        permissions = data.get("permissions", [])
        if not isinstance(permissions, list):
            permissions = [str(permissions)]
            
        dependencies = data.get("dependencies", [])
        if not isinstance(dependencies, list):
            dependencies = [str(dependencies)]
            
        supported_modes = data.get("supported_modes", [])
        if not isinstance(supported_modes, list):
            supported_modes = [str(supported_modes)]

        # Parse actions
        raw_actions = data.get("actions", [])
        if not isinstance(raw_actions, list):
            raw_actions = []

        actions: List[ActionMetadata] = []
        for raw_act in raw_actions:
            if isinstance(raw_act, dict) and "name" in raw_act:
                act_name = str(raw_act["name"])
                act_desc = str(raw_act.get("description", ""))
                req_inputs = raw_act.get("required_inputs", [])
                if not isinstance(req_inputs, list):
                    req_inputs = [str(req_inputs)]
                out_fmt = str(raw_act.get("output_format", "text"))
                in_schema = raw_act.get("input_schema", {})
                if not isinstance(in_schema, dict):
                    in_schema = {}
                out_schema = raw_act.get("output_schema", {})
                if not isinstance(out_schema, dict):
                    out_schema = {}
                    
                actions.append(ActionMetadata(
                    name=act_name,
                    description=act_desc,
                    required_inputs=[str(inp) for inp in req_inputs],
                    output_format=out_fmt,
                    input_schema=in_schema,
                    output_schema=out_schema
                ))

        return SkillMetadata(
            name=name.strip().lower(),
            description=description.strip(),
            version=version,
            permissions=[str(p) for p in permissions],
            actions=actions,
            doc_body=doc_body,
            file_path=file_path,
            dependencies=[str(d) for d in dependencies],
            supported_modes=[str(m).upper() for m in supported_modes],
            category=category
        )

    @classmethod
    def _parse_yaml(cls, yaml_text: str) -> Dict[str, Any]:
        """Parses YAML with PyYAML if available, or using a fallback parser."""
        if _YAML:
            try:
                return yaml.safe_load(yaml_text) or {}
            except Exception as e:
                logger.warning(f"PyYAML failed to parse frontmatter: {e}. Attempting fallback.")

        # Fallback simple key-value / list parser
        result: Dict[str, Any] = {}
        current_list_key = None

        for line in yaml_text.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            # List item
            if line_str.startswith("- ") and current_list_key:
                val = line_str[2:].strip().strip('"').strip("'")
                if current_list_key in result and isinstance(result[current_list_key], list):
                    result[current_list_key].append(val)
                continue

            # Key-value pair
            if ":" in line_str:
                parts = line_str.split(":", 1)
                key = parts[0].strip()
                val = parts[1].strip().strip('"').strip("'")

                if val == "":
                    # Beginning of a list or nested structure
                    result[key] = []
                    current_list_key = key
                else:
                    result[key] = val
                    current_list_key = None

        return result
