"""
Unit and Integration Tests for Prompt 68 — Real-Time System Visualization.
"""
import pytest
import sys
import time
from backend.visualization.models import MetricPoint, SystemMetricsSnapshot
from backend.visualization.service import SystemVisualizationService


@pytest.fixture(autouse=True)
def restore_psutil_state(monkeypatch):
    """Ensure test isolation from any suites that assign MagicMock to psutil."""
    import importlib
    from unittest.mock import MagicMock
    import backend.visualization.service as viz_svc

    original_psutil = sys.modules.get("psutil")
    was_mock = isinstance(original_psutil, MagicMock) or getattr(viz_svc, "psutil", None) is None or isinstance(getattr(viz_svc, "psutil", None), MagicMock)

    if was_mock:
        sys.modules.pop("psutil", None)
        try:
            import psutil as real_psutil
            monkeypatch.setitem(sys.modules, "psutil", real_psutil)
            importlib.reload(viz_svc)
        except Exception:
            pass

    yield

    if was_mock and original_psutil is not None:
        sys.modules["psutil"] = original_psutil


def test_system_visualization_snapshot_collection():
    service = SystemVisualizationService(history_capacity=10)
    snapshot = service.collect_snapshot()

    assert isinstance(snapshot, SystemMetricsSnapshot)
    assert snapshot.cpu_percent >= 0.0
    assert snapshot.ram_used_percent >= 0.0
    assert "gpu_utilization" in snapshot.unavailable_metrics
    assert snapshot.gpu_available is False

    trends = service.get_historical_trends()
    assert len(trends["cpu"]) == 1
    assert len(trends["ram"]) == 1


def test_system_visualization_pause_resume():
    service = SystemVisualizationService(history_capacity=10)
    service.collect_snapshot()
    assert len(service.get_historical_trends()["cpu"]) == 1

    service.pause()
    assert service.is_paused() is True

    # Collecting while paused should not append to history
    service.collect_snapshot()
    assert len(service.get_historical_trends()["cpu"]) == 1

    service.resume()
    assert service.is_paused() is False
    service.collect_snapshot()
    assert len(service.get_historical_trends()["cpu"]) == 2


def test_system_visualization_bounded_ring_buffer():
    service = SystemVisualizationService(history_capacity=3)
    for _ in range(5):
        service.collect_snapshot()

    trends = service.get_historical_trends()
    assert len(trends["cpu"]) == 3
    assert len(trends["ram"]) == 3
