import os
import re
import json

findings = {
    "missing_wiring": [],
    "mock_dependencies": [],
    "circular_dependencies": [],
    "error_handling_gaps": [],
    "race_conditions": [],
    "persistence_gaps": []
}

def check_file(path):
    if not os.path.exists(path):
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

# 1. Check Core Wiring in core.py
core_content = check_file("backend/core/core.py")
expected = ["orchestrator", "memory", "event_bus", "scheduler", "proactive_engine", "task_planner", "execution_engine", "agent_manager"]
for e in expected:
    if e not in core_content.lower():
        findings["missing_wiring"].append(f"core.py missing {e}")

# 2. Check Orchestrator
orch_content = check_file("backend/orchestrator/orchestrator.py")
if "self.planner" not in orch_content:
    findings["missing_wiring"].append("Orchestrator does not use TaskPlanner directly")
if "self.execution_engine" not in orch_content:
    findings["missing_wiring"].append("Orchestrator does not use ExecutionEngine directly")
if "Exception" in orch_content and "except Exception:" in orch_content and "logger.error" not in orch_content:
    findings["error_handling_gaps"].append("Orchestrator swallows exceptions")

# 3. Check Memory API
mem_content = check_file("backend/memory/memory_api.py")
if "await self.db.commit()" not in mem_content and "commit()" in mem_content:
    findings["async_sync_mismatches"] = ["memory_api.py uses sync commit in async context"]

# 4. Check Proactive Engine
proactive_content = check_file("backend/proactive/engine.py")
if "await self.memory.add_memory" not in proactive_content:
    findings["persistence_gaps"].append("ProactiveEngine memory persistence is not awaited properly or missing")

# 5. Check Test Mocks in Production
for root, _, files in os.walk("backend"):
    for f in files:
        if f.endswith(".py"):
            path = os.path.join(root, f)
            c = check_file(path)
            if "MagicMock" in c or "AsyncMock" in c:
                findings["mock_dependencies"].append(path)

print(json.dumps(findings, indent=2))
