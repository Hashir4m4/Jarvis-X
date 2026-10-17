"""
Unit and Integration Tests for Prompt 69 — Intelligent Notification System.
"""
import pytest
import time
from backend.notifications.models import (
    NotificationPriority, NotificationCategory, NotificationItem, NotificationPreferences
)
from backend.notifications.service import NotificationService


def test_notification_service_post_and_unread():
    service = NotificationService()
    n1 = service.post_notification(title="Alert 1", message="Task complete", category=NotificationCategory.TASK_COMPLETION)
    assert n1 is not None
    assert service.get_unread_count() == 1

    service.mark_as_read(n1.notification_id)
    assert service.get_unread_count() == 0


def test_notification_service_deduplication():
    service = NotificationService()
    n1 = service.post_notification(title="Build Failed", message="Error code 500", dedup_key="build_123")
    assert n1 is not None

    # Immediate duplicate should be suppressed
    n2 = service.post_notification(title="Build Failed", message="Error code 500", dedup_key="build_123")
    assert n2 is None
    assert len(service.get_history()) == 1


def test_notification_service_quiet_hours():
    prefs = NotificationPreferences(
        quiet_hours_enabled=True,
        quiet_hours_start="00:00",
        quiet_hours_end="23:59",
        allow_critical_in_quiet_hours=True
    )
    service = NotificationService(preferences=prefs)

    # Normal alert should be suppressed
    n_norm = service.post_notification(title="Note", message="Info", priority=NotificationPriority.NORMAL)
    assert n_norm is None

    # Critical alert should bypass quiet hours
    n_crit = service.post_notification(title="Emergency", message="System halt", priority=NotificationPriority.CRITICAL)
    assert n_crit is not None
    assert len(service.get_history()) == 1


def test_notification_service_dismiss_and_clear():
    service = NotificationService()
    n = service.post_notification(title="Test", message="Testing dismiss")
    assert n is not None
    assert len(service.get_history()) == 1

    service.dismiss(n.notification_id)
    assert len(service.get_history(include_dismissed=False)) == 0
    assert len(service.get_history(include_dismissed=True)) == 1
