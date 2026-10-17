import unittest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

from backend.proactive.engine import ProactiveEngine
from backend.proactive.models import (
    JarvisEvent, EventType, EventPriority, NotificationMode, EventState,
    ConditionRule
)
from backend.proactive.monitors import SystemMonitor, MonitorRegistry

class TestProactiveEngine(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.event_bus = AsyncMock()
        self.mock_storage = MagicMock()
        self.mock_storage.load_state.return_value = {} # Always load empty state to use defaults
        
        self.engine = ProactiveEngine(event_bus=self.event_bus, storage=self.mock_storage)
        # Clear cooldowns to ensure test independence
        for rule in self.engine.rules:
            rule.last_triggered_at = 0.0

    async def test_01_event_detection_and_normalization(self):
        # Trigger an event and ensure it's normalized and processed
        event_data = {
            "event_type": "SYSTEM_EVENT",
            "source": "battery_monitor",
            "priority": "MEDIUM",
            "payload": {"percent": 15.0}
        }
        notif = await self.engine.handle_event(event_data)
        self.assertIsNotNone(notif)
        self.assertEqual(notif.priority, EventPriority.MEDIUM)
        
    async def test_02_importance_scoring_and_context(self):
        # A medium priority rule is scored as 2.
        event_data = {
            "event_type": "SYSTEM_EVENT",
            "source": "battery_monitor",
            "priority": "MEDIUM",
            "payload": {"percent": 10.0}
        }
        notif = await self.engine.handle_event(event_data)
        self.assertIsNotNone(notif)
        self.assertEqual(notif.importance_score, 2)
        
        # Test busy context suppression
        self.engine._is_user_busy = True
        # Need to simulate cooldown expiration
        # Instead, trigger a different event to avoid cooldown logic
        self.engine.rules.append(ConditionRule(
            rule_id="test_busy",
            name="Test Busy",
            source_event_type=EventType.SYSTEM_EVENT,
            condition_type="equals",
            target_key="test_busy",
            threshold_value=True,
            priority=EventPriority.LOW,
            cooldown_seconds=0
        ))
        event_data_2 = {
            "event_type": "SYSTEM_EVENT",
            "source": "test_busy_monitor",
            "priority": "MEDIUM",
            "payload": {"test_busy": True}
        }
        notif_busy = await self.engine.handle_event(event_data_2)
        # Should be suppressed because score goes from 1 -> 0, and < 1 is suppressed
        self.assertIsNone(notif_busy)

    async def test_03_deduplication(self):
        # Test that duplicate events inside 10s are suppressed and counted
        event_data = {
            "event_type": "SYSTEM_EVENT",
            "source": "disk_monitor",
            "priority": "HIGH",
            "payload": {"metric": "disk_free", "pct_free": 5.0}
        }
        n1 = await self.engine.handle_event(event_data)
        self.assertIsNotNone(n1)
        
        n2 = await self.engine.handle_event(event_data)
        self.assertIsNone(n2) # Suppressed
        self.assertEqual(self.engine.stats["events_suppressed"], 1)

    async def test_04_quiet_mode(self):
        self.engine.set_notification_mode(NotificationMode.QUIET)
        
        # Create a low priority event
        self.engine.rules.append(ConditionRule(
            rule_id="test_quiet",
            name="Test Quiet",
            source_event_type=EventType.SYSTEM_EVENT,
            condition_type="equals",
            target_key="test_quiet",
            threshold_value=True,
            priority=EventPriority.LOW,
            cooldown_seconds=0
        ))
        
        event_data = {
            "event_type": "SYSTEM_EVENT",
            "source": "test_quiet_monitor",
            "priority": "LOW",
            "payload": {"test_quiet": True}
        }
        notif = await self.engine.handle_event(event_data)
        self.assertIsNone(notif) # Suppressed by quiet mode

    async def test_05_critical_event_passthrough(self):
        self.engine.set_notification_mode(NotificationMode.DO_NOT_DISTURB)
        
        self.engine.rules.append(ConditionRule(
            rule_id="test_crit",
            name="Test Crit",
            source_event_type=EventType.SYSTEM_EVENT,
            condition_type="equals",
            target_key="test_crit",
            threshold_value=True,
            priority=EventPriority.CRITICAL,
            cooldown_seconds=0
        ))
        
        event_data = {
            "event_type": "SYSTEM_EVENT",
            "source": "test_crit_monitor",
            "priority": "CRITICAL",
            "payload": {"test_crit": True}
        }
        notif = await self.engine.handle_event(event_data)
        self.assertIsNotNone(notif) # DND allows CRITICAL
        self.assertEqual(notif.importance_score, 5)

    async def test_06_event_acknowledgement(self):
        self.engine.rules.append(ConditionRule(
            rule_id="test_ack",
            name="Test Ack",
            source_event_type=EventType.SYSTEM_EVENT,
            condition_type="equals",
            target_key="test_ack",
            threshold_value=True,
            priority=EventPriority.HIGH,
            cooldown_seconds=0
        ))
        event_data = {
            "event_type": "SYSTEM_EVENT",
            "source": "test_ack_monitor",
            "payload": {"test_ack": True}
        }
        
        self.engine.acknowledge_event("test_ack_monitor")
        
        notif = await self.engine.handle_event(event_data)
        self.assertIsNone(notif) # Suppressed due to ack
        self.assertGreaterEqual(self.engine.stats["events_acknowledged"], 1)

if __name__ == '__main__':
    unittest.main()
