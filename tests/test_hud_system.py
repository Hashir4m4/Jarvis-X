"""
Unit and Integration Tests for Prompt 66 — Advanced JARVIS HUD 2.0.
"""
import pytest
import os
import tempfile
from backend.hud.models import HUDTheme, WidgetType, WidgetConfig, HUDLayoutPreferences, HUDStateSnapshot
from backend.hud.service import HUDService


def test_hud_models_serialization():
    widget = WidgetConfig(
        widget_id="w_test",
        widget_type=WidgetType.SYSTEM_STATUS,
        title="Test Widget",
        visible=True,
        order=1
    )
    data = widget.to_dict()
    assert data["widget_id"] == "w_test"
    assert data["widget_type"] == "system_status"
    assert data["visible"] is True

    prefs = HUDLayoutPreferences(
        theme=HUDTheme.STEALTH_DARK,
        refresh_rate_ms=500,
        widgets=[widget]
    )
    prefs_dict = prefs.to_dict()
    assert prefs_dict["theme"] == "stealth_dark"
    assert prefs_dict["refresh_rate_ms"] == 500
    assert len(prefs_dict["widgets"]) == 1


def test_hud_service_preferences_persistence():
    with tempfile.TemporaryDirectory() as tmp_dir:
        cfg_path = os.path.join(tmp_dir, "hud_prefs.json")
        service = HUDService(jarvis_core=None, config_path=cfg_path)

        assert len(service.preferences.widgets) == 6
        assert service.preferences.theme == HUDTheme.CYAN_NEON

        # Update theme and widget visibility
        res = service.update_theme(HUDTheme.AMBER_TACTICAL)
        assert res is True
        assert service.preferences.theme == HUDTheme.AMBER_TACTICAL

        res_vis = service.set_widget_visibility("w_sys", False)
        assert res_vis is True

        # Reload from disk
        service_reloaded = HUDService(jarvis_core=None, config_path=cfg_path)
        assert service_reloaded.preferences.theme == HUDTheme.AMBER_TACTICAL
        w_sys = next(w for w in service_reloaded.preferences.widgets if w.widget_id == "w_sys")
        assert w_sys.visible is False


def test_hud_service_graceful_degradation_without_core():
    service = HUDService(jarvis_core=None)
    snapshot = service.get_snapshot()

    assert isinstance(snapshot, HUDStateSnapshot)
    assert "jarvis_core_uninitialized" in snapshot.degraded_services
    assert snapshot.system_status["status"] == "offline"


def test_hud_service_with_mock_core():
    class MockCore:
        def __init__(self):
            self._running = True
            self.session_id = "test_sess"
            self.brain = object()
            self.memory = object()
            self.skill_registry = type("Reg", (), {"list_skills": lambda self: ["s1", "s2"]})()
            self.workflow_engine = None
            self.goal_engine = None
            self.planning_engine = None
            self.voice_manager = None
            self.notification_service = None

    core = MockCore()
    service = HUDService(jarvis_core=core)
    snapshot = service.get_snapshot()

    assert snapshot.ai_status["operating_state"] == "RUNNING"
    assert snapshot.ai_status["skills_registered"] == 2
    assert snapshot.workflows["status"] == "unloaded"
