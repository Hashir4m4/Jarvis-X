import asyncio
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger(__name__)

class EventBus:
    """
    An asynchronous Publish-Subscribe event bus for inter-agent communication.
    """
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, event_type: str, callback: Callable):
        """Subscribe to an event type with an async callback."""
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            logger.debug(f"Subscribed to event: {event_type}")

    async def unsubscribe(self, event_type: str, callback: Callable):
        """Unsubscribe from an event type."""
        async with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                    logger.debug(f"Unsubscribed from event: {event_type}")
                except ValueError:
                    pass

    async def publish(self, event_type: str, data: Any = None):
        """Publish an event to all subscribers concurrently."""
        async with self._lock:
            callbacks = self._subscribers.get(event_type, []).copy()
        
        if not callbacks:
            return

        logger.debug(f"Publishing event: {event_type} to {len(callbacks)} subscribers")
        
        # Fire and forget tasks for all subscribers to prevent blocking the publisher
        tasks = []
        for callback in callbacks:
            tasks.append(asyncio.create_task(self._safe_execute(callback, event_type, data)))
            
        if tasks:
            # We don't await the gather here because we want true async fire-and-forget
            # But we could if we wanted synchronous event handling
            pass

    async def _safe_execute(self, callback: Callable, event_type: str, data: Any):
        """Executes a callback safely, catching any exceptions."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event_type, data)
            else:
                # Run sync callbacks in thread pool to avoid blocking the event loop
                await asyncio.to_thread(callback, event_type, data)
        except Exception as e:
            logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)
