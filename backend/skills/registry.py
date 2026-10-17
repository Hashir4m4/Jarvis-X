import os
import logging
from typing import Dict, List, Optional, Any

from .base_skill import BaseSkill
from .parser import SkillMetadataParser, SkillMetadata, SkillValidationError
from backend.core.models import Intent, SkillResult, UserInput, SkillStatus, SkillCategory, JarvisError, ErrorCategory
from .capability_registry import CapabilityRegistry

from .conversation_skill import ConversationSkill
from .system_skill import SystemSkill
from .coding_skill import CodingSkill
from .plan_skill import PlanSkill
from .vault_skill import VaultSkill
from .close_day_skill import CloseDaySkill
from .metrics_skill import MetricsSkill
from .brief_skill import BriefSkill
from .trends_skill import TrendsSkill
from .inbox_skill import InboxSkill
from .memory_skill import MemorySkill
from .desktop_skill import DesktopSkill
from .screen_vision_skill import ScreenVisionSkill
from .browser_skill import BrowserSkill
from .goal_skill import GoalSkill

logger = logging.getLogger("JARVIS.SkillRegistry")

# Central list of all available core skills
ALL_SKILLS = [
    ConversationSkill,
    SystemSkill,
    CodingSkill,
    PlanSkill,
    VaultSkill,
    CloseDaySkill,
    MetricsSkill,
    BriefSkill,
    TrendsSkill,
    InboxSkill,
    MemorySkill,
    DesktopSkill,
    ScreenVisionSkill,
    GoalSkill
]


