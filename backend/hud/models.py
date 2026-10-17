"""
JARVIS HUD 2.0 State and Configuration Models.
Prompt 66 — Advanced JARVIS HUD 2.0.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional
import time


class HUDTheme(str, Enum):
    CYAN_NEON = "cyan_neon"
    AMBER_TACTICAL = "amber_tactical"
    STEALTH_DARK = "stealth_dark"
    OBSIDIAN_PURPLE = "obsidian_purple"


class WidgetType(str, Enum):
    SYSTEM_STATUS = "system_status"
    AI_ASSISTANT_STATUS = "ai_assistant_status"
    WORKFLOW_TASK_VIEW = "workflow_task_view"
    GOALS_PLANNING = "goals_planning"
    NOTIFICATIONS_OVERVIEW = "notifications_overview"
    INTERACTION_STATE = "interaction_state"
    WORKSPACE_PANEL = "workspace_panel"
    AMBIENT_STATUS = "ambient_status"


@dataclass
class WidgetConfig:
    widget_id: str
    widget_type: WidgetType
    title: str
    visible: bool = True
    order: int = 0
    collapsed: bool = False
    custom_settings: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "widget_id": self.widget_id,
            "widget_type": self.widget_type.value if isinstance(self.widget_type, WidgetType) else str(self.widget_type),
            "title": self.title,
            "visible": self.visible,
            "order": self.order,
            "collapsed": self.collapsed,
            "custom_settings": dict(self.custom_settings)
        }


@dataclass
class HUDLayoutPreferences:
    theme: HUDTheme = HUDTheme.CYAN_NEON
    refresh_rate_ms: int = 1000
    high_contrast: bool = False
    screen_reader_hints: bool = True
    compact_mode: bool = False
    widgets: List[WidgetConfig] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "theme": self.theme.value if isinstance(self.theme, HUDTheme) else str(self.theme),
            "refresh_rate_ms": self.refresh_rate_ms,
            "high_contrast": self.high_contrast,
            "screen_reader_hints": self.screen_reader_hints,
            "compact_mode": self.compact_mode,
            "widgets": [w.to_dict() for w in self.widgets]
        }


@dataclass
class HUDStateSnapshot:
    timestamp: float = field(default_factory=time.time)
    system_status: Dict[str, Any] = field(default_factory=dict)
    ai_status: Dict[str, Any] = field(default_factory=dict)
    workflows: Dict[str, Any] = field(default_factory=dict)
    planning: Dict[str, Any] = field(default_factory=dict)
    notifications: Dict[str, Any] = field(default_factory=dict)
    voice_multimodal: Dict[str, Any] = field(default_factory=dict)
    degraded_services: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "system_status": self.system_status,
            "ai_status": self.ai_status,
            "workflows": self.workflows,
            "planning": self.planning,
            "notifications": self.notifications,
            "voice_multimodal": self.voice_multimodal,
            "degraded_services": list(self.degraded_services)
        }
