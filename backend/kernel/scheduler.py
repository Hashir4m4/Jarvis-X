import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Callable, Dict, Any, List, Optional, Union

from backend.core.models import UserInput, InputChannel, CoreResponse

logger = logging.getLogger("JARVIS.Scheduler")


@dataclass
class ScheduledTask:
    """Represents a configured scheduled OS task."""
    task_id: str
    command: str
    schedule_type: str  # "one_time", "interval", "daily"
    schedule_value: Any  # interval seconds (int/float), daily time "HH:MM", or one-time timestamp (float)
    enabled: bool = True
    tts_notify: bool = False
    created_at: float = field(default_factory=time.time)
    last_run: Optional[float] = None
    next_run: Optional[float] = None
    run_count: int = 0
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Scheduler:
    """
    JARVIS OS Unified Task Scheduler.
    Executes one-time, interval, and daily tasks through the central JARVIS Core pipeline:
    SCHEDULE -> JARVIS CORE -> ROUTER -> SKILL -> EXECUTION -> MEMORY -> NOTIFICATION/HUD/TTS
    """

    def __init__(
        self,
        task_manager: Optional[Any] = None,
        core_executor: Optional[Callable[[UserInput], Any]] = None,
        event_bus: Optional[Any] = None,
        storage_path: Optional[str] = None
    ):
        self.task_manager = task_manager
        self.core_executor = core_executor
        self.event_bus = event_bus
        self.storage_path = storage_path or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../configs/schedules.json")
        )

        self._tasks: Dict[str, ScheduledTask] = {}
        self._async_jobs: Dict[str, asyncio.Task] = {}
        self._custom_callbacks: Dict[str, Callable] = {}
        self._history: List[Dict[str, Any]] = []
        self._running = False

        self._load_persisted_schedules()

    def set_core_executor(self, executor: Callable[[UserInput], Any]):
        """Sets the central JARVIS core input processing handler."""
        self.core_executor = executor

    def set_event_bus(self, event_bus: Any):
        """Sets the Kernel event bus for HUD notifications."""
        self.event_bus = event_bus

    # ─────────────────────────────────────────────────────────────
    # Schedule Configuration & Persistence
    # ─────────────────────────────────────────────────────────────

    def _load_persisted_schedules(self):
        """Loads configured schedules from disk."""
        if os.path.isfile(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data.get("tasks", []):
                        task = ScheduledTask(**item)
                        self._tasks[task.task_id] = task
                    self._history = data.get("history", [])[-100:]
                logger.info(f"Loaded {len(self._tasks)} persisted schedules from {self.storage_path}.")
            except Exception as e:
                logger.error(f"Error loading persisted schedules: {e}")
        else:
            self._populate_default_schedules()

    def _populate_default_schedules(self):
        """Creates default configurable daily routines without hardcoding."""
        defaults = [
            ScheduledTask(
                task_id="morning_brief",
                command="What do I need to do today?",
                schedule_type="daily",
                schedule_value="07:00",
                description="Morning brief and action items review",
                tts_notify=True
            ),
            ScheduledTask(
                task_id="plan_today",
                command="Plan today's objectives and priorities.",
                schedule_type="daily",
                schedule_value="09:00",
                description="Daily plan creation and alignment",
                tts_notify=False
            ),
            ScheduledTask(
                task_id="metrics_pull",
                command="Summarize my metrics.",
                schedule_type="daily",
                schedule_value="14:00",
                description="Midday hardware and usage metrics pull",
                tts_notify=False
            ),
            ScheduledTask(
                task_id="close_the_day",
                command="What changed today?",
                schedule_type="daily",
                schedule_value="19:00",
                description="Evening digest and interaction change log",
                tts_notify=True
            )
        ]
        for task in defaults:
            self._tasks[task.task_id] = task
        self.save_schedules()

    def save_schedules(self):
        """Safely persists configured schedules and history to disk."""
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            data = {
                "tasks": [t.to_dict() for t in self._tasks.values()],
                "history": self._history[-100:]
            }
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Saved {len(self._tasks)} schedules to disk.")
        except Exception as e:
            logger.error(f"Failed to persist schedules to {self.storage_path}: {e}")

    # ─────────────────────────────────────────────────────────────
    # Scheduling Operations
    # ─────────────────────────────────────────────────────────────

    def schedule_daily(
        self,
        daily_time: str,
        command: str,
        task_id: Optional[str] = None,
        tts_notify: bool = False,
        description: Optional[str] = None
    ) -> ScheduledTask:
        """Schedules a task to run daily at HH:MM (24-hour time)."""
        tid = task_id or f"daily_{daily_time.replace(':', '')}_{int(time.time())}"
        task = ScheduledTask(
            task_id=tid,
            command=command,
            schedule_type="daily",
            schedule_value=daily_time,
            enabled=True,
            tts_notify=tts_notify,
            description=description
        )
        self.add_task(task)
        return task

    def schedule_interval(
        self,
        interval_seconds: Union[int, float, str] = None,
        command: Union[int, float, str, Callable] = None,
        task_id: Optional[Union[str, Callable]] = None,
        tts_notify: bool = False,
        description: Optional[str] = None,
        **kwargs
    ) -> ScheduledTask:
        """
        Schedules a task to run repeatedly every N seconds.
        Supports both modern (interval_seconds, command, task_id) and legacy (name, interval, coro) signatures.
        """
        # Legacy signature: schedule_interval("job_name", 0.01, coro_func)
        if isinstance(interval_seconds, str) and isinstance(command, (int, float)):
            name = interval_seconds
            interval_val = float(command)
            callback = task_id if callable(task_id) else None
            tid = kwargs.get("task_id", name)
            task = ScheduledTask(
                task_id=tid,
                command=name,
                schedule_type="interval",
                schedule_value=interval_val,
                enabled=True,
                tts_notify=tts_notify,
                description=description
            )
            if callback:
                self._custom_callbacks[tid] = callback
            self.add_task(task)
            return task

        # Modern signature: schedule_interval(interval_seconds=10, command="...", task_id="...")
        interval_val = float(interval_seconds if interval_seconds is not None else kwargs.get("interval", 60))
        cmd_str = str(command) if command is not None else "interval_task"
        tid = str(task_id) if task_id and not callable(task_id) else kwargs.get("task_id", f"interval_{int(interval_val)}s_{int(time.time())}")
        task = ScheduledTask(
            task_id=tid,
            command=cmd_str,
            schedule_type="interval",
            schedule_value=interval_val,
            enabled=True,
            tts_notify=tts_notify,
            description=description
        )
        if callable(task_id):
            self._custom_callbacks[tid] = task_id
        self.add_task(task)
        return task

    def schedule_at(
        self,
        run_at_timestamp: float,
        command: str,
        task_id: Optional[str] = None,
        tts_notify: bool = False,
        description: Optional[str] = None
    ) -> ScheduledTask:
        """Schedules a one-time execution at a target Unix timestamp."""
        tid = task_id or f"onetime_{int(run_at_timestamp)}_{int(time.time())}"
        task = ScheduledTask(
            task_id=tid,
            command=command,
            schedule_type="one_time",
            schedule_value=run_at_timestamp,
            enabled=True,
            tts_notify=tts_notify,
            description=description
        )
        self.add_task(task)
        return task

    def add_task(self, task: ScheduledTask):
        """Registers and starts a scheduled task."""
        self._tasks[task.task_id] = task
        self.save_schedules()

        if self._running:
            self._start_task_job(task)

        self._emit_schedule_update()
        logger.info(f"Scheduled task '{task.task_id}' ({task.schedule_type}: {task.schedule_value}) registered.")

    def cancel_task(self, task_id: str) -> bool:
        """Cancels and removes a scheduled task."""
        if task_id in self._async_jobs:
            self._async_jobs[task_id].cancel()
            del self._async_jobs[task_id]

        if task_id in self._custom_callbacks:
            del self._custom_callbacks[task_id]

        if task_id in self._tasks:
            del self._tasks[task_id]
            self.save_schedules()
            self._emit_schedule_update()
            logger.info(f"Cancelled scheduled task '{task_id}'.")
            return True
        return False

    def get_active_schedules(self) -> List[Dict[str, Any]]:
        """Returns all configured active schedules for HUD visualization."""
        return [t.to_dict() for t in self._tasks.values()]

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent execution logs for scheduled tasks."""
        return self._history[-limit:]

    # ─────────────────────────────────────────────────────────────
    # Execution Engine
    # ─────────────────────────────────────────────────────────────

    def start(self):
        """Starts all scheduled background jobs."""
        if self._running:
            return

        self._running = True
        for task in list(self._tasks.values()):
            if task.enabled:
                self._start_task_job(task)
        logger.info(f"Scheduler ONLINE with {len(self._async_jobs)} active jobs.")

    def stop(self):
        """Stops the scheduler and cancels all background workers."""
        self._running = False
        for task_id, job in self._async_jobs.items():
            if not job.done():
                job.cancel()
        self._async_jobs.clear()
        logger.info("Scheduler stopped.")

    def _start_task_job(self, task: ScheduledTask):
        """Creates an asyncio background loop for a specific scheduled task."""
        if task.task_id in self._async_jobs and not self._async_jobs[task.task_id].done():
            self._async_jobs[task.task_id].cancel()

        if task.schedule_type == "interval":
            job = asyncio.create_task(self._run_interval_loop(task))
        elif task.schedule_type == "daily":
            job = asyncio.create_task(self._run_daily_loop(task))
        elif task.schedule_type == "one_time":
            job = asyncio.create_task(self._run_onetime_job(task))
        else:
            logger.warning(f"Unknown schedule type '{task.schedule_type}' for task '{task.task_id}'.")
            return

        self._async_jobs[task.task_id] = job

    async def _run_interval_loop(self, task: ScheduledTask):
        """Worker loop for recurring interval tasks."""
        interval = float(task.schedule_value)
        while self._running and task.enabled:
            await asyncio.sleep(interval)
            if not self._running or not task.enabled:
                break
            await self.execute_task_now(task)

    async def _run_daily_loop(self, task: ScheduledTask):
        """Worker loop calculating sleep until next target daily time (HH:MM)."""
        while self._running and task.enabled:
            time_str = str(task.schedule_value)
            try:
                target_hour, target_min = map(int, time_str.split(":"))
            except ValueError:
                logger.error(f"Invalid daily time format '{time_str}' for task {task.task_id}. Expected HH:MM.")
                break

            now = datetime.now()
            target = now.replace(hour=target_hour, minute=target_min, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)

            task.next_run = target.timestamp()
            sleep_seconds = max(1.0, (target - now).total_seconds())

            await asyncio.sleep(sleep_seconds)
            if not self._running or not task.enabled:
                break

            await self.execute_task_now(task)

    async def _run_onetime_job(self, task: ScheduledTask):
        """Worker executing at target timestamp then removing task."""
        target_timestamp = float(task.schedule_value)
        task.next_run = target_timestamp
        sleep_seconds = max(0.0, target_timestamp - time.time())

        if sleep_seconds > 0:
            await asyncio.sleep(sleep_seconds)

        if self._running and task.enabled:
            await self.execute_task_now(task)
            self.cancel_task(task.task_id)

    async def execute_task_now(self, task: ScheduledTask) -> Dict[str, Any]:
        """
        Executes a scheduled task through the full OS Core loop:
        SCHEDULE -> JARVIS CORE -> ROUTER -> SKILL -> EXECUTION -> MEMORY -> NOTIFICATION/HUD/TTS
        """
        start_time = time.time()
        task.last_run = start_time
        task.run_count += 1
        logger.info(f"[SCHEDULER:TRIGGER] Executing task '{task.task_id}': '{task.command}'")

        # Check if a custom coroutine callback is attached (e.g. kernel telemetry or test)
        if task.task_id in self._custom_callbacks:
            callback = self._custom_callbacks[task.task_id]
            try:
                if self.task_manager and hasattr(self.task_manager, "spawn"):
                    self.task_manager.spawn(callback(), name=f"scheduled_{task.task_id}")
                elif asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
                return {"task_id": task.task_id, "status": "success", "executed_at": start_time}
            except Exception as e:
                logger.error(f"Error in custom callback for task {task.task_id}: {e}")
                return {"task_id": task.task_id, "status": "error", "error": str(e)}

        user_input = UserInput(
            content=task.command,
            channel=InputChannel.SCHEDULED,
            metadata={"scheduled_task_id": task.task_id, "schedule_type": task.schedule_type}
        )

        response_text = ""
        status = "success"
        execution_time_ms = 0.0

        try:
            if self.core_executor:
                if asyncio.iscoroutinefunction(self.core_executor):
                    result = await self.core_executor(user_input)
                else:
                    result = self.core_executor(user_input)

                if isinstance(result, CoreResponse):
                    response_text = result.text
                    execution_time_ms = result.execution_time_ms
                elif hasattr(result, "response"):
                    response_text = result.response
                    execution_time_ms = getattr(result, "execution_time_ms", 0.0)
                else:
                    response_text = str(result)
            else:
                response_text = "No core executor attached to scheduler."
                status = "error"
        except Exception as e:
            logger.error(f"[SCHEDULER:ERROR] Failed executing scheduled task '{task.task_id}': {e}", exc_info=True)
            response_text = f"Scheduled task error: {str(e)}"
            status = "error"

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        log_entry = {
            "task_id": task.task_id,
            "command": task.command,
            "schedule_type": task.schedule_type,
            "executed_at": start_time,
            "status": status,
            "response": response_text[:300],
            "execution_time_ms": elapsed_ms,
            "tts_notified": task.tts_notify
        }
        self._history.append(log_entry)
        self.save_schedules()

        # Emit telemetry event to EventBus for HUD and Notification systems
        if self.event_bus:
            try:
                await self.event_bus.publish("scheduled_task_executed", log_entry)
                if task.tts_notify and response_text:
                    await self.event_bus.publish("voice_speak_request", {"text": response_text})
            except Exception as e:
                logger.debug(f"EventBus publish error: {e}")

        logger.info(f"[SCHEDULER:COMPLETE] Task '{task.task_id}' finished in {elapsed_ms}ms | Status: {status.upper()}")
        return log_entry

    def _emit_schedule_update(self):
        """Broadcasts active schedules list to the HUD."""
        if self.event_bus and self._running:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.event_bus.publish("schedule_updated", {"schedules": self.get_active_schedules()}))
            except Exception:
                pass
