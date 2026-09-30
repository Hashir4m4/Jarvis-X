import logging
import os
import platform
import psutil
from dataclasses import dataclass
from typing import Dict, Any, Optional

from backend.core.models import TaskCategory

logger = logging.getLogger("JARVIS.LocalModels")

# Default recommended local models
DEFAULT_MODEL_ROLES = {
    "general": "qwen2.5-coder:7b",
    "fast": "qwen2.5:1.5b",
    "reasoning": "deepseek-r1:7b",
    "coding": "qwen2.5-coder:7b",
    "vision": "moondream:latest"
}


@dataclass
class LocalModelConfig:
    """Configurable local model roles for specialized task execution."""
    general_model: str = DEFAULT_MODEL_ROLES["general"]
    fast_model: str = DEFAULT_MODEL_ROLES["fast"]
    reasoning_model: str = DEFAULT_MODEL_ROLES["reasoning"]
    coding_model: str = DEFAULT_MODEL_ROLES["coding"]
    vision_model: str = DEFAULT_MODEL_ROLES["vision"]

    @classmethod
    def from_config(cls, config: Optional[Dict[str, Any]] = None) -> "LocalModelConfig":
        llm_cfg = (config or {}).get("llm", {})
        roles = llm_cfg.get("local_models", {})
        default_model = llm_cfg.get("model", DEFAULT_MODEL_ROLES["general"])

        return cls(
            general_model=roles.get("general", default_model),
            fast_model=roles.get("fast", "qwen2.5:1.5b"),
            reasoning_model=roles.get("reasoning", "deepseek-r1:7b"),
            coding_model=roles.get("coding", default_model),
            vision_model=roles.get("vision", "moondream:latest")
        )

    def get_model_for_task(self, task_category: TaskCategory) -> str:
        """Selects the optimal local model role based on the task classification."""
        if task_category == TaskCategory.CODING_TASK:
            return self.coding_model
        elif task_category in (TaskCategory.PLANNING_TASK, TaskCategory.RESEARCH_TASK):
            return self.reasoning_model
        elif task_category in (TaskCategory.COMMAND, TaskCategory.COMPUTER_ACTION):
            return self.fast_model
        else:
            return self.general_model


def detect_hardware_profile() -> Dict[str, Any]:
    """Detects available host hardware resources to guide local model selection."""
    try:
        mem = psutil.virtual_memory()
        raw_total = mem.total
        if isinstance(raw_total, (int, float)):
            total_ram_gb = round(float(raw_total) / (1024 ** 3), 2)
        else:
            total_ram_gb = 8.0
        cpu_cores = int(psutil.cpu_count(logical=True) or 4) if isinstance(psutil.cpu_count(logical=True), (int, float)) else 4
        cpu_phys = int(psutil.cpu_count(logical=False) or cpu_cores) if isinstance(psutil.cpu_count(logical=False), (int, float)) else cpu_cores
    except Exception:
        total_ram_gb = 8.0
        cpu_cores = 4
        cpu_phys = 4

    if not isinstance(total_ram_gb, (int, float)):
        total_ram_gb = 8.0

    # Recommend maximum model size based on available RAM
    if total_ram_gb >= 32.0:
        recommended_tier = "14B-32B"
    elif total_ram_gb >= 16.0:
        recommended_tier = "7B-8B"
    elif total_ram_gb >= 8.0:
        recommended_tier = "3B-7B (Q4_K_M quantized)"
    else:
        recommended_tier = "1B-3B"

    return {
        "os": platform.system(),
        "arch": platform.machine(),
        "cpu_logical_cores": cpu_cores,
        "cpu_physical_cores": cpu_phys,
        "total_ram_gb": total_ram_gb,
        "recommended_model_tier": recommended_tier
    }
