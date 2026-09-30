import os
import ast

def check_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    issues = []
    
    # Check for hardcoded mock implementations
    if "MagicMock" in content or "AsyncMock" in content:
        issues.append("Contains test mock imports (MagicMock/AsyncMock)")
        
    if "return True # TODO" in content or "return None # TODO" in content or "pass # TODO" in content:
        issues.append("Contains stubbed TODO returns")
        
    return issues

def analyze_backend():
    print("=== BACKEND ANALYSIS ===")
    for root, _, files in os.walk("backend"):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                issues = check_file(path)
                if issues:
                    print(f"[{path}]: {', '.join(issues)}")

def check_wiring():
    print("\n=== CORE WIRING CHECK ===")
    core_files = [
        "start_jarvis.py",
        "backend/core/jarvis.py",
        "backend/core/orchestrator.py",
        "backend/api/app.py",
    ]
    
    expected_components = [
        "ProactiveEngine",
        "TaskPlanner",
        "ExecutionEngine",
        "LongTermMemory",
        "DesktopController",
        "EventBus"
    ]
    
    for path in core_files:
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            found = []
            missing = []
            for comp in expected_components:
                if comp in content:
                    found.append(comp)
                else:
                    missing.append(comp)
            print(f"[{path}]")
            print(f"  Found: {', '.join(found) if found else 'None'}")
            print(f"  Missing: {', '.join(missing) if missing else 'None'}")

if __name__ == '__main__':
    analyze_backend()
    check_wiring()
