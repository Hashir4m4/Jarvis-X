# Hybrid Intelligent Model Router — Architecture

## Overview

The Hybrid Intelligent Model Router is a focused, deterministic component that selects the **smallest and most appropriate AI intelligence** for each JARVIS request. It sits between the Orchestrator's task classification step and execution step, replacing the previous hard-coded `"local:ollama"` model references with a structured, privacy-aware, fallback-capable selection system.

**Key Principle**: *"Use the smallest and most appropriate capability required to solve the task."*

All routing decisions are rule-based. No LLM is invoked to decide which model to use.

## Architecture

```
JARVIS ORCHESTRATOR
        │
        ▼
    TASK CLASSIFICATION  (DecisionEngine)
        │
        ▼
    MODEL ROUTER  ◄── CapabilityDetector, PrivacyBoundary,
        │              LocalModelConfig, CloudModelConfig
        ├───────────────┐
        ▼               ▼
   LOCAL CAPABLE?   CLOUD CAPABLE?
        │               │
        └───────┬───────┘
                ▼
       MODEL SELECTION  (scored candidates + fallback chain)
                │
                ▼
           EXECUTION  (Orchestrator)
```

## Component: `backend/llm/model_router.py`

### `ModelRouter.select(request: ModelSelectionRequest) -> ModelSelectionResult`

Core routing method. Takes a structured request and returns a structured result.

### Decision Flow

1. **Role Mapping**: Maps `TaskCategory` → `ModelRole` (`none`, `fast`, `general`, `reasoning`, `coding`, `vision`)
2. **NO_LLM Gate**: Direct system commands and tool-only skills skip AI entirely
3. **Privacy Gate**: Sensitive content or `LOCAL_ONLY` policy excludes cloud candidates
4. **Candidate Building**: Generates scored local + cloud candidates based on availability
5. **User Preference**: Re-orders candidates based on explicit user override
6. **Selection**: Returns the highest-scoring candidate with fallback chain

## Decision Factors

| Factor | Description | Impact |
|---|---|---|
| **Task Category** | What type of request (conversation, coding, research, etc.) | Determines required model role |
| **Complexity** | LOW / MEDIUM / HIGH estimated from keywords + word count | HIGH upgrades role to reasoning |
| **Privacy Level** | LOCAL_ONLY / PREFER_LOCAL / CLOUD_ALLOWED | Controls cloud candidate eligibility |
| **Internet** | Connected or disconnected | Blocks cloud candidates when offline |
| **Local LLM** | Ollama running and model available | Enables local candidates |
| **Cloud Providers** | Configured, authenticated, and healthy | Enables cloud candidates |
| **Latency** | Voice requests prefer low latency | Boosts local scoring |
| **User Preference** | AUTO / LOCAL / CLOUD / HYBRID | Overrides candidate ordering |
| **Cost** | Cloud candidates scored slightly lower | Prefers local when equivalent |

## Routing Modes

### LOCAL Mode
All AI processing stays on the local machine. Ollama provides the intelligence layer.

### CLOUD Mode
Cloud AI models are selected when they provide superior capability and privacy permits.

### HYBRID Mode
Both local and cloud are available. The router selects optimally based on task requirements.

### DIRECT Mode
No AI model needed. System tools, skills, and automation handle the request directly.

## Privacy Policies

### `LOCAL_ONLY`
- All AI processing stays local
- Cloud providers are **never** included in candidates
- Fallback chain never crosses to cloud
- Applied automatically when sensitive content is detected (API keys, passwords, tokens)

### `PREFER_LOCAL`  (Default)
- Local AI is preferred when capable
- Cloud is available as fallback but scored lower
- Memory requests default to this policy

### `CLOUD_ALLOWED`
- Cloud models may be selected when beneficial
- Research tasks and high-complexity reasoning benefit from cloud models
- Privacy boundary still redacts secrets before any cloud transmission

## Offline Behaviour

When internet is unavailable:
- Cloud providers are excluded from all candidate lists
- Local models handle all AI-capable requests
- NO_LLM paths (system commands, tools) remain fully functional
- If local AI is also unavailable, the router returns `NO_CAPABILITY` status
- The system does NOT fabricate information it cannot access

