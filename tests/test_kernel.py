import unittest
import asyncio
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.kernel.event_bus import EventBus
from backend.kernel.task_manager import TaskManager
from backend.kernel.scheduler import Scheduler
from backend.kernel.kernel import JarvisKernel

class TestKernel(unittest.IsolatedAsyncioTestCase):
    
    async def test_event_bus_pubsub(self):
        bus = EventBus()
        received = []
        
        async def mock_handler(event_type, data):
            received.append((event_type, data))
            
        await bus.subscribe("test_event", mock_handler)
        await bus.publish("test_event", {"key": "value"})
        
        # Give event loop a tick to process tasks
        await asyncio.sleep(0.01)
        
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0][0], "test_event")
        self.assertEqual(received[0][1], {"key": "value"})

    async def test_task_manager(self):
        manager = TaskManager()
        
        async def dummy_task():
            await asyncio.sleep(0.01)
            return "done"
            
        task_id = manager.spawn(dummy_task(), name="dummy")
        
        # Initially running
        status = manager.get_status(task_id)
        self.assertEqual(status["status"], "running")
        
        # Wait for completion
        await asyncio.sleep(0.05)
        status = manager.get_status(task_id)
        self.assertEqual(status["status"], "completed")
        self.assertEqual(status["result"], "done")

    async def test_scheduler(self):
        manager = TaskManager()
        scheduler = Scheduler(manager)
        
        count = 0
        async def recurring_task():
            nonlocal count
            count += 1
            
        scheduler.schedule_interval("test_job", 0.01, recurring_task)
        scheduler.start()
        
        await asyncio.sleep(0.15)
        scheduler.stop()
        
        self.assertGreaterEqual(count, 1)

    async def test_kernel_init(self):
        kernel = JarvisKernel({"llm": {}})
        self.assertIsNotNone(kernel.event_bus)
        self.assertIsNotNone(kernel.task_manager)
        self.assertIsNotNone(kernel.scheduler)

if __name__ == "__main__":
    unittest.main()
