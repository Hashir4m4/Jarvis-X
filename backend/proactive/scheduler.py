import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable, Awaitable
import uuid

logger = logging.getLogger(__name__)

class ScheduledTask:
    def __init__(
        self,
        task_id: str,
        target_event: Dict[str, Any],
        scheduled_time: float,
        recurrence: Optional[str] = None,  # "ONE_TIME", "DAILY", "WEEKLY"
        enabled: bool = True
    ):
        self.task_id = task_id
        self.target_event = target_event
        self.scheduled_time = scheduled_time
        self.recurrence = recurrence or "ONE_TIME"
        self.enabled = enabled
        self.last_run_time = 0.0

    def is_due(self, now: float) -> bool:
        return self.enabled and now >= self.scheduled_time

    def calculate_next_run(self):
        if self.recurrence == "DAILY":
            self.scheduled_time += 86400.0
        elif self.recurrence == "WEEKLY":
            self.scheduled_time += 604800.0
        else:
            self.enabled = False  # one time task

class ProactiveScheduler:
    """
    Lightweight scheduler for proactive tasks.
    Every scheduled execution emits an event that routes through Proactive Engine.
    """
    def __init__(self, event_bus):
        self.event_bus = event_bus
        self.tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._loop_task = None

    def schedule_task(self, target_event: Dict[str, Any], delay_seconds: float = 0.0, recurrence: str = "ONE_TIME") -> str:
        task_id = f"sch_{uuid.uuid4().hex[:8]}"
        self.tasks[task_id] = ScheduledTask(
            task_id=task_id,
            target_event=target_event,
            scheduled_time=time.time() + delay_seconds,
            recurrence=recurrence
        )
        logger.info(f"[SCHEDULER] Scheduled task {task_id} for {delay_seconds}s from now (recurrence: {recurrence})")
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        if task_id in self.tasks:
            self.tasks[task_id].enabled = False
            logger.info(f"[SCHEDULER] Cancelled task {task_id}")
            return True
            
        # Try to find by partial match if needed, but strict is safer
        return False

    async def start(self):
        if self._running: return
        self._running = True
        self._loop_task = asyncio.create_task(self._scheduler_loop())
        logger.info("[SCHEDULER] Started.")

    async def stop(self):
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        logger.info("[SCHEDULER] Stopped.")

    async def _scheduler_loop(self):
        while self._running:
            try:
                now = time.time()
                for t_id, task in self.tasks.items():
                    if task.is_due(now):
                        task.last_run_time = now
                        logger.info(f"[SCHEDULER] Executing scheduled task {t_id}")
                        # Emit to event bus for proactive engine
                        if self.event_bus:
                            await self.event_bus.publish("proactive_event", task.target_event)
                        
                        task.calculate_next_run()

                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[SCHEDULER] Error: {e}")
                await asyncio.sleep(1.0)