class SkillRegistry:
    """
    Central discovery, lifecycle, and safe execution registry for JARVIS OS Skills.
    Supports automatic SKILL.md discovery and validation.
    """

    def __init__(self, skills_dir: Optional[str] = None):
        self._skills: Dict[str, BaseSkill] = {}
        self._metadata: Dict[str, SkillMetadata] = {}
        self.capability_registry = CapabilityRegistry()

        if skills_dir and os.path.isdir(skills_dir):
            self.discover_skills(skills_dir)

    def discover_skills(self, skills_dir: str) -> Dict[str, SkillMetadata]:
        """
        Scans a directory for subdirectories containing SKILL.md and parses them.
        """
        if not os.path.exists(skills_dir):
            logger.warning(f"Skills directory not found at: {skills_dir}")
            return {}

        logger.info(f"Scanning for skills in: {skills_dir}")
        discovered = {}

        for entry in os.listdir(skills_dir):
            entry_path = os.path.join(skills_dir, entry)
            if os.path.isdir(entry_path):
                skill_md_path = os.path.join(entry_path, "SKILL.md")
                if os.path.isfile(skill_md_path):
                    try:
                        meta = SkillMetadataParser.parse_file(skill_md_path)
                        self._metadata[meta.name] = meta
                        discovered[meta.name] = meta
                        logger.info(f"Discovered skill '{meta.name}' v{meta.version} with {len(meta.actions)} action(s).")

                        # If a skill instance is already registered for this name, bind metadata
                        if meta.name in self._skills:
                            self._skills[meta.name].metadata = meta
                    except SkillValidationError as e:
                        logger.error(f"Failed to parse skill at '{skill_md_path}': {e}")
                    except Exception as e:
                        logger.error(f"Unexpected error loading skill at '{skill_md_path}': {e}")

        return discovered

    def register(self, skill: BaseSkill):
        """Registers an executable skill in the registry and binds metadata if available."""
        skill_name = skill.name.lower()
        if skill_name in self._metadata and not skill.metadata:
            skill.metadata = self._metadata[skill_name]

        # Register capability status
        category = SkillCategory(skill.category) if skill.category in [c.value for c in SkillCategory] else SkillCategory.UNCATEGORIZED
        self.capability_registry.register_skill_metadata(
            name=skill_name,
            category=category,
            dependencies=skill.dependencies,
            supported_modes=skill.supported_modes
        )

        self._skills[skill_name] = skill
        logger.info(f"Registered Skill Executor: '{skill.name}' ({skill.description})")

    def unregister(self, skill_name: str):
        """Removes a skill from the registry."""
        self._skills.pop(skill_name.lower(), None)

    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """Retrieves an executable skill by name."""
        return self._skills.get(name.lower())

    def get(self, name: str) -> Optional[BaseSkill]:
        """Alias for get_skill."""
        return self.get_skill(name)

    def get_metadata(self, name: str) -> Optional[SkillMetadata]:
        """Retrieves parsed SKILL.md metadata for a skill."""
        return self._metadata.get(name.lower())

    def find_skill_for_intent(self, intent: Intent) -> Optional[BaseSkill]:
        """Finds the registered skill matching an Intent."""
        skill = self._skills.get(intent.skill_name.lower())
        if skill and skill.can_handle(intent):
            return skill

        for candidate in self._skills.values():
            if candidate.can_handle(intent):
                return candidate

        return None

    def execute_intent(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        """
        Safely executes an intent with complete validation and error handling:
        1. Checks skill presence and availability.
        2. Validates required inputs from metadata.
        3. Validates action permissions & availability.
        4. Executes skill and catches runtime errors.
        """
        import time
        start_time = time.time()
        
        skill = self.find_skill_for_intent(intent)
        if not skill:
            return SkillResult(
                success=False,
                status="not_found",
                message=f"Skill '{intent.skill_name}' is not registered.",
                output_text=f"I don't have a registered skill for '{intent.skill_name}'.",
                errors=[JarvisError(category=ErrorCategory.SKILL_MISSING, message=f"Skill {intent.skill_name} not found.")]
            )

        # 1. Check availability
        status = self.capability_registry.get_skill_status(skill.name)
        if status in (SkillStatus.UNAVAILABLE, SkillStatus.DISABLED, SkillStatus.FAILED):
            reason = self.capability_registry.get_skill_reason(skill.name)
            return SkillResult(
                success=False,
                status=status.value,
                message=f"Skill '{skill.name}' is currently {status.value}: {reason}",
                output_text=f"I cannot perform that action right now because the required capability is {status.value}.",
                errors=[JarvisError(category=ErrorCategory.UNKNOWN, message=f"Skill unavailable: {reason}")]
            )

        # 2. Validate required inputs
        validation_errors = skill.validate_inputs(intent)
        if validation_errors:
            err_msg = "; ".join(validation_errors)
            logger.warning(f"Input validation failed for {skill.name}:{intent.action} - {err_msg}")
            return SkillResult(
                success=False,
                status="invalid_input",
                message=err_msg,
                output_text=f"Missing or invalid information needed to execute the request.",
                errors=[JarvisError(category=ErrorCategory.UNKNOWN, message=err_msg)]
            )

        # 3. Execute skill safely
        try:
            result = skill.execute(intent, context)
            result.execution_time_ms = round((time.time() - start_time) * 1000, 2)
            return result
        except Exception as e:
            logger.error(f"Execution error in skill '{skill.name}': {e}", exc_info=True)
            return SkillResult(
                success=False,
                status="execution_failed",
                message=f"Skill execution failed: {str(e)}",
                output_text=f"An error occurred while executing {skill.name}.",
                errors=[JarvisError(category=ErrorCategory.UNKNOWN, message=str(e))],
                execution_time_ms=round((time.time() - start_time) * 1000, 2)
            )

    def match_intent(self, user_input: UserInput) -> Optional[Intent]:
        """Queries skills for custom intent matches."""
        for skill in self._skills.values():
            matched = skill.match_custom_intent(user_input)
            if matched:
                return matched
        return None

    def list_skills(self) -> List[Dict[str, Any]]:
        """Returns metadata for all registered skills."""
        skill_names = set(self._skills.keys()) | set(self._metadata.keys())
        result = []
        for name in skill_names:
            skill = self._skills.get(name)
            meta = self._metadata.get(name) or (skill.metadata if skill else None)
            result.append({
                "name": name,
                "description": meta.description if meta else (skill.description if skill else ""),
                "version": meta.version if meta else "1.0.0",
                "permissions": meta.permissions if meta else [],
                "actions": [act.name for act in meta.actions] if (meta and meta.actions) else (skill.supported_actions if skill else []),
                "is_active": skill is not None
            })
        return result
