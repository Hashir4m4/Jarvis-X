import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger("JARVIS.LLMTelemetry")

class NetworkState:
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"

class CostTracker:
    def __init__(self):
        self.session_cost: float = 0.0
        self.daily_cost: float = 0.0
        self.provider_usage: Dict[str, float] = {}
        self.token_usage: Dict[str, int] = {}
        self.timeouts: int = 0
        self.fallback_count: int = 0
        
    def add_cost(self, provider: str, cost: float, tokens: int = 0):
        self.session_cost += cost
        self.daily_cost += cost
        self.provider_usage[provider] = self.provider_usage.get(provider, 0.0) + cost
        self.token_usage[provider] = self.token_usage.get(provider, 0) + tokens
        
    def record_timeout(self):
        self.timeouts += 1
        
    def record_fallback(self):
        self.fallback_count += 1

    def get_summary(self) -> Dict[str, Any]:
        return {
            "session_cost": round(self.session_cost, 4),
            "daily_cost": round(self.daily_cost, 4),
            "provider_costs": self.provider_usage,
            "provider_tokens": self.token_usage,
            "timeouts": self.timeouts,
            "fallbacks": self.fallback_count
        }

class NetworkDetector:
    """Detects actual network reachability rather than just local interface state."""
    
    def __init__(self):
        self.current_state = NetworkState.UNKNOWN
        self.last_latency_ms = 0.0
        
    def check_network(self) -> str:
        """Ping a highly available endpoint to verify true internet access."""
        try:
            import urllib.request
            start = time.time()
            # Fast timeout for detection
            urllib.request.urlopen('http://1.1.1.1', timeout=1.0)
            latency = (time.time() - start) * 1000
            self.last_latency_ms = latency
            
            if latency > 800:
                self.current_state = NetworkState.DEGRADED
            else:
                self.current_state = NetworkState.ONLINE
                
            return self.current_state
        except Exception:
            self.current_state = NetworkState.OFFLINE
            return self.current_state

# Global singleton
cost_tracker = CostTracker()
network_detector = NetworkDetector()
