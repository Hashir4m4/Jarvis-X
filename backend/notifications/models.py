"""
Intelligent Notification System Models.
Prompt 69 — Intelligent Notification System.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time
import uuid


class NotificationPriority(str, Enum):
    LOW = "LOW"
    INFO = "INFO"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class NotificationCategory(str, Enum):
    APPLICATION = "application"
    TASK_COMPLETION = "task_completion"
    APPROVAL_REQUEST = "approval_request"
    GOAL_REMINDER = "goal_reminder"
    WORKFLOW_FAILURE = "workflow_failure"
    SYSTEM_HEALTH = "system_health"
    BACKGROUND_UPDATE = "background_update"


@dataclass
class NotificationItem:
    title: str
    message: str
    category: NotificationCategory = NotificationCategory.APPLICATION
    priority: NotificationPriority = NotificationPriority.NORMAL
    source: str = "JARVIS"
    notification_id: str = field(default_factory=lambda: f"notif_{uuid.uuid4().hex[:8]}")
    timestamp: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    is_read: bool = False
    is_dismissed: bool = False
    action_type: Optional[str] = None
    action_payload: Dict[str, Any] = field(default_factory=dict)
    dedup_key: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "title": self.title,
            "message": self.message,
            "category": self.category.value if isinstance(self.category, NotificationCategory) else str(self.category),
            "priority": self.priority.value if isinstance(self.priority, NotificationPriority) else str(self.priority),
            "source": self.source,
            "timestamp": self.timestamp,
            "expires_at": self.expires_at,
            "is_read": self.is_read,
            "is_dismissed": self.is_dismissed,
            "action_type": self.action_type,
            "action_payload": dict(self.action_payload),
            "dedup_key": self.dedup_key
        }


@dataclass
class NotificationPreferences:
    quiet_hours_enabled: bool = False
    quiet_hours_start: str = "22:00"  # HH:MM
    quiet_hours_end: str = "08:00"    # HH:MM
    allow_critical_in_quiet_hours: bool = True
    muted_categories: List[NotificationCategory] = field(default_factory=list)
    max_history: int = 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "quiet_hours_enabled": self.quiet_hours_enabled,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "allow_critical_in_quiet_hours": self.allow_critical_in_quiet_hours,
            "muted_categories": [c.value if isinstance(c, NotificationCategory) else str(c) for c in self.muted_categories],
            "max_history": self.max_history
        }
