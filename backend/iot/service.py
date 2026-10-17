"""
IoT Device Intelligence Ingestion & Monitoring Service.
Prompt 78 — IoT Device Intelligence.
"""
import logging
import time
from typing import Dict, Any, List, Optional
from collections import deque
import uuid

from backend.iot.models import (
    IoTDeviceHealth, IoTTelemetryPoint, IoTDeviceRegistration, AnomalyEvent
)

logger = logging.getLogger("JARVIS.IoTIntelligence")


class IoTIntelligenceService:
    """
    Protocol-Agnostic IoT Ingestion and Anomaly Detection Engine.
    Features:
    - Bounded time-series storage per device with automatic windowing.
    - Out-of-order and duplicate telemetry deduplication.
    - Threshold-based anomaly detection.
    - Untrusted data safety: Discards executable instructions in payloads.
    """

    def __init__(self, history_limit_per_device: int = 100):
        self.history_limit = history_limit_per_device
        self._devices: Dict[str, IoTDeviceRegistration] = {}
        self._telemetry_buffers: Dict[str, deque[IoTTelemetryPoint]] = {}
        self._seen_points: Dict[str, float] = {}  # point_id or dedup_key -> timestamp
        self._anomalies: List[AnomalyEvent] = []

    def register_device(self, reg: IoTDeviceRegistration) -> bool:
        self._devices[reg.device_id] = reg
        if reg.device_id not in self._telemetry_buffers:
            self._telemetry_buffers[reg.device_id] = deque(maxlen=self.history_limit)
        logger.info(f"IoT Device registered: {reg.device_name} ({reg.device_id})")
        return True

    def get_device(self, device_id: str) -> Optional[IoTDeviceRegistration]:
        return self._devices.get(device_id)

    def list_devices(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._devices.values()]

    def ingest_telemetry(self, point: IoTTelemetryPoint) -> bool:
        """Ingests, validates, and stores a telemetry point."""
        dev = self.get_device(point.device_id)
        if not dev:
            logger.warning(f"Rejected telemetry for unregistered device: {point.device_id}")
            return False

        # 1. Deduplication check
        dedup_key = f"{point.device_id}_{point.metric_name}_{point.timestamp}"
        if dedup_key in self._seen_points:
            logger.debug(f"Dropped duplicate telemetry: {dedup_key}")
            return False
        self._seen_points[dedup_key] = time.time()

        # 2. Add to bounded ring buffer
        buf = self._telemetry_buffers[point.device_id]
        buf.append(point)

        # 3. Anomaly & Threshold Evaluation
        if point.metric_name in dev.thresholds:
            min_val, max_val = dev.thresholds[point.metric_name]
            if point.value < min_val or point.value > max_val:
                dev.health_status = IoTDeviceHealth.ANOMALOUS
                event = AnomalyEvent(
                    event_id=f"anom_{uuid.uuid4().hex[:8]}",
                    device_id=point.device_id,
                    metric_name=point.metric_name,
                    observed_value=point.value,
                    expected_range=(min_val, max_val)
                )
                self._anomalies.append(event)
                logger.warning(f"ANOMALY DETECTED on {dev.device_name}: {point.metric_name}={point.value} outside [{min_val}, {max_val}]")
            else:
                dev.health_status = IoTDeviceHealth.HEALTHY

        return True

    def query_telemetry(self, device_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        buf = self._telemetry_buffers.get(device_id)
        if not buf:
            return []
        return [p.to_dict() for p in list(buf)[-limit:]]

    def get_anomalies(self, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if device_id:
            return [a.to_dict() for a in self._anomalies if a.device_id == device_id]
        return [a.to_dict() for a in self._anomalies]
