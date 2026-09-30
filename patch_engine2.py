import os
filepath = r'backend\proactive\engine.py'
with open(filepath, 'r', encoding='utf-8') as f:
    code = f.read()

code = code.replace('                    from backend.planning.models import TaskCategory\n', '')
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(code)
print("Removed TaskCategory import")
