import os
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

from backend.core.models import TaskCategory

logger = logging.getLogger("JARVIS.CloudModels")

# Default recommended cloud model identifiers across provider roles
DEFAULT_CLOUD_MODEL_ROLES = {
    "general": "gpt-4o-mini",
    "reasoning": "o3-mini",
    "coding": "claude-3-5-sonnet-20241022",
    "fast": "gpt-4o-mini",
    "vision": "gpt-4o"
}


@dataclass
class CloudModelConfig:
    """Configurable cloud model roles for specialized task execution."""
    general_model: str = DEFAULT_CLOUD_MODEL_ROLES["general"]
    reasoning_model: str = DEFAULT_CLOUD_MODEL_ROLES["reasoning"]
    coding_model: str = DEFAULT_CLOUD_MODEL_ROLES["coding"]
    fast_model: str = DEFAULT_CLOUD_MODEL_ROLES["fast"]
    vision_model: str = DEFAULT_CLOUD_MODEL_ROLES["vision"]

    @classmethod
    def from_config(cls, config: Optional[Dict[str, Any]] = None) -> "CloudModelConfig":
        llm_cfg = (config or {}).get("llm", {})
        roles = llm_cfg.get("cloud_models", {})
        default_model = llm_cfg.get("model", DEFAULT_CLOUD_MODEL_ROLES["general"])

        return cls(
            general_model=roles.get("general") or os.getenv("CLOUD_GENERAL_MODEL", default_model),
            reasoning_model=roles.get("reasoning") or os.getenv("CLOUD_REASONING_MODEL", "o3-mini"),
            coding_model=roles.get("coding") or os.getenv("CLOUD_CODING_MODEL", "claude-3-5-sonnet-20241022"),
            fast_model=roles.get("fast") or os.getenv("CLOUD_FAST_MODEL", "gpt-4o-mini"),
            vision_model=roles.get("vision") or os.getenv("CLOUD_VISION_MODEL", "gpt-4o")
        )

    def get_model_for_task(self, task_category: TaskCategory) -> str:
        """Selects the optimal cloud model role based on the task classification."""
        if task_category == TaskCategory.CODING_TASK:
            return self.coding_model
        elif task_category in (TaskCategory.PLANNING_TASK, TaskCategory.RESEARCH_TASK):
            return self.reasoning_model
        elif task_category in (TaskCategory.COMMAND, TaskCategory.COMPUTER_ACTION):
            return self.fast_model
        elif task_category == TaskCategory.VISION_TASK:
            return self.vision_model
        else:
            return self.general_model
