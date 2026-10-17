"""
Real-Time System Visualization Service.
Prompt 68 — Real-Time System Visualization.
"""
import logging
import time
from typing import Dict, Any, List, Optional
from collections import deque

from backend.visualization.models import MetricPoint, SystemMetricsSnapshot

logger = logging.getLogger("JARVIS.SystemVisualization")

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


class SystemVisualizationService:
    """
    Manages bounded real-time metric streams and historical trend buffers.
    Does not collect unrelated personal activity.
    Accurately identifies unavailable metrics rather than fabricating data.
    """

    def __init__(self, history_capacity: int = 60, jarvis_core: Optional[Any] = None):
        self.capacity = history_capacity
        self.core = jarvis_core
        self._is_paused = False
        self._last_net_bytes: Optional[tuple[int, int, float]] = None

        # Bounded ring buffers for trend charts
        self._cpu_history: deque[MetricPoint] = deque(maxlen=history_capacity)
        self._ram_history: deque[MetricPoint] = deque(maxlen=history_capacity)
        self._disk_history: deque[MetricPoint] = deque(maxlen=history_capacity)
        self._net_history: deque[MetricPoint] = deque(maxlen=history_capacity)

    def pause(self):
        self._is_paused = True

    def resume(self):
        self._is_paused = False

    def is_paused(self) -> bool:
        return self._is_paused

    def collect_snapshot(self) -> SystemMetricsSnapshot:
        """
        Samples live OS hardware and process metrics using psutil.
        Appends to ring buffers if not paused.
        """
        now = time.time()
        unavailable: List[str] = []

        if not _PSUTIL:
            unavailable.extend(["cpu", "ram", "disk", "network", "processes"])
            return SystemMetricsSnapshot(
                timestamp=now,
                service_health_status="DEGRADED",
                unavailable_metrics=unavailable
            )

        # 1. CPU
        try:
            cpu_val = psutil.cpu_percent(interval=None)
        except Exception:
            cpu_val = 0.0
            unavailable.append("cpu")

        # 2. RAM
        try:
            mem = psutil.virtual_memory()
            ram_pct = mem.percent
            ram_tot = round(mem.total / (1024 ** 3), 2)
            ram_avail = round(mem.available / (1024 ** 3), 2)
        except Exception:
            ram_pct, ram_tot, ram_avail = 0.0, 0.0, 0.0
            unavailable.append("ram")

        # 3. Disk
        try:
            disk = psutil.disk_usage('/')
            disk_pct = disk.percent
            disk_tot = round(disk.total / (1024 ** 3), 2)
            disk_free = round(disk.free / (1024 ** 3), 2)
        except Exception:
            disk_pct, disk_tot, disk_free = 0.0, 0.0, 0.0
            unavailable.append("disk")

        # 4. Network Throughput
        net_sent_rate = 0.0
        net_recv_rate = 0.0
        try:
            net = psutil.net_io_counters()
            sent_bytes = net.bytes_sent
            recv_bytes = net.bytes_recv

            if self._last_net_bytes:
                prev_sent, prev_recv, prev_time = self._last_net_bytes
                dt = max(0.1, now - prev_time)
                try:
                    net_sent_rate = float(round(((sent_bytes - prev_sent) / 1024.0) / dt, 2))
                    net_recv_rate = float(round(((recv_bytes - prev_recv) / 1024.0) / dt, 2))
                except (TypeError, ValueError):
                    net_sent_rate = 0.0
                    net_recv_rate = 0.0

            self._last_net_bytes = (sent_bytes, recv_bytes, now)
        except Exception:
            sent_bytes, recv_bytes = 0, 0
            net_sent_rate = 0.0
            net_recv_rate = 0.0
            unavailable.append("network")

        # 5. Process Count
        try:
            proc_count = len(psutil.pids())
        except Exception:
            proc_count = 0
            unavailable.append("processes")

        # 6. GPU (Identified honestly as unavailable unless platform NVML is active)
        unavailable.append("gpu_utilization")
        unavailable.append("gpu_memory")

        # 7. Subsystem health & active tasks
        active_tasks = 0
        health = "HEALTHY"
        if self.core:
            try:
                if hasattr(self.core, "kernel") and self.core.kernel:
                    active_tasks = len(self.core.kernel.scheduler.get_active_schedules())
            except Exception:
                pass

        snapshot = SystemMetricsSnapshot(
            timestamp=now,
            cpu_percent=cpu_val,
            ram_used_percent=ram_pct,
            ram_total_gb=ram_tot,
            ram_available_gb=ram_avail,
            disk_used_percent=disk_pct,
            disk_total_gb=disk_tot,
            disk_free_gb=disk_free,
            network_sent_bytes=sent_bytes,
            network_recv_bytes=recv_bytes,
            network_sent_rate_kbps=max(0.0, net_sent_rate),
            network_recv_rate_kbps=max(0.0, net_recv_rate),
            gpu_available=False,
            process_count=proc_count,
            active_tasks_count=active_tasks,
            service_health_status=health,
            unavailable_metrics=unavailable
        )

        if not self._is_paused:
            self._cpu_history.append(MetricPoint(timestamp=now, value=cpu_val))
            self._ram_history.append(MetricPoint(timestamp=now, value=ram_pct))
            self._disk_history.append(MetricPoint(timestamp=now, value=disk_pct))
            self._net_history.append(MetricPoint(timestamp=now, value=max(0.0, net_recv_rate)))

        return snapshot

    def get_historical_trends(self) -> Dict[str, List[Dict[str, float]]]:
        return {
            "cpu": [{"timestamp": p.timestamp, "value": p.value} for p in self._cpu_history],
            "ram": [{"timestamp": p.timestamp, "value": p.value} for p in self._ram_history],
            "disk": [{"timestamp": p.timestamp, "value": p.value} for p in self._disk_history],
            "network": [{"timestamp": p.timestamp, "value": p.value} for p in self._net_history]
        }
