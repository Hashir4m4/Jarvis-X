import asyncio
import logging
import uuid
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class TaskManager:
    """
    Manages long-running or background tasks in the Jarvis OS Kernel.
    Allows for tracking, cancelling, and querying task status.
    """
    def __init__(self):
        self._tasks: Dict[str, asyncio.Task] = {}
        self._task_metadata: Dict[str, Dict[str, Any]] = {}

    def spawn(self, coro, name: str = "AnonymousTask", metadata: Optional[Dict[str, Any]] = None) -> str:
        """Spawns a new background task."""
        task_id = str(uuid.uuid4())
        task = asyncio.create_task(self._task_wrapper(task_id, name, coro))
        
        self._tasks[task_id] = task
        self._task_metadata[task_id] = {
            "name": name,
            "status": "running",
            "metadata": metadata or {}
        }
        
        logger.info(f"Spawned task '{name}' (ID: {task_id})")
        return task_id

    async def _task_wrapper(self, task_id: str, name: str, coro):
        """Wraps a coroutine to handle exceptions and cleanup."""
        try:
            result = await coro
            self._task_metadata[task_id]["status"] = "completed"
            self._task_metadata[task_id]["result"] = result
            logger.info(f"Task '{name}' completed successfully.")
        except asyncio.CancelledError:
            self._task_metadata[task_id]["status"] = "cancelled"
            logger.warning(f"Task '{name}' was cancelled.")
            raise
        except Exception as e:
            self._task_metadata[task_id]["status"] = "failed"
            self._task_metadata[task_id]["error"] = str(e)
            logger.error(f"Task '{name}' failed: {e}", exc_info=True)
        finally:
            # We don't delete the metadata so it can be queried later
            # But we can clean up the task reference
            self._tasks.pop(task_id, None)

    def cancel(self, task_id: str) -> bool:
        """Cancels a running task by ID."""
        task = self._tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def get_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Returns the status and metadata of a task."""
        return self._task_metadata.get(task_id)

    def list_running_tasks(self) -> List[Dict[str, Any]]:
        """Lists all currently running tasks."""
        running = []
        for tid, meta in self._task_metadata.items():
            if meta["status"] == "running":
                running.append({"id": tid, **meta})
        return running
