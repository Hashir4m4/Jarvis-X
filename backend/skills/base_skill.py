from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from backend.core.models import Intent, SkillResult, UserInput
from .parser import SkillMetadata


class BaseSkill(ABC):
    """
    Abstract Base Class for all JARVIS OS Skills.
    Skills encapsulate a functional domain (e.g. System, Metrics, Vault)
    and execute intents using underlying tools or agents.
    """

    def __init__(self, metadata: Optional[SkillMetadata] = None):
        self.metadata = metadata

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for the skill."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of capabilities."""
        pass

    @property
    def supported_actions(self) -> List[str]:
        """List of actions this skill can execute."""
        if self.metadata and self.metadata.actions:
            return self.metadata.action_names
        return []

    @property
    def category(self) -> str:
        """Category of this skill."""
        if self.metadata and self.metadata.category:
            return self.metadata.category
        return "uncategorized"

    @property
    def dependencies(self) -> List[str]:
        """List of required dependencies for this skill (e.g., internet, local_llm)."""
        if self.metadata and self.metadata.dependencies:
            return self.metadata.dependencies
        return []

    @property
    def supported_modes(self) -> List[str]:
        """List of supported AI modes (e.g., LOCAL, ONLINE, HYBRID)."""
        if self.metadata and self.metadata.supported_modes:
            return self.metadata.supported_modes
        return []

    def can_handle(self, intent: Intent) -> bool:
        """Returns True if this skill handles the given intent."""
        return intent.skill_name.lower() == self.name.lower()

    def match_custom_intent(self, user_input: UserInput) -> Optional[Intent]:
        """Optional hook for skills to declare specialized pattern matching."""
        return None

    def validate_inputs(self, intent: Intent) -> List[str]:
        """
        Validates that required inputs defined in metadata are present and match schemas.
        Returns a list of error strings if invalid, or an empty list if valid.
        """
        if not self.metadata:
            return []

        action_meta = self.metadata.get_action(intent.action)
        if not action_meta:
            # Not an error if we don't have metadata for the action, fallback to no validation
            return []

        errors = []
        params = intent.parameters or {}
        missing = [inp for inp in action_meta.required_inputs if inp not in params or params[inp] is None or params[inp] == ""]
        if missing:
            errors.append(f"Missing required input(s) for action '{intent.action}': {', '.join(missing)}")
            
        # Optional: implement basic type checking against input_schema here if needed
        # For now, structural presence is sufficient.

        return errors

    @abstractmethod
    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        """Executes the action specified by the intent."""
        pass
