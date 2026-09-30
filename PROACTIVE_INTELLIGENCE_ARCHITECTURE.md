# JARVIS OS: Controlled Proactive Intelligence and Event Monitoring Architecture

## 1. Architectural Philosophy & Hierarchy

In JARVIS OS, proactive intelligence is **strictly event-driven, non-intrusive, privacy-aware, and permission-gated**. The system does not continuously poll every sensor by default, flood the user with unnecessary alerts, or execute autonomous recovery actions without approval.

The system adheres to the following controlled processing pipeline:

```
                    EVENT SOURCES
        (OS Telemetry, Tasks, Model Server, Scheduler)
                          │
                          ▼
                    EVENT MONITORS
             (Managed by MonitorRegistry)
                          │
                          ▼
                     EVENT BUS
                (Kernel EventBus)
                          │
                          ▼
              RULE & CONDITION ENGINE
             (Evaluates thresholds & rules)
                          │
                          ▼
            ANTI-SPAM & NOTIFICATION POLICY
         (Cooldowns, Quiet/Focus modes, Deduplication)
                          │
                          ▼
                 JARVIS ORCHESTRATOR
                          │
                          ▼
                  USER NOTIFICATION
               (HUD, Voice, Notification)
```

---

## 2. Core Invariants & Anti-Spam Safety

1. **User-Controlled & Configurable**: Users can enable, disable, inspect, or adjust monitors and rules at any time via Voice, HUD, or Settings.
2. **Strict Cooldown Enforcement**: Every condition rule specifies a mandatory cooldown window (e.g. 5 to 30 minutes) to prevent notification looping when a metric fluctuates near a threshold.
3. **Event Deduplication**: Identical telemetry events arriving within a 10-second window are automatically deduplicated.
4. **Proactive Suggestions Without Autonomous Risk**: When an issue is detected (e.g. Local AI server offline, low disk space), JARVIS generates a suggestion (`"Would you like me to diagnose connectivity?"`) but **never** performs dangerous actions (restarting services, deleting files) autonomously.
5. **Quiet & Focus Modes**:
   - `NORMAL`: Delivers all notifications.
   - `QUIET`: Suppresses `LOW` priority notifications.
   - `FOCUS`: Delivers only `HIGH` and `CRITICAL` priority alerts.
   - `DO_NOT_DISTURB`: Suppresses all notifications except `CRITICAL` alerts.

---

## 3. Data Models (`backend/proactive/models.py`)

- **`JarvisEvent`**: Unified typed event schema across the operating system.
  - Fields: `event_id`, `event_type`, `source`, `timestamp`, `payload`, `priority`, `sensitivity_level`, `related_task_id`.
- **`EventType`**: `SYSTEM_EVENT`, `TASK_EVENT`, `REMINDER_EVENT`, `MONITOR_EVENT`, `APPLICATION_EVENT`, `AUTOMATION_EVENT`, `NETWORK_EVENT`, `CUSTOM_EVENT`.
- **`EventPriority`**: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- **`ConditionRule`**:
  - Evaluates conditions (`threshold_below`, `threshold_above`, `equals`, `state_change`).
  - Contains customizable notification templates and non-intrusive proactive suggestions.
- **`Reminder`**:
  - Scheduled alert with recurrence support (`ONE_TIME`, `DAILY`, `WEEKLY`).
- **`ProactiveNotification`**:
  - Standardized notification payload delivered to HUD alerts and Voice TTS.

---

## 4. Monitor Registry & Built-In Monitors (`backend/proactive/monitors.py`)

The `MonitorRegistry` provides discovery, lifecycle controls, and polling management:

| Monitor ID | Type | Description | Interval | Privacy Level |
| :--- | :--- | :--- | :--- | :--- |
| **`battery_monitor`** | Polling | Checks battery percent and charging state via `psutil`. Emits event when battery drops below 20%. | 60s | `LOCAL_ONLY` |
| **`disk_monitor`** | Polling | Evaluates system storage free space percentage. Emits high-priority alert when below 10%. | 120s | `LOCAL_ONLY` |
| **`model_server_monitor`** | Polling | Probes local AI inference endpoint (`http://localhost:11434`). Emits event on offline state change. | 30s | `LOCAL_ONLY` |
| **`task_monitor`** | Event-Driven | Listens for task progress, completion, or failure from the Task Execution Engine. | Instant | `LOCAL_ONLY` |

---

## 5. Proactive Engine & Anti-Spam Pipeline (`backend/proactive/engine.py`)

The `ProactiveEngine` coordinates event handling:
1. **Deduplication**: Hashes event sources and values; drops repeated events within a 10s window.
2. **Rule Evaluation**: Matches events against active `ConditionRule` definitions.
3. **Cooldown Check**: Ignores triggered rules if `(now - last_triggered) < cooldown_seconds`.
4. **Quiet Mode Filter**: Drops notifications lower than the active `NotificationMode` threshold.
5. **Notification Dispatch**: Emits `hud_notification` and `voice_speak_request` events to the Kernel `EventBus`.
6. **Reminder Engine**: Runs a periodic check loop for scheduled reminders, advancing recurring dates (`DAILY` / `WEEKLY`) upon delivery.

---

## 6. Persistence & Storage (`backend/proactive/storage.py`)

State is persisted safely to `configs/proactive_state.json`:
- Active notification mode (`NORMAL`, `QUIET`, `FOCUS`, `DO_NOT_DISTURB`).
- Registered monitors and their enabled/disabled status.
- Configured condition rules, thresholds, and last triggered timestamps.
- Active and recurring reminders.

---

## 7. Verification & Test Suite

The comprehensive 21-point test suite in [`tests/test_proactive_intelligence.py`](file:///c:/Data/Projects/Jarvis%20X/tests/test_proactive_intelligence.py) verifies:
1. Event creation.
2. Event dispatch through bus.
3. Monitor registration.
4. Battery threshold condition.
5. Disk threshold condition.
6. Task completion event.
7. Reminder scheduling.
8. Recurring reminder.
9. Reminder cancellation.
10. Notification priority filtering.
11. Quiet mode suppression.
12. Focus mode suppression.
13. Duplicate event suppression.
14. Notification cooldown enforcement.
15. Monitor failure isolation.
16. Offline monitoring.
17. Monitor persistence.
18. Disabled monitor behavior.
19. User stops monitoring.
20. Proactive suggestion generation.
21. Proactive system does not automatically execute risky actions.
