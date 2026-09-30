import os
import re
filepath = r'tests\test_proactive_intelligence.py'
with open(filepath, 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('self.engine.rules[1].priority = EventPriority.MEDIUM\n        self.engine.rules[1].last_triggered_at = 0\n        notif2 = await self.engine.handle_event(event_data)', 
'self.engine.rules[1].priority = EventPriority.MEDIUM\n        self.engine.rules[1].last_triggered_at = 0\n        event_data["priority"] = "MEDIUM"\n        notif2 = await self.engine.handle_event(event_data)')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed event priority in test_22")
