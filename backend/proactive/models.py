import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


class EventType(str, enum.Enum):
    """Supported event categories."""
    SYSTEM_EVENT = "SYSTEM_EVENT"
    TASK_EVENT = "TASK_EVENT"
    REMINDER_EVENT = "REMINDER_EVENT"
    MONITOR_EVENT = "MONITOR_EVENT"
    APPLICATION_EVENT = "APPLICATION_EVENT"
    AUTOMATION_EVENT = "AUTOMATION_EVENT"
    NETWORK_EVENT = "NETWORK_EVENT"
    CUSTOM_EVENT = "CUSTOM_EVENT"


class EventPriority(str, enum.Enum):
    """Priority grading for event notification delivery."""
    IGNORE = "IGNORE"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"
    MEDIUM = "MEDIUM"
    IMPORTANT = "IMPORTANT"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class EventState(str, enum.Enum):
    DETECTED = "DETECTED"
    NOTIFIED = "NOTIFIED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IGNORED = "IGNORED"
    SNOOZED = "SNOOZED"
    RESOLVED = "RESOLVED"


class NotificationMode(str, enum.Enum):
    """User quiet and focus filtering modes."""
    NORMAL = "NORMAL"
    QUIET = "QUIET"
    FOCUS = "FOCUS"
    DO_NOT_DISTURB = "DO_NOT_DISTURB"


class MonitorStatus(str, enum.Enum):
    """Operational status of a registered monitor."""
    ACTIVE = "ACTIVE"
    DISABLED = "DISABLED"
    ERROR = "ERROR"
    PAUSED = "PAUSED"


class RecurrencePattern(str, enum.Enum):
    """Recurrence rules for scheduled reminders."""
    ONE_TIME = "ONE_TIME"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


@dataclass
class JarvisEvent:
    """Standardized event data structure across the OS."""
    event_id: str = field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:8]}")
    event_type: EventType = EventType.CUSTOM_EVENT
    source: str = "system"
    timestamp: float = field(default_factory=time.time)
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.LOW
    importance_score: int = 1  # 0 to 5
    sensitivity_level: str = "NORMAL"  # "NORMAL" or "CONFIDENTIAL"
    related_task_id: Optional[str] = None
    state: EventState = EventState.DETECTED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source": self.source,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "priority": self.priority.value,
            "importance_score": self.importance_score,
            "sensitivity_level": self.sensitivity_level,
            "related_task_id": self.related_task_id,
            "state": self.state.value
        }


@dataclass
class MonitorDefinition:
    """Metadata describing a monitor registered in the MonitorRegistry."""
    monitor_id: str
    name: str
    description: str
    event_types: List[EventType] = field(default_factory=list)
    required_capabilities: List[str] = field(default_factory=list)
    interval_seconds: float = 30.0
    enabled: bool = True
    privacy_level: str = "LOCAL_ONLY"
    status: MonitorStatus = MonitorStatus.ACTIVE
    last_poll_time: float = 0.0
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "monitor_id": self.monitor_id,
            "name": self.name,
            "description": self.description,
            "event_types": [e.value for e in self.event_types],
            "required_capabilities": self.required_capabilities,
            "interval_seconds": self.interval_seconds,
            "enabled": self.enabled,
            "privacy_level": self.privacy_level,
            "status": self.status.value,
            "last_poll_time": self.last_poll_time,
            "error_message": self.error_message
        }


@dataclass
class ConditionRule:
    """Evaluates incoming events against safety and notification thresholds."""
    rule_id: str
    name: str
    source_event_type: EventType
    condition_type: str  # "threshold_below", "threshold_above", "equals", "state_change"
    target_key: str
    threshold_value: Any
    priority: EventPriority = EventPriority.MEDIUM
    cooldown_seconds: float = 300.0  # 5 minutes default anti-spam cooldown
    notification_template: str = "{message}"
    proactive_suggestion: Optional[str] = None
    enabled: bool = True
    last_triggered_at: float = 0.0

    def evaluate(self, event: JarvisEvent) -> bool:
        """Evaluates whether an event satisfies this rule's conditions."""
        if not self.enabled:
            return False

        if event.event_type != self.source_event_type:
            return False

        val = event.payload.get(self.target_key)
        if val is None:
            return False

        try:
            if self.condition_type == "threshold_below":
                return float(val) < float(self.threshold_value)
            elif self.condition_type == "threshold_above":
                return float(val) > float(self.threshold_value)
            elif self.condition_type == "equals":
                return str(val).lower() == str(self.threshold_value).lower()
            elif self.condition_type == "state_change":
                # Matches if the value is explicitly not equal to the nominal value
                return str(val).lower() != str(self.threshold_value).lower()
        except Exception:
            return False

        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "source_event_type": self.source_event_type.value,
            "condition_type": self.condition_type,
            "target_key": self.target_key,
            "threshold_value": self.threshold_value,
            "priority": self.priority.value,
            "cooldown_seconds": self.cooldown_seconds,
            "notification_template": self.notification_template,
            "proactive_suggestion": self.proactive_suggestion,
            "enabled": self.enabled,
            "last_triggered_at": self.last_triggered_at
        }


@dataclass
class Reminder:
    """Scheduled user reminder."""
    reminder_id: str = field(default_factory=lambda: f"rem_{uuid.uuid4().hex[:8]}")
    message: str = ""
    scheduled_time: float = field(default_factory=time.time)
    recurrence: RecurrencePattern = RecurrencePattern.ONE_TIME
    priority: EventPriority = EventPriority.MEDIUM
    enabled: bool = True
    delivered: bool = False
    created_at: float = field(default_factory=time.time)

    def is_due(self, current_time: Optional[float] = None) -> bool:
        t = current_time if current_time is not None else time.time()
        return self.enabled and not self.delivered and (t >= self.scheduled_time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reminder_id": self.reminder_id,
            "message": self.message,
            "scheduled_time": self.scheduled_time,
            "recurrence": self.recurrence.value,
            "priority": self.priority.value,
            "enabled": self.enabled,
            "delivered": self.delivered,
            "created_at": self.created_at
        }


@dataclass
class ProactiveNotification:
    """Notification payload sent to the Orchestrator, HUD, and TTS channels."""
    notification_id: str = field(default_factory=lambda: f"notif_{uuid.uuid4().hex[:8]}")
    title: str = "JARVIS Alert"
    message: str = ""
    priority: EventPriority = EventPriority.MEDIUM
    importance_score: int = 1
    suggestion: Optional[str] = None
    source_rule_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    spoken: bool = False

    def to_hud_payload(self) -> Dict[str, Any]:
        return {
            "id": self.notification_id,
            "title": self.title,
            "message": self.message,
            "priority": self.priority.value,
            "importance_score": self.importance_score,
            "suggestion": self.suggestion,
            "timestamp": self.timestamp
        }