## Online Behaviour

When internet is available:
- Cloud AI is **optional**, not automatic
- Simple commands still route to direct tools (no unnecessary API calls)
- Local memory queries stay local
- Research and complex reasoning may route to cloud if policy allows
- User can force `LOCAL` mode even when online

## Fallback Strategy

```
PREFERRED     →  Cloud Reasoning Model
UNAVAILABLE   →  Local Reasoning Model
UNAVAILABLE   →  Local General Model
UNAVAILABLE   →  Return NO_CAPABILITY error
```

### Fallback Rules
- **Privacy is preserved**: `LOCAL_ONLY` never falls back to cloud
- **Permissions are respected**: Destructive operations require confirmation regardless of model
- **Capabilities are matched**: Vision requests don't fall back to text-only models
- **Status is reported**: `FALLBACK` routing status is set when using non-primary candidate

## User Overrides

### Configuration
```env
MODEL_ROUTING_PREFERENCE=AUTO     # AUTO | LOCAL | CLOUD | HYBRID
MODEL_PRIVACY_POLICY=PREFER_LOCAL # LOCAL_ONLY | PREFER_LOCAL | CLOUD_ALLOWED
```

### Runtime Override Support
The router accepts per-request `user_preference` overrides. Future voice commands like:
- *"Use local AI"* → `UserRoutingPreference.LOCAL`
- *"Use cloud AI for this"* → `UserRoutingPreference.CLOUD`
- *"Stay offline"* → `UserRoutingPreference.LOCAL`
- *"Use the best available option"* → `UserRoutingPreference.AUTO`

## HUD Integration

The router exposes safe telemetry via `to_hud_payload()`:

```json
{
  "mode": "LOCAL",
  "active_provider": "local",
  "active_model": "qwen2.5-coder:7b",
  "routing_status": "AVAILABLE",
  "model_role": "coding",
  "reason": "Local model selected for 'coding' role."
}
```

**Never exposed**: API keys, internal scoring, hidden chain-of-thought.

## Performance

- **No LLM invocation** for routing decisions
- **Deterministic rules** based on enum matching and keyword heuristics
- **Complexity classification**: ~0.01ms (word count + keyword scan)
- **Privacy detection**: ~0.05ms (regex pattern matching)
- **Full routing**: ~0.1ms total
- **Provider status caching**: 30s TTL via CloudProviderManager, 15s TTL via CapabilityDetector

## Task → Model Role Mapping

| Task Category | Model Role | Rationale |
|---|---|---|
| `COMMAND` | None | Direct tool execution |
| `COMPUTER_ACTION` | None | System automation |
| `SCHEDULED_TASK` | Fast | Minimal processing |
| `CONVERSATION` | General | Standard dialogue |
| `QUESTION` | General | Knowledge Q&A |
| `MEMORY_REQUEST` | Fast | Retrieval-augmented |
| `CODING_TASK` | Coding | Specialized coding models |
| `PLANNING_TASK` | Reasoning | Complex planning |
| `RESEARCH_TASK` | Reasoning | Deep analysis |
| `VISION_TASK` | Vision | Multimodal models |
| `MULTI_STEP_TASK` | Reasoning | Multi-step orchestration |

## Extension Points

1. **New Providers**: Register via `CloudProviderManager.register_provider()` — automatically included in routing candidates
2. **New Task Categories**: Add to `TASK_ROLE_MAP` in `model_router.py`
3. **Custom Scoring**: Override `_score_candidate()` for domain-specific preferences
4. **New Privacy Levels**: Extend `PrivacyPolicy` enum and `_resolve_effective_privacy()` logic
5. **Cost Tracking**: Extend scoring with token cost estimates per provider

## Files

| File | Purpose |
|---|---|
| `backend/llm/model_router.py` | Core router component |
| `backend/orchestrator/decision_engine.py` | Task classification (modified) |
| `backend/orchestrator/orchestrator.py` | Orchestrator integration (modified) |
| `backend/router/context.py` | Execution context (modified) |
| `.env.example` | Configuration template (modified) |
| `tests/test_hybrid_model_router.py` | 31 test cases |
| `HYBRID_MODEL_ROUTER.md` | This document |
