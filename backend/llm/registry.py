import enum
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

class ModelLifecycleState(str, enum.Enum):
    COLD = "COLD"
    LOADING = "LOADING"
    READY = "READY"
    BUSY = "BUSY"
    IDLE = "IDLE"
    UNLOADING = "UNLOADING"
    ERROR = "ERROR"

@dataclass
class ModelCapabilities:
    text_generation: bool = True
    streaming: bool = True
    vision: bool = False
    tool_calling: bool = False
    structured_output: bool = False
    embedding: bool = False

@dataclass
class ResourceRequirements:
    min_ram_gb: float = 0.0
    min_vram_gb: float = 0.0
    recommended_ram_gb: float = 0.0
    recommended_vram_gb: float = 0.0

@dataclass
class ModelMetadata:
    model_id: str
    provider: str
    local_or_online: str  # "local" or "online"
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    context_window: int = 4096
    max_output: int = 1024
    latency_class: str = "normal"  # "low", "normal", "high"
    quality_class: str = "general" # "fast", "general", "reasoning", "coding"
    resource_requirements: ResourceRequirements = field(default_factory=ResourceRequirements)
    availability: bool = False
    cost_class: str = "free"       # "free", "low", "medium", "high"
    lifecycle_state: ModelLifecycleState = ModelLifecycleState.COLD
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": self.provider,
            "local_or_online": self.local_or_online,
            "capabilities": {
                "text_generation": self.capabilities.text_generation,
                "streaming": self.capabilities.streaming,
                "vision": self.capabilities.vision,
                "tool_calling": self.capabilities.tool_calling,
                "structured_output": self.capabilities.structured_output,
                "embedding": self.capabilities.embedding
            },
            "context_window": self.context_window,
            "max_output": self.max_output,
            "latency_class": self.latency_class,
            "quality_class": self.quality_class,
            "resource_requirements": {
                "min_ram_gb": self.resource_requirements.min_ram_gb,
                "min_vram_gb": self.resource_requirements.min_vram_gb,
                "recommended_ram_gb": self.resource_requirements.recommended_ram_gb,
                "recommended_vram_gb": self.resource_requirements.recommended_vram_gb
            },
            "availability": self.availability,
            "cost_class": self.cost_class,
            "lifecycle_state": self.lifecycle_state.value
        }

class ModelRegistry:
    """Central repository for all known models and their capabilities."""
    
    def __init__(self):
        self._models: Dict[str, ModelMetadata] = {}
        self._register_known_models()
        
    def _register_known_models(self):
        # Seed some known local models
        self.register(ModelMetadata(
            model_id="llama3.2:3b",
            provider="ollama",
            local_or_online="local",
            capabilities=ModelCapabilities(tool_calling=True, structured_output=True),
            context_window=8192,
            latency_class="low",
            quality_class="fast",
            resource_requirements=ResourceRequirements(min_ram_gb=4.0)
        ))
        self.register(ModelMetadata(
            model_id="qwen2.5-coder:7b",
            provider="ollama",
            local_or_online="local",
            capabilities=ModelCapabilities(tool_calling=True, structured_output=True),
            context_window=8192,
            latency_class="normal",
            quality_class="coding",
            resource_requirements=ResourceRequirements(min_ram_gb=8.0)
        ))
        
        # Seed some known online models
        self.register(ModelMetadata(
            model_id="gpt-4o",
            provider="openai",
            local_or_online="online",
            capabilities=ModelCapabilities(vision=True, tool_calling=True, structured_output=True),
            context_window=128000,
            latency_class="normal",
            quality_class="reasoning",
            cost_class="high"
        ))
        self.register(ModelMetadata(
            model_id="claude-3-5-sonnet",
            provider="anthropic",
            local_or_online="online",
            capabilities=ModelCapabilities(vision=True, tool_calling=True, structured_output=True),
            context_window=200000,
            latency_class="normal",
            quality_class="reasoning",
            cost_class="medium"
        ))
        
    def register(self, metadata: ModelMetadata):
        self._models[metadata.model_id] = metadata
        
    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        return self._models.get(model_id)
        
    def get_models_by_provider(self, provider: str) -> List[ModelMetadata]:
        return [m for m in self._models.values() if m.provider == provider]

    def get_available_models(self, local_only: bool = False, requires_vision: bool = False, requires_tools: bool = False) -> List[ModelMetadata]:
        results = []
        for m in self._models.values():
            if local_only and m.local_or_online != "local":
                continue
            if requires_vision and not m.capabilities.vision:
                continue
            if requires_tools and not m.capabilities.tool_calling:
                continue
            if m.availability:
                results.append(m)
        return results

    def update_model_availability(self, model_id: str, available: bool, lifecycle_state: ModelLifecycleState = None):
        if model_id in self._models:
            self._models[model_id].availability = available
            if lifecycle_state:
                self._models[model_id].lifecycle_state = lifecycle_state
