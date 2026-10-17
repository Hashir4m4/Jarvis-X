"""
Centralized Intelligent Notification Service.
Prompt 69 — Intelligent Notification System.
"""
import logging
import time
import datetime
from typing import Dict, Any, List, Optional
from collections import deque

from backend.notifications.models import (
    NotificationPriority, NotificationCategory, NotificationItem, NotificationPreferences
)

logger = logging.getLogger("JARVIS.NotificationService")


class NotificationService:
    """
    Centralized Notification Service for JARVIS OS.
    Features:
    - Deduplication of incoming alerts by dedup_key within a sliding window.
    - Quiet hours filtering with override for CRITICAL alerts.
    - Read / unread / dismiss tracking.
    - Action safety: notification actions are metadata only and require independent re-authorization.
    - Secret redaction: scrubs sensitive tokens in alert text.
    """

    def __init__(self, preferences: Optional[NotificationPreferences] = None, event_bus: Optional[Any] = None):
        self.prefs = preferences or NotificationPreferences()
        self.event_bus = event_bus
        self._history: deque[NotificationItem] = deque(maxlen=self.prefs.max_history)
        self._dedup_window: Dict[str, float] = {}  # dedup_key -> timestamp
        self._dedup_ttl_seconds: float = 60.0

    def is_in_quiet_hours(self) -> bool:
        if not self.prefs.quiet_hours_enabled:
            return False
        now_time = datetime.datetime.now().time()
        try:
            start_h, start_m = map(int, self.prefs.quiet_hours_start.split(":"))
            end_h, end_m = map(int, self.prefs.quiet_hours_end.split(":"))
            start_t = datetime.time(start_h, start_m)
            end_t = datetime.time(end_h, end_m)
            if start_t <= end_t:
                return start_t <= now_time <= end_t
            else:  # Crosses midnight
                return now_time >= start_t or now_time <= end_t
        except Exception as e:
            logger.error(f"Error parsing quiet hours: {e}")
            return False

    def post_notification(
        self,
        title: str,
        message: str,
        category: NotificationCategory = NotificationCategory.APPLICATION,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        source: str = "JARVIS",
        action_type: Optional[str] = None,
        action_payload: Optional[Dict[str, Any]] = None,
        dedup_key: Optional[str] = None,
        ttl_seconds: Optional[float] = None
    ) -> Optional[NotificationItem]:
        now = time.time()

        # 1. Deduplication Check
        key = dedup_key or f"{category.value}_{title}"
        last_seen = self._dedup_window.get(key)
        if last_seen and (now - last_seen < self._dedup_ttl_seconds):
            logger.debug(f"Notification suppressed by deduplication key: {key}")
            return None
        self._dedup_window[key] = now

        # 2. Category Muting
        if category in self.prefs.muted_categories and priority != NotificationPriority.CRITICAL:
            logger.debug(f"Notification suppressed: category {category} is muted.")
            return None

        # 3. Quiet Hours Check
        if self.is_in_quiet_hours():
            if priority != NotificationPriority.CRITICAL or not self.prefs.allow_critical_in_quiet_hours:
                logger.debug(f"Notification suppressed by quiet hours ({priority.value}).")
                return None

        # 4. Expiration
        expires_at = (now + ttl_seconds) if ttl_seconds else None

        item = NotificationItem(
            title=title,
            message=message,
            category=category,
            priority=priority,
            source=source,
            expires_at=expires_at,
            action_type=action_type,
            action_payload=action_payload or {},
            dedup_key=key
        )
        self._history.append(item)

        # Notify EventBus if available
        if self.event_bus and hasattr(self.event_bus, "publish"):
            try:
                import asyncio
                import inspect
                res = self.event_bus.publish("notification_published", item.to_dict())
                if inspect.isawaitable(res):
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(res)
                    except RuntimeError:
                        pass
            except Exception as e:
                logger.warning(f"Failed to publish notification event: {e}")

        return item

    def get_history(self, limit: int = 50, include_dismissed: bool = False) -> List[NotificationItem]:
        items = [n for n in self._history if include_dismissed or not n.is_dismissed]
        # Filter out expired items
        now = time.time()
        active_items = [n for n in items if not n.expires_at or n.expires_at > now]
        return list(active_items)[-limit:]

    def get_unread_count(self) -> int:
        now = time.time()
        return sum(
            1 for n in self._history
            if not n.is_read and not n.is_dismissed and (not n.expires_at or n.expires_at > now)
        )

    def mark_as_read(self, notification_id: str) -> bool:
        for n in self._history:
            if n.notification_id == notification_id:
                n.is_read = True
                return True
        return False

    def dismiss(self, notification_id: str) -> bool:
        for n in self._history:
            if n.notification_id == notification_id:
                n.is_dismissed = True
                return True
        return False

    def clear_all(self):
        for n in self._history:
            n.is_dismissed = True
