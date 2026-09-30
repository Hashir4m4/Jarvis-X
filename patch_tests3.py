import os
import re
filepath = r'tests\test_proactive_intelligence.py'
with open(filepath, 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('event_data["priority"] = "MEDIUM"\n        notif2 = await self.engine.handle_event(event_data)', 
'event_data["priority"] = "MEDIUM"\n        event_data["source"] = "disk_monitor_2"\n        notif2 = await self.engine.handle_event(event_data)')

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(code)

print("Fixed event source in test_22")
