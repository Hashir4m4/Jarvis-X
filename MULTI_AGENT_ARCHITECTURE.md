# JARVIS OS: Controlled Multi-Agent Intelligence System Architecture

## 1. Architectural Philosophy & Hierarchy

In JARVIS OS, **JARVIS is the unified intelligence**. Agents are specialized internal reasoning and execution capabilities subordinate to the Central Intelligence Orchestrator. 

Agents **never** operate as independent chatbots or bypass security boundaries. The system strictly maintains the following hierarchical lifecycle:

```
                    USER
                      │
                      ▼
             JARVIS ORCHESTRATOR
                      │
                      ▼
               TASK ANALYSIS
                      │
              ┌───────┼────────┐
              ▼       ▼        ▼
         RESEARCH   CODING   PLANNING   (Specialized Agents)
          AGENT     AGENT     AGENT
              │       │        │
              └───────┼────────┘
                      ▼
               AGENT RESULTS
                      │
                      ▼
             JARVIS SYNTHESIS
                      │
                      ▼
                    USER
```

### Core Invariants & Boundaries
1. **Unified Persona**: The user always converses with JARVIS. Agents produce structured internal outputs (`AgentResult`) that JARVIS synthesizes into conversational responses.
2. **Strict Least Privilege**: Each agent only receives context pertinent to its immediate task. Secrets, credentials, raw system prompts, and unrelated memory stores are never exposed to agents.
3. **Controlled Tool Permissibility**: Agents cannot invoke arbitrary desktop or shell actions. Destructive operations (`delete_file`, `shell_execute`, arbitrary clicks) are prohibited.
4. **Finite Delegation**: Maximum delegation depth is bounded to `2` (`max_depth=2`) and active agents per task are capped at `4` (`max_agents_per_task=4`), preventing runaway recursion or infinite loops.
5. **Robust Partial Failure**: If an individual agent fails or encounters an unrecoverable exception, JARVIS gracefully handles the partial results and reports limited capabilities rather than crashing.

---

## 2. Agent Registry & Metadata Specification

The `AgentRegistry` (`backend/agents/agent_registry.py`) governs agent discovery, capability indexing, uniqueness validation, and lifecycle controls.

### Metadata Schema
Every agent registers with structured metadata:
- `agent_id` (str): Unique canonical identifier (e.g., `research_agent`, `coding_agent`).
- `name` (str): Human-readable agent display name.
- `description` (str): Functional overview of what the agent handles.
- `specialization` (str): Core competency.
- `capabilities` (List[AgentCapability]): Granular capability tags (e.g., `WEB_RESEARCH`, `CODE_ANALYSIS`).
- `allowed_tools` (List[str]): Whitelist of tool identifiers the agent is authorized to invoke.
- `allowed_skills` (List[str]): Whitelist of skills the agent may trigger.
- `model_role` (str): Role hint for the Hybrid Model Router (`reasoning`, `coding`, `general`).
- `offline_support` (OfflineSupport): Operational status when disconnected (`FULL`, `LIMITED`, `NONE`).
- `status` (AgentStatus): Real-time lifecycle state (`IDLE`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED`, `UNAVAILABLE`).

---

## 3. Specialized Agents

| Agent ID | Specialization | Key Capabilities | Allowed Tools | Offline Support |
| :--- | :--- | :--- | :--- | :--- |
| **`research_agent`** | Web research, source extraction & evaluation | `WEB_RESEARCH`, `SOURCE_ANALYSIS` | `browser.search`, `browser.extract`, `document.read`, `web.search` | `LIMITED` (Cached local docs available) |
| **`coding_agent`** | Code analysis, debugging & syntax diagnosis | `CODE_ANALYSIS`, `CODE_GENERATION`, `DEBUGGING` | `code.read`, `code.analyze`, `code.test`, `file.read` | `FULL` (Local models supported) |
| **`planning_agent`** | Task decomposition & phased roadmaps | `TASK_DECOMPOSITION`, `PROJECT_PLANNING` | `plan.decompose`, `vault.read` | `FULL` (100% offline reasoning) |
| **`analysis_agent`** | Structured comparison & trade-off matrices | `TECHNICAL_ANALYSIS`, `COMPARISON` | `data.analyze`, `metrics.compare` | `FULL` (Deterministic evaluation) |
| **`system_agent`** | Safe read-only diagnostics & telemetry | `SYSTEM_DIAGNOSTICS` | `system.info`, `system.status`, `metrics.read` | `FULL` (Local OS probes) |
| **`productivity_agent`** | Schedule planning, briefs & day wrap-up | `PRODUCTIVITY_PLANNING` | `productivity.schedule`, `inbox.read` | `FULL` (Local SQLite & Vault) |

---

## 4. Multi-Agent Coordinator & Execution Governance

The `MultiAgentCoordinator` (`backend/agents/multi_agent_coordinator.py`) manages the lifecycle of multi-agent tasks:

1. **Context Bounding**: Packages user requirements into an `AgentTaskContext` containing only necessary metadata, timeout limits, and online/offline flags.
2. **Depth & Budget Enforcement**:
   - `delegation_depth > max_depth (2)`: Rejects execution with `recursion_limit_exceeded`.
   - `len(agents) > max_agents_per_task (4)`: Truncates pipeline to top 4 candidate agents.
3. **Asynchronous Execution & Timeouts**: Runs agent executions concurrently or sequentially with per-step timeout ceilings using `asyncio.wait_for`.
4. **Global Cancellation**: Propagates cancellation signals from `JarvisCore.cancel()` or Orchestrator directly to all active agents.
5. **Synthesis Engine**: Aggregates structured outputs from all agents and creates an integrated, transparent summary for JARVIS to present to the user.

---

## 5. Hybrid Model Router Integration

Agents dynamically request model selection through the Hybrid Intelligent Model Router based on:
- Privacy policies (`LOCAL_ONLY`, `PREFER_LOCAL`, `CLOUD_ALLOWED`).
- Connectivity status (`Offline` vs `Online`).
- Agent specialization role:
  - `coding_agent` maps to local coding models (`qwen2.5-coder:7b`) or approved cloud coding models.
  - `research_agent` / `analysis_agent` leverage reasoning models.
  - `planning_agent` runs on low-latency local LLMs.

---

## 6. How to Add a New Specialized Agent

To add a new agent:
1. Inherit from `BaseAgent` (`backend/agents/base_agent.py`).
2. Define an `AgentMetadata` object specifying capabilities, strictly allowed tools, and offline support.
3. Implement `can_handle(task_context: AgentTaskContext) -> bool`.
4. Implement `execute(task_context: AgentTaskContext) -> AgentResult`.
5. Register the agent in `JarvisCore._init_multi_agent_system()`:
   ```python
   self.specialized_registry.register(MyCustomAgent())
   ```

---

## 7. Testing & Verification Guide

Run the multi-agent test suite:
```powershell
python -m unittest tests/test_multi_agent_system.py
```

All 17 verification points pass without external dependencies or live network connections:
- Agent registration & duplicate rejection
- Discovery by capability
- Simple request bypass (no delegation for basic commands)
- Specialized agent selection (Research, Coding, Planning)
- Multi-agent collaborative workflows
- Unavailable agent handling
- Tool boundary enforcement
- Offline and cloud routing
- Timeout and cancellation propagation
- Delegation depth safety limit (depth <= 2)
- Structured synthesis
