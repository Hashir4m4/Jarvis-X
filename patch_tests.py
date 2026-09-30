import os
filepath = r'tests\test_proactive_intelligence.py'
with open(filepath, 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('self.engine.memory = MagicMock()', 'self.engine.memory = AsyncMock()')

test_22_new = '''
    async def test_22_task_engine_integration(self):
        self.engine.task_planner = AsyncMock()
        self.engine.execution_engine = AsyncMock()
        self.engine.task_planner.create_plan.return_value = {"mock": "plan"}
        
        # This will be HIGH priority -> ASK_CONFIRMATION
        event_data = {
            "event_id": "test_disk",
            "event_type": "SYSTEM_EVENT",
            "source": "disk_monitor",
            "priority": "HIGH",
            "payload": {"pct_free": 5, "path": "C:"}
        }
        self.engine.rules[1].last_triggered_at = 0
        notif = await self.engine.handle_event(event_data)
        self.assertIsNotNone(notif)
        self.engine.task_planner.create_plan.assert_not_called()
        self.assertIn("[Requires Confirmation]", notif.message)
        
        # Now trigger a MEDIUM priority -> EXECUTE
        self.engine.rules[1].priority = EventPriority.MEDIUM
        self.engine.rules[1].last_triggered_at = 0
        notif2 = await self.engine.handle_event(event_data)
        self.engine.task_planner.create_plan.assert_called_once()
        self.assertIn("[Auto-Executing]", notif2.message)
'''

import re
code = re.sub(r'    async def test_22_task_engine_integration.*?self\.engine\.task_planner\.create_plan\.assert_called_once\(\)', test_22_new, code, flags=re.DOTALL)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(code)

print("Patched tests")
