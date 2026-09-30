import psutil
import logging
from typing import Dict, Any, Optional

from backend.llm.registry import ModelMetadata, ResourceRequirements

logger = logging.getLogger("JARVIS.ResourceManager")

class ResourceManager:
    """Detects available hardware resources to safely gate local model execution."""
    
    def __init__(self):
        self._last_ram_gb = 0.0
        self._last_vram_gb = 0.0
        
    def _detect_ram_gb(self) -> float:
        try:
            mem = psutil.virtual_memory()
            return mem.available / (1024 ** 3)
        except Exception as e:
            logger.warning(f"Failed to detect RAM: {e}")
            return 0.0
            
    def _detect_vram_gb(self) -> float:
        # Since pynvml might not be installed, we will mock VRAM detection
        # In a real environment, we would use GPUtil or pynvml.
        # Fall back to using 0 to indicate no dedicated VRAM detected, 
        # meaning models must rely on RAM.
        return 0.0
        
    def get_available_resources(self) -> Dict[str, float]:
        self._last_ram_gb = self._detect_ram_gb()
        self._last_vram_gb = self._detect_vram_gb()
        
        return {
            "available_ram_gb": round(self._last_ram_gb, 2),
            "available_vram_gb": round(self._last_vram_gb, 2)
        }
        
    def can_load_model(self, metadata: ModelMetadata) -> bool:
        """
        Determines if there is enough available RAM or VRAM to safely load the model
        without crashing the system.
        """
        if metadata.local_or_online != "local":
            return True # Cloud models don't use local resources (significantly)
            
        reqs = metadata.resource_requirements
        if reqs.min_ram_gb == 0.0 and reqs.min_vram_gb == 0.0:
            return True # Unknown requirements, assume it can load
            
        avail = self.get_available_resources()
        ram = avail["available_ram_gb"]
        vram = avail["available_vram_gb"]
        
        # Check VRAM first if specified
        if reqs.min_vram_gb > 0:
            if vram >= reqs.min_vram_gb:
                return True
            if ram >= reqs.min_ram_gb: # Fallback to RAM if VRAM insufficient
                return True
            return False
            
        # Check RAM
        if reqs.min_ram_gb > 0:
            if ram >= reqs.min_ram_gb:
                return True
            return False
            
        return True
