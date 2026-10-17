"""
Unit and Integration Tests for Prompt 78 — IoT Device Intelligence.
"""
import pytest
import time
from backend.iot.models import (
    IoTDeviceHealth, IoTTelemetryPoint, IoTDeviceRegistration, AnomalyEvent
)
from backend.iot.service import IoTIntelligenceService


def test_iot_device_registration_and_telemetry_ingest():
    service = IoTIntelligenceService(history_limit_per_device=5)
    dev = IoTDeviceRegistration(
        device_id="temp_sensor_01",
        device_name="Server Room Temp",
        device_type="TEMPERATURE",
        thresholds={"temperature": (15.0, 30.0)}
    )
    service.register_device(dev)

    # Ingest within threshold
    p1 = IoTTelemetryPoint(device_id="temp_sensor_01", metric_name="temperature", value=22.5, unit="C")
    assert service.ingest_telemetry(p1) is True
    assert dev.health_status == IoTDeviceHealth.HEALTHY

    records = service.query_telemetry("temp_sensor_01")
    assert len(records) == 1
    assert records[0]["value"] == 22.5


def test_iot_duplicate_telemetry_dropping():
    service = IoTIntelligenceService()
    dev = IoTDeviceRegistration(device_id="pressure_01", device_name="Air Pressure", device_type="BAROMETER")
    service.register_device(dev)

    ts = time.time()
    p1 = IoTTelemetryPoint(device_id="pressure_01", metric_name="pressure", value=101.3, unit="kPa", timestamp=ts)
    p2 = IoTTelemetryPoint(device_id="pressure_01", metric_name="pressure", value=101.3, unit="kPa", timestamp=ts)

    assert service.ingest_telemetry(p1) is True
    # Duplicate with same timestamp and metric must be dropped
    assert service.ingest_telemetry(p2) is False
    assert len(service.query_telemetry("pressure_01")) == 1


def test_iot_anomaly_detection():
    service = IoTIntelligenceService()
    dev = IoTDeviceRegistration(
        device_id="power_meter_01",
        device_name="Rack Power",
        device_type="POWER",
        thresholds={"power_watts": (100.0, 1500.0)}
    )
    service.register_device(dev)

    # Ingest out-of-bound value
    spike = IoTTelemetryPoint(device_id="power_meter_01", metric_name="power_watts", value=2400.0, unit="W")
    assert service.ingest_telemetry(spike) is True
    assert dev.health_status == IoTDeviceHealth.ANOMALOUS

    anomalies = service.get_anomalies("power_meter_01")
    assert len(anomalies) == 1
    assert anomalies[0]["observed_value"] == 2400.0
