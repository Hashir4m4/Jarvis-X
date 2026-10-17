"""
IoT Device Intelligence Domain Models.
Prompt 78 — IoT Device Intelligence.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class IoTDeviceHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNRESPONSIVE = "UNRESPONSIVE"
    ANOMALOUS = "ANOMALOUS"


@dataclass
class IoTTelemetryPoint:
    device_id: str
    metric_name: str
    value: float
    unit: str
    timestamp: float = field(default_factory=time.time)
    point_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "point_id": self.point_id,
            "device_id": self.device_id,
            "metric_name": self.metric_name,
            "value": self.value,
            "unit": self.unit,
            "timestamp": self.timestamp
        }


@dataclass
class IoTDeviceRegistration:
    device_id: str
    device_name: str
    device_type: str
    group_name: str = "default"
    health_status: IoTDeviceHealth = IoTDeviceHealth.HEALTHY
    registered_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    thresholds: Dict[str, tuple[float, float]] = field(default_factory=dict)  # metric -> (min, max)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_type": self.device_type,
            "group_name": self.group_name,
            "health_status": self.health_status.value,
            "registered_at": self.registered_at,
            "metadata": dict(self.metadata),
            "thresholds": dict(self.thresholds)
        }


@dataclass
class AnomalyEvent:
    event_id: str
    device_id: str
    metric_name: str
    observed_value: float
    expected_range: tuple[float, float]
    detected_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "device_id": self.device_id,
            "metric_name": self.metric_name,
            "observed_value": self.observed_value,
            "expected_range": list(self.expected_range),
            "detected_at": self.detected_at
        }
