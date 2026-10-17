"""
JARVIS HUD 2.0 Aggregator and State Engine.
Prompt 66 — Advanced JARVIS HUD 2.0.
"""
import logging
import json
import os
import time
from typing import Dict, Any, List, Optional

from backend.hud.models import (
    HUDTheme, WidgetType, WidgetConfig, HUDLayoutPreferences, HUDStateSnapshot
)

logger = logging.getLogger("JARVIS.HUDService")


class HUDService:
    """
    HUD 2.0 Aggregator Service.
    Aggregates live state across real core subsystems (Core, Workflows, Planning, Voice, System)
    without crashing if any optional subsystem is offline or degraded.
    Persists user layout and theme preferences.
    """

    DEFAULT_CONFIG_PATH = os.path.join("configs", "hud_preferences.json")

    def __init__(self, jarvis_core: Optional[Any] = None, config_path: Optional[str] = None):
        self.core = jarvis_core
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.preferences = self._load_preferences()

    def _default_widgets(self) -> List[WidgetConfig]:
        return [
            WidgetConfig(widget_id="w_sys", widget_type=WidgetType.SYSTEM_STATUS, title="System Telemetry", order=1),
            WidgetConfig(widget_id="w_ai", widget_type=WidgetType.AI_ASSISTANT_STATUS, title="AI Assistant State", order=2),
            WidgetConfig(widget_id="w_tasks", widget_type=WidgetType.WORKFLOW_TASK_VIEW, title="Active Workflows & Tasks", order=3),
            WidgetConfig(widget_id="w_plan", widget_type=WidgetType.GOALS_PLANNING, title="Strategic Goals & Plans", order=4),
            WidgetConfig(widget_id="w_notif", widget_type=WidgetType.NOTIFICATIONS_OVERVIEW, title="Notifications & Alerts", order=5),
            WidgetConfig(widget_id="w_voice", widget_type=WidgetType.INTERACTION_STATE, title="Voice & Interaction", order=6),
        ]

    def _load_preferences(self) -> HUDLayoutPreferences:
        if os.path.isfile(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    widgets = [
                        WidgetConfig(
                            widget_id=w.get("widget_id", "w"),
                            widget_type=WidgetType(w.get("widget_type", "system_status")),
                            title=w.get("title", "Widget"),
                            visible=w.get("visible", True),
                            order=w.get("order", 0),
                            collapsed=w.get("collapsed", False),
                            custom_settings=w.get("custom_settings", {})
                        )
                        for w in data.get("widgets", [])
                    ]
                    return HUDLayoutPreferences(
                        theme=HUDTheme(data.get("theme", HUDTheme.CYAN_NEON.value)),
                        refresh_rate_ms=data.get("refresh_rate_ms", 1000),
                        high_contrast=data.get("high_contrast", False),
                        screen_reader_hints=data.get("screen_reader_hints", True),
                        compact_mode=data.get("compact_mode", False),
                        widgets=widgets or self._default_widgets()
                    )
            except Exception as e:
                logger.warning(f"Failed to load HUD preferences from {self.config_path}: {e}")
        return HUDLayoutPreferences(widgets=self._default_widgets())

    def save_preferences(self, prefs: HUDLayoutPreferences) -> bool:
        self.preferences = prefs
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(prefs.to_dict(), f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save HUD preferences: {e}")
            return False

    def update_theme(self, theme: HUDTheme) -> bool:
        self.preferences.theme = theme
        return self.save_preferences(self.preferences)

    def set_widget_visibility(self, widget_id: str, visible: bool) -> bool:
        for w in self.preferences.widgets:
            if w.widget_id == widget_id:
                w.visible = visible
                return self.save_preferences(self.preferences)
        return False

    def get_snapshot(self) -> HUDStateSnapshot:
        """
        Aggregates real-time state from all available subsystems.
        Guarantees safe degradation with empty/error markers instead of throwing exceptions.
        """
        degraded = []
        system_status: Dict[str, Any] = {"status": "ok"}
        ai_status: Dict[str, Any] = {"status": "idle"}
        workflows: Dict[str, Any] = {"active": [], "count": 0}
        planning: Dict[str, Any] = {"active_goals": 0, "active_plans": 0}
        notifications: Dict[str, Any] = {"unread": 0, "recent": []}
        voice_mm: Dict[str, Any] = {"mic_active": False, "mode": "IDLE", "vision_online": False}

        if not self.core:
            degraded.append("jarvis_core_uninitialized")
            return HUDStateSnapshot(
                system_status={"status": "offline", "error": "JARVIS Core not attached"},
                degraded_services=degraded
            )

        # 1. System Status
        try:
            if hasattr(self.core, "tools") and hasattr(self.core.tools, "system_ctrl"):
                sys_ctrl = self.core.tools.system_ctrl
                info = sys_ctrl.get_system_info()
                system_status.update(info)
            else:
                system_status["note"] = "system_controller_unavailable"
        except Exception as e:
            degraded.append("system_metrics")
            system_status["error"] = str(e)

        # 2. AI Assistant State
        try:
            ai_status = {
                "operating_state": "RUNNING" if getattr(self.core, "_running", False) else "STOPPED",
                "session_id": getattr(self.core, "session_id", "default"),
                "has_brain": self.core.brain is not None,
                "has_memory": self.core.memory is not None,
                "skills_registered": len(self.core.skill_registry.list_skills()) if self.core.skill_registry else 0,
            }
        except Exception as e:
            degraded.append("ai_assistant")
            ai_status["error"] = str(e)

        # 3. Workflows & Executions
        try:
            if hasattr(self.core, "workflow_engine") and self.core.workflow_engine:
                engine = self.core.workflow_engine
                active_execs = [
                    e.to_dict() for e in engine._executions.values()
                    if hasattr(e, "status") and getattr(e.status, "value", str(e.status)) == "RUNNING"
                ]
                workflows = {
                    "active_count": len(active_execs),
                    "total_registered": len(engine._workflows),
                    "recent_executions": active_execs[:5]
                }
            else:
                workflows["status"] = "unloaded"
        except Exception as e:
            degraded.append("workflows")
            workflows["error"] = str(e)

        # 4. Strategic Planning & Goals
        try:
            goals_count = 0
            plans_count = 0
            if hasattr(self.core, "goal_engine") and self.core.goal_engine:
                goals_count = len(self.core.goal_engine.list_goals())
            if hasattr(self.core, "planning_engine") and self.core.planning_engine:
                plans_count = len(self.core.planning_engine.list_plans())
            planning = {
                "goals_count": goals_count,
                "plans_count": plans_count
            }
        except Exception as e:
            degraded.append("planning")
            planning["error"] = str(e)

        # 5. Notifications
        try:
            if hasattr(self.core, "notification_service") and self.core.notification_service:
                notif_svc = self.core.notification_service
                recent = notif_svc.get_history(limit=5)
                unread = notif_svc.get_unread_count()
                notifications = {
                    "unread": unread,
                    "recent": [n.to_dict() for n in recent]
                }
            else:
                notifications["status"] = "service_idle"
        except Exception as e:
            degraded.append("notifications")
            notifications["error"] = str(e)

        # 6. Voice & Multimodal
        try:
            if hasattr(self.core, "voice_manager") and self.core.voice_manager:
                vm = self.core.voice_manager
                voice_mm["mic_active"] = getattr(vm, "_is_active", False)
                voice_mm["state"] = getattr(vm.state, "value", str(vm.state))
                voice_mm["mode"] = getattr(vm.mode, "value", str(vm.mode))
            if hasattr(self.core, "vision_manager") and self.core.vision_manager:
                voice_mm["vision_online"] = True
        except Exception as e:
            degraded.append("voice_multimodal")
            voice_mm["error"] = str(e)

        return HUDStateSnapshot(
            system_status=system_status,
            ai_status=ai_status,
            workflows=workflows,
            planning=planning,
            notifications=notifications,
            voice_multimodal=voice_mm,
            degraded_services=degraded
        )
