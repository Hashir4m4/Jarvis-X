"""
Real-Time System Visualization Models.
Prompt 68 — Real-Time System Visualization.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
import time


@dataclass
class MetricPoint:
    timestamp: float
    value: float


@dataclass
class SystemMetricsSnapshot:
    timestamp: float = field(default_factory=time.time)
    cpu_percent: float = 0.0
    ram_used_percent: float = 0.0
    ram_total_gb: float = 0.0
    ram_available_gb: float = 0.0
    disk_used_percent: float = 0.0
    disk_total_gb: float = 0.0
    disk_free_gb: float = 0.0
    network_sent_bytes: int = 0
    network_recv_bytes: int = 0
    network_sent_rate_kbps: float = 0.0
    network_recv_rate_kbps: float = 0.0
    gpu_percent: Optional[float] = None
    gpu_memory_used_mb: Optional[float] = None
    gpu_available: bool = False
    process_count: int = 0
    active_tasks_count: int = 0
    service_health_status: str = "HEALTHY"
    unavailable_metrics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "cpu_percent": self.cpu_percent,
            "ram_used_percent": self.ram_used_percent,
            "ram_total_gb": self.ram_total_gb,
            "ram_available_gb": self.ram_available_gb,
            "disk_used_percent": self.disk_used_percent,
            "disk_total_gb": self.disk_total_gb,
            "disk_free_gb": self.disk_free_gb,
            "network_sent_bytes": self.network_sent_bytes,
            "network_recv_bytes": self.network_recv_bytes,
            "network_sent_rate_kbps": self.network_sent_rate_kbps,
            "network_recv_rate_kbps": self.network_recv_rate_kbps,
            "gpu_percent": self.gpu_percent,
            "gpu_memory_used_mb": self.gpu_memory_used_mb,
            "gpu_available": self.gpu_available,
            "process_count": self.process_count,
            "active_tasks_count": self.active_tasks_count,
            "service_health_status": self.service_health_status,
            "unavailable_metrics": list(self.unavailable_metrics)
        }
