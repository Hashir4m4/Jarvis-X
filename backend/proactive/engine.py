import asyncio
import logging
import time
from typing import Dict, Any, List, Optional

from .models import (
    JarvisEvent, EventType, EventPriority, NotificationMode,
    ConditionRule, Reminder, ProactiveNotification, RecurrencePattern, EventState
)
import heapq
from .monitors import MonitorRegistry
from .storage import ProactiveStorage
from backend.orchestrator.decision_engine import DecisionEngine, DecisionAction
from backend.core.models import UserInput, InputChannel
from .scheduler import ProactiveScheduler
import asyncio


logger = logging.getLogger("JARVIS.ProactiveEngine")


class ProactiveEngine:
    """
    Controlled Proactive Intelligence and Event Monitoring Engine:
    - Evaluates ConditionRules against incoming JarvisEvents.
    - Anti-Spam protection: Cooldowns, deduplication, and rate limiting.
    - Quiet Mode & Focus Mode enforcement.
    - Generates proactive suggestions without automatic execution of risky actions.
    - Reminders management (One-time, Daily, Weekly).
    - EventBus publisher for HUD alerts and TTS speech requests.
    """

    def __init__(self, event_bus=None, monitor_registry=None, storage=None, config=None, memory_system=None, task_planner=None, execution_engine=None, security_proxy=None, orchestrator=None, decision_engine=None):

        self.event_bus = event_bus
        self.monitors = monitor_registry or MonitorRegistry(event_bus=self.event_bus)
        self.storage = storage or ProactiveStorage()
        self.config = config or {}
        self.memory = memory_system
        self.task_planner = task_planner
        self.execution_engine = execution_engine
        self.decision_engine = decision_engine or DecisionEngine()
        self.security_proxy = security_proxy
        self.orchestrator = orchestrator
        self.scheduler = ProactiveScheduler(event_bus)

        self.notification_mode: NotificationMode = NotificationMode.NORMAL
        self.rules: List[ConditionRule] = []
        self.reminders: List[Reminder] = []
        self._last_event_hashes: Dict[str, float] = {}
        self._event_spam_counts: Dict[str, int] = {}
        self._running = False
        self._reminder_loop_task: Optional[asyncio.Task] = None
        self._is_user_busy: bool = False
        self._acknowledged_sources: set = set()

        # Telemetry
        self.stats = {
            "events_detected": 0,
            "events_suppressed": 0,
            "events_notified": 0,
            "events_acknowledged": 0
        }

        # Priority Queue for notifications
        self._notification_queue: List[tuple] = []
        self._queue_lock = asyncio.Lock()
        self._queue_processor_task: Optional[asyncio.Task] = None

        self._load_or_initialize_state()

    def _load_or_initialize_state(self):
        """Loads state from storage or seeds default rules."""
        state = self.storage.load_state()
        try:
            self.notification_mode = NotificationMode(state.get("notification_mode", "NORMAL"))
        except Exception:
            self.notification_mode = NotificationMode.NORMAL

        # Load persisted rules or defaults
        raw_rules = state.get("rules", [])
        if raw_rules:
            for r in raw_rules:
                try:
                    self.rules.append(ConditionRule(
                        rule_id=r["rule_id"],
                        name=r["name"],
                        source_event_type=EventType(r["source_event_type"]),
                        condition_type=r["condition_type"],
                        target_key=r["target_key"],
                        threshold_value=r["threshold_value"],
                        priority=EventPriority(r.get("priority", "MEDIUM")),
                        cooldown_seconds=r.get("cooldown_seconds", 300.0),
                        notification_template=r.get("notification_template", "{message}"),
                        proactive_suggestion=r.get("proactive_suggestion"),
                        enabled=r.get("enabled", True),
                        last_triggered_at=r.get("last_triggered_at", 0.0)
                    ))
                except Exception as e:
                    logger.debug(f"Error parsing rule: {e}")
        else:
            self._seed_default_rules()

        # Load reminders
        raw_reminders = state.get("reminders", [])
        for rem in raw_reminders:
            try:
                self.reminders.append(Reminder(
                    reminder_id=rem["reminder_id"],
                    message=rem["message"],
                    scheduled_time=rem["scheduled_time"],
                    recurrence=RecurrencePattern(rem.get("recurrence", "ONE_TIME")),
                    priority=EventPriority(rem.get("priority", "MEDIUM")),
                    enabled=rem.get("enabled", True),
                    delivered=rem.get("delivered", False),
                    created_at=rem.get("created_at", time.time())
                ))
            except Exception as e:
                logger.debug(f"Error parsing reminder: {e}")

    def _seed_default_rules(self):
        """Seeds built-in non-intrusive monitoring rules."""
        # 1. Low Battery Alert
        self.rules.append(ConditionRule(
            rule_id="rule_battery_low",
            name="Low Battery Alert",
            source_event_type=EventType.SYSTEM_EVENT,
            condition_type="threshold_below",
            target_key="percent",
            threshold_value=20.0,
            priority=EventPriority.MEDIUM,
            cooldown_seconds=600.0,  # 10 minutes cooldown
            notification_template="Laptop battery is low ({percent}%). Please plug in your charger.",
            proactive_suggestion="Would you like to enable power saver mode?"
        ))

        # 2. Critical Disk Space Alert
        self.rules.append(ConditionRule(
            rule_id="rule_disk_low",
            name="Critically Low Disk Space",
            source_event_type=EventType.SYSTEM_EVENT,
            condition_type="threshold_below",
            target_key="pct_free",
            threshold_value=10.0,
            priority=EventPriority.HIGH,
            cooldown_seconds=1800.0,  # 30 minutes cooldown
            notification_template="Disk space is critically low ({pct_free}% free on {path}).",
            proactive_suggestion="I can help scan for temporary files and large caches."
        ))

        # 3. Local Model Server Offline
        self.rules.append(ConditionRule(
            rule_id="rule_local_ai_offline",
            name="Local AI Offline",
            source_event_type=EventType.SYSTEM_EVENT,
            condition_type="equals",
            target_key="status",
            threshold_value="OFFLINE",
            priority=EventPriority.MEDIUM,
            cooldown_seconds=900.0,  # 15 minutes cooldown
            notification_template="Local AI model server (Ollama) appears to be offline.",
            proactive_suggestion="Would you like me to diagnose local server connectivity?"
        ))

        # 4. Task Completed Event
        self.rules.append(ConditionRule(
            rule_id="rule_task_completed",
            name="Task Completion Notice",
            source_event_type=EventType.TASK_EVENT,
            condition_type="equals",
            target_key="status",
            threshold_value="COMPLETED",
            priority=EventPriority.LOW,
            cooldown_seconds=5.0,
            notification_template="Task '{goal}' has completed successfully.",
            proactive_suggestion=None
        ))

    def save_state(self):
        """Persists current proactive state to disk."""
        self.storage.save_state(
            notification_mode=self.notification_mode,
            monitors=self.monitors._monitors,
            rules=self.rules,
            reminders=self.reminders
        )

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Notification & Quiet Mode Governance
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def set_notification_mode(self, mode: NotificationMode):
        self.notification_mode = mode
        logger.info(f"[PROACTIVE_ENGINE] Notification mode set to: {mode.value}")
        self.save_state()

    def should_deliver(self, priority: EventPriority) -> bool:
        """Enforces Quiet Mode and Focus Mode policies."""
        if self.notification_mode == NotificationMode.NORMAL:
            return True

        if self.notification_mode == NotificationMode.QUIET:
            return priority in (EventPriority.MEDIUM, EventPriority.HIGH, EventPriority.CRITICAL)

        if self.notification_mode == NotificationMode.FOCUS:
            return priority in (EventPriority.HIGH, EventPriority.CRITICAL)

        if self.notification_mode == NotificationMode.DO_NOT_DISTURB:
            return priority == EventPriority.CRITICAL

        return True

    def _calculate_importance_score(self, event: JarvisEvent, rule: ConditionRule, spam_count: int) -> int:
        """Context Evaluator: Calculates an importance score from 0 (Ignore) to 5 (Critical)."""
        score = 1

        # Base priority weight
        if rule.priority == EventPriority.CRITICAL:
            score = 5
        elif rule.priority == EventPriority.HIGH:
            score = 4
        elif rule.priority == EventPriority.IMPORTANT:
            score = 3
        elif rule.priority == EventPriority.MEDIUM:
            score = 2

        # Frequency weight (high frequency implies importance if it persists)
        if spam_count > 5 and score < 4:
            score += 1

        # Context weight
        if self._is_user_busy and score < 4:
            # Suppress non-critical alerts when busy
            score -= 1

        # Ensure bounds
        return max(0, min(5, score))

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Event Ingestion & Evaluation Pipeline
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def handle_event(self, event_data: Dict[str, Any]) -> Optional[ProactiveNotification]:
        """
        Main entry point for incoming events.
        Applies deduplication, evaluates rules, verifies cooldowns, and routes delivery.
        """
        try:
            event = JarvisEvent(
                event_id=event_data.get("event_id"),
                event_type=EventType(event_data.get("event_type")),
                source=event_data.get("source", "system"),
                timestamp=event_data.get("timestamp", time.time()),
                payload=event_data.get("payload", {}),
                priority=EventPriority(event_data.get("priority", "LOW")),
                related_task_id=event_data.get("related_task_id")
            )
        except Exception as e:
            logger.debug(f"[PROACTIVE_ENGINE] Malformed event dropped: {e}")
            return None

        self.stats["events_detected"] += 1

        # If source is acknowledged, suppress
        if event.source in self._acknowledged_sources:
            self.stats["events_suppressed"] += 1
            return None

        # Anti-spam: Duplicate detection across identical metric/value pairs within cooldown window
        event_signature = f"{event.source}:{event.payload.get('metric') or event.payload.get('service')}:{event.payload.get('percent') or event.payload.get('status')}"
        now = time.time()
        last_seen = self._last_event_hashes.get(event_signature, 0.0)

        self._event_spam_counts[event_signature] = self._event_spam_counts.get(event_signature, 0) + 1
        spam_count = self._event_spam_counts[event_signature]

        if now - last_seen < 10.0 and spam_count < 10:
            logger.debug(f"[PROACTIVE_ENGINE] Suppressed duplicate event: {event_signature}")
            self.stats["events_suppressed"] += 1
            return None
        self._last_event_hashes[event_signature] = now
        self._event_spam_counts[event_signature] = 0 # reset after processing

        # Evaluate against active rules
        for rule in self.rules:
            if rule.evaluate(event):
                # Check cooldown
                if now - rule.last_triggered_at < rule.cooldown_seconds and spam_count < 10:
                    logger.debug(f"[PROACTIVE_ENGINE] Rule '{rule.rule_id}' suppressed by cooldown.")
                    continue

                rule.last_triggered_at = now
                self.save_state()

                # Context Evaluator: Importance Scoring
                importance_score = self._calculate_importance_score(event, rule, spam_count)
                event.importance_score = importance_score

                # Format notification message with correlation support
                if spam_count >= 10:
                    formatted_msg = f"Repeated events detected: {rule.name} occurred rapidly {spam_count} times."
                else:
                    try:
                        formatted_msg = rule.notification_template.format(**event.payload)
                    except Exception:
                        formatted_msg = rule.name

                # Check quiet mode delivery policy
                if not self.should_deliver(rule.priority) or importance_score < 1:
                    logger.info(f"[PROACTIVE_ENGINE] Notification '{rule.name}' suppressed by mode or low importance.")
                    event.state = EventState.IGNORED
                    self.stats["events_suppressed"] += 1
                    continue


                notif = ProactiveNotification(
                    title=rule.name,
                    message=formatted_msg,
                    priority=rule.priority,
                    importance_score=importance_score,
                    suggestion=rule.proactive_suggestion,
                    source_rule_id=rule.rule_id,
                    timestamp=now
                )

                # Decision Engine
                decision = self.decision_engine.evaluate(event, rule.proactive_suggestion)

                if decision == DecisionAction.EXECUTE and self.orchestrator:
                    goal = rule.proactive_suggestion or f"Address {rule.name}"
                    logger.info(f"[PROACTIVE_ENGINE] Routing proactive event execution via orchestrator for source: {event.source}")
                    # Wrap in UserInput and submit to Orchestrator
                    user_input = UserInput(
                        content=f"PROACTIVE_EVENT: {event.payload.get('message', event.source)} | SUGGESTION: {goal}",
                        channel=InputChannel.SCHEDULED,
                        metadata={
                            "proactive": True,
                            "source": event.source,
                            "importance": importance_score,
                            "event_data": event.payload
                        }
                    )
                    # Dispatch async so we don't block the engine loop
                    asyncio.create_task(self.orchestrator.process_request(user_input))
                    notif.message += " [Auto-Executing]"
                elif decision == DecisionAction.ASK_CONFIRMATION:
                    notif.message += " [Requires Confirmation]"
                    event.state = EventState.NOTIFIED

                if self.memory and importance_score >= 3:
                    self.memory.write_memory(f"Proactive Alert: {formatted_msg}", memory_type="proactive")

                # Broadcast notification to Queue

                async with self._queue_lock:
                    # heapq sorts by first element. We want highest score first, so negative.
                    heapq.heappush(self._notification_queue, (-importance_score, now, notif))
                self.stats["events_notified"] += 1
                return notif

        return None

    def acknowledge_event(self, source: str):
        """Acknowledges an event source, suppressing future similar events."""
        self._acknowledged_sources.add(source)
        self.stats["events_acknowledged"] += 1
        logger.info(f"[PROACTIVE_ENGINE] User acknowledged source: {source}")

    async def _process_notification_queue(self):
        """Processes notifications with priority ordering."""
        while self._running:
            try:
                notif = None
                async with self._queue_lock:
                    if self._notification_queue:
                        _, _, notif = heapq.heappop(self._notification_queue)

                if notif:
                    await self._dispatch_notification(notif)
                    # Simple rate limit cooldown after dispatch
                    await asyncio.sleep(2.0)
                else:
                    await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[PROACTIVE_ENGINE] Queue processor error: {e}")
                await asyncio.sleep(1.0)

    async def _dispatch_notification(self, notif: ProactiveNotification):
        """Emits notification to the EventBus for HUD rendering and Voice synthesis."""
        if self.event_bus:
            try:
                # 1. Broadcast HUD alert
                await self.event_bus.publish("hud_notification", notif.to_hud_payload())
                # 2. If priority is high or medium, request voice speak (respecting non-intrusiveness)
                if notif.priority in (EventPriority.MEDIUM, EventPriority.IMPORTANT, EventPriority.HIGH, EventPriority.CRITICAL) and notif.importance_score >= 2:
                    speech_text = f"{notif.message}"
                    if notif.suggestion:
                        speech_text += f" {notif.suggestion}"
                    await self.event_bus.publish("voice_speak_request", {"text": speech_text})
            except Exception as e:
                logger.debug(f"[PROACTIVE_ENGINE] Notification dispatch error: {e}")

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Reminder Engine
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def add_reminder(
        self,
        message: str,
        scheduled_time: float,
        recurrence: RecurrencePattern = RecurrencePattern.ONE_TIME,
        priority: EventPriority = EventPriority.MEDIUM
    ) -> Reminder:
        """Adds a scheduled reminder."""
        rem = Reminder(
            message=message,
            scheduled_time=scheduled_time,
            recurrence=recurrence,
            priority=priority,
            enabled=True
        )
        self.reminders.append(rem)
        self.save_state()
        logger.info(f"[PROACTIVE_ENGINE] Added reminder '{rem.reminder_id}': '{message}' at {scheduled_time}")
        return rem

    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancels a scheduled reminder by ID."""
        for r in self.reminders:
            if r.reminder_id == reminder_id:
                r.enabled = False
                self.save_state()
                logger.info(f"[PROACTIVE_ENGINE] Cancelled reminder '{reminder_id}'")
                return True
        return False

    def list_reminders(self, active_only: bool = True) -> List[Reminder]:
        if active_only:
            return [r for r in self.reminders if r.enabled and not r.delivered]
        return self.reminders

    async def _check_reminders_loop(self):
        """Periodic background check for due reminders."""
        while self._running:
            try:
                now = time.time()
                for rem in self.reminders:
                    if rem.is_due(now):
                        rem.delivered = True
                        notif = ProactiveNotification(
                            title="Reminder",
                            message=f"Reminder: {rem.message}",
                            priority=rem.priority,
                            timestamp=now
                        )
                        await self._dispatch_notification(notif)

                        # Handle recurrence
                        if rem.recurrence == RecurrencePattern.DAILY:
                            rem.scheduled_time += 86400.0
                            rem.delivered = False
                        elif rem.recurrence == RecurrencePattern.WEEKLY:
                            rem.scheduled_time += 604800.0
                            rem.delivered = False

                        self.save_state()
                await asyncio.sleep(5.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[PROACTIVE_ENGINE] Reminder loop error: {e}")
                await asyncio.sleep(5.0)

    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Lifecycle Management
    # â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    async def start(self):
        """Starts Proactive Engine services and registers EventBus listener."""
        if self._running:
            return
        self._running = True

        # Wire event bus listener for proactive events
        if self.event_bus:
            await self.event_bus.subscribe("proactive_event", self._handle_bus_event)
            await self.event_bus.subscribe("task_progress", self._handle_task_progress_event)

        # Start monitors
        await self.monitors.start()
        await self.scheduler.start()

        # Start reminder ticker
        self._reminder_loop_task = asyncio.create_task(self._check_reminders_loop())
        self._queue_processor_task = asyncio.create_task(self._process_notification_queue())
        logger.info("[PROACTIVE_ENGINE] Proactive Intelligence Engine ONLINE.")

    async def stop(self):
        """Stops Proactive Engine services gracefully."""
        self._running = False
        await self.monitors.stop()
        await self.scheduler.stop()
        if self._reminder_loop_task:
            self._reminder_loop_task.cancel()
        logger.info("[PROACTIVE_ENGINE] Proactive Intelligence Engine offline.")

    async def _handle_bus_event(self, event_type: str, data: Any):
        if isinstance(data, dict):
            await self.handle_event(data)

    async def _handle_task_progress_event(self, event_type: str, data: Any):
        if isinstance(data, dict):
            status = data.get("status")
            if status == "RUNNING":
                self._is_user_busy = True
            elif status in ("COMPLETED", "FAILED", "CANCELLED", "AWAITING_APPROVAL"):
                self._is_user_busy = False

            task_monitor = self.monitors.get_monitor("task_monitor")
            if task_monitor and task_monitor.enabled:
                evt = task_monitor.handle_task_event(data)
                if evt:
                    await self.handle_event(evt.to_dict())
