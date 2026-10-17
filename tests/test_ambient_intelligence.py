"""
Unit and Integration Tests for Prompt 74 — Ambient Intelligence Mode.
"""
import pytest
import time
from backend.ambient.models import (
    AmbientOperatingMode, AmbientSuggestion, AmbientConfiguration
)
from backend.ambient.service import AmbientIntelligenceService


def test_ambient_intelligence_default_disabled():
    service = AmbientIntelligenceService()
    assert service.mode == AmbientOperatingMode.DISABLED
    assert service.config.enabled is False

    # Emitting suggestions while disabled must return None
    sugg = service.emit_suggestion("Optimization", "Check CPU usage")
    assert sugg is None


def test_ambient_intelligence_enable_pause_disable():
    service = AmbientIntelligenceService()
    service.enable()
    assert service.mode == AmbientOperatingMode.ACTIVE
    assert service.config.enabled is True

    service.pause()
    assert service.mode == AmbientOperatingMode.PAUSED

    # While paused, suggestions are suppressed
    assert service.emit_suggestion("Test", "Test rationale") is None

    service.resume()
    assert service.mode == AmbientOperatingMode.ACTIVE

    service.disable()
    assert service.mode == AmbientOperatingMode.DISABLED


def test_ambient_intelligence_suggestion_and_cooldown():
    cfg = AmbientConfiguration(enabled=True, schedule_start="00:00", schedule_end="23:59", cooldown_seconds=10.0)
    service = AmbientIntelligenceService(config=cfg)
    service.mode = AmbientOperatingMode.ACTIVE

    sugg1 = service.emit_suggestion("Clean Cache", "Disk temp files exceeded 500MB")
    assert sugg1 is not None
    assert sugg1.requires_approval is True
    assert len(service.get_recent_suggestions()) == 1

    # Cooldown should suppress immediate follow-up
    sugg2 = service.emit_suggestion("Clean Cache", "Duplicate notice")
    assert sugg2 is None
