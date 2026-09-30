# JARVIS OS: Autonomous Task Planning and Controlled Execution Engine

## 1. Architectural Philosophy & Hierarchy

In JARVIS OS, **autonomous planning is strictly separated from execution**. The Task Planner acts as a reasoning system that designs structured proposals, while the Execution Engine acts as a gatekeeper that verifies dependencies, enforces safety permissions, and dispatches tasks to established system capabilities (Skills, Tools, Agents).

The system strictly adheres to the following controlled execution architecture:

```
                      USER GOAL
                          │
                          ▼
                 JARVIS ORCHESTRATOR
                          │
                          ▼
                    TASK ANALYSIS
              (Determine if plan required)
                          │
                          ▼
                     TASK PLANNER
            (Decomposes into TaskPlan & Steps)
                          │
                          ▼
              DEPENDENCY & RISK ANALYSIS
            (Cycle detection & risk grading)
                          │
                          ▼
                PERMISSION CHECKPOINTS
       (Safe steps auto-execute; High risk pauses)
                          │
                          ▼
                   EXECUTION ENGINE
           (Step dispatch to Skills/Tools/Agents)
                          │
                          ▼
                  RESULT VERIFICATION
            (File exists, data non-empty, etc.)
                          │
                          ▼
                PROGRESS & SYNTHESIS
                          │
                          ▼
                         USER
```

---

## 2. Core Invariants & Safety Principles

1. **Separation of Concerns**: The Planner never executes commands directly. It outputs structured `TaskPlan` models composed of typed `TaskStep` objects.
2. **Deterministic DAG Execution**: Steps must strictly satisfy all dependencies before executing. Circular dependencies are prohibited and detected ahead of execution.
3. **Permission Checkpoints**:
   - `LOW` risk steps (reading data, AST analysis, telemetry queries) may proceed automatically.
   - `HIGH` risk steps (deleting files, killing processes, system modifications) trigger `AWAITING_APPROVAL` checkpoints and mandate authorization via `SecurityProxy`.
4. **Resilient Recovery**: Steps support configurable `RetryPolicy` (`NO_RETRY`, `LIMITED_RETRY`, `ALTERNATIVE_CAPABILITY`). Destructive actions are never automatically retried.
5. **No Hallucinated Capabilities**: When offline, tasks requiring live network access are rejected during validation or gracefully degraded to cached knowledge.

---

## 3. Plan & Step Data Models (`backend/planning/models.py`)

### TaskPlan States (`PlanStatus`)
- `CREATED`: Initialized plan object.
- `PLANNING`: In-flight decomposition by planner.
- `AWAITING_APPROVAL`: Paused waiting for user elevation / confirmation.
- `READY`: Validated and prepared for execution.
- `RUNNING`: Actively processing steps.
- `PAUSED`: Halted by user ("Pause that"); safe to resume.
- `COMPLETED`: All steps executed and verified.
- `FAILED`: Non-recoverable failure occurred.
- `CANCELLED`: Aborted via user command ("Stop") or emergency stop.
- `PARTIALLY_COMPLETED`: One or more steps completed, but subsequent steps failed or deadlocked.

### TaskStep States (`StepStatus`)
- `PENDING`: Awaiting satisfaction of prerequisite dependencies.
- `RUNNING`: In progress.
- `AWAITING_APPROVAL`: Blocked at a permission checkpoint.
- `COMPLETED`: Successfully executed and verified.
- `FAILED`: Execution or post-verification failed.
- `SKIPPED`: Bypassed due to predecessor failure.
- `CANCELLED`: Terminated due to global cancellation.

### Risk Levels (`RiskLevel`)
- `LOW`: Read-only queries, research extraction, AST analysis, telemetry monitoring.
- `MEDIUM`: File generation, directory creation, non-destructive exports.
- `HIGH`: File deletion, process termination, system configuration changes.

---

## 4. Dependency Graph & Validation (`backend/planning/analyzer.py`)

The `PlanAnalyzer` inspects all proposed plans prior to execution:
1. **Cycle Detection**: Employs Depth-First Search cycle detection to prevent recursive deadlocks.
2. **Topological Ordering**: Computes valid sequential/parallel execution order using Kahn's algorithm.
3. **Capability Resolution**:
   - Validates `required_skill` in `SkillRegistry`.
   - Validates `required_tool` in `ToolRegistry`.
   - Validates `required_agent` in `AgentRegistry`.
4. **Offline Awareness**: Rejects online dependencies if internet connectivity is missing unless an offline fallback is declared.

---

## 5. Controlled Execution Engine (`backend/planning/execution_engine.py`)

The `ExecutionEngine` governs step execution:
1. **Concurrency Support**: Independent safe steps (`RiskLevel.LOW`) may execute concurrently using `asyncio.gather`.
2. **Capability Dispatch**:
   - Routes agent steps to `MultiAgentCoordinator`.
   - Routes tool steps to `ToolRegistry`.
   - Routes skill steps to `SkillRegistry.execute_intent`.
3. **Post-Execution Result Verification**:
   - File generation: Confirms file existence on disk.
   - Information gathering: Verifies non-empty structured output.
4. **Pause, Resume & Cancellation**:
   - `pause()`: Sets execution hold; pending steps do not launch.
   - `resume()`: Re-evaluates ready queue and resumes execution.
   - `cancel()`: Immediately sets `CANCELLED` and propagates cancellation tokens to active agents.
   - `emergency_stop()`: Halts all automation across desktop, agents, and engine pipelines.

---

## 6. Verification & Test Suite

The test suite in [`tests/test_task_planning_engine.py`](file:///c:/Data/Projects/Jarvis%20X/tests/test_task_planning_engine.py) covers all 24 required test scenarios:
1. Simple request bypasses planner.
2. Complex request generates plan.
3. Plan validation.
4. Circular dependency detection.
5. Missing skill error.
6. Missing agent error.
7. Missing tool error.
8. Low-risk automatic execution.
9. High-risk approval required.
10. Step dependency ordering.
11. Independent step execution where supported.
12. Step success verification.
13. Transient failure retry.
14. Retry limit reached.
15. Alternative capability fallback.
16. Plan pause.
17. Plan resume.
18. Task cancellation.
19. Emergency stop.
20. Partial completion.
21. Plan modification.
22. New risky step requires approval.
23. Offline capability unavailable.
24. Maximum execution limit.

---

## 7. How to Add a New Task Capability

1. Implement the tool in `ToolRegistry` (`backend/router/tool_registry.py`) or register a skill in `SkillRegistry` (`backend/skills/registry.py`).
2. Add capability metadata to `AgentMetadata` if utilizing specialized agents.
3. In `TaskPlanner._decompose_goal_into_steps`, map high-level goal patterns to the new `required_capability`, `required_tool`, or `required_skill`.
4. Define verification rules in `ExecutionEngine._verify_result` if the output produces tangible artifacts.
