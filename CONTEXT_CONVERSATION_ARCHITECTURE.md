# Advanced Context and Conversation Management Layer — Architecture

## Overview

The Context Manager adds a persistent state layer to the JARVIS Intelligence Orchestrator. It transforms the system from a stateless command processor into a continuous assistant capable of understanding ongoing tasks, resolving pronoun references, and maintaining session-specific memory.

## Architecture

```
JARVIS ORCHESTRATOR
        │
        ▼  [1. Prepare Context]
   CONTEXT MANAGER
        │
        ├── Conversation Context (History with Summarization)
        ├── Active Task Context (Multi-step tracking)
        ├── Entity/Reference Context (Recent mentions)
        ├── Recent Results Context (Tool outputs, files)
        └── Relevant Memory Retrieval
        │
        ▼
   EXECUTION CONTEXT
        │
        ▼  [2. Orchestrator Executes Task]
        │
        ▼  [3. Update Context]
   CONTEXT MANAGER (Buffers new results and updates tasks)
```

## Core Components

### `ActiveTask`
Tracks multi-step tasks (e.g., `RESEARCH_TASK`, `CODING_TASK`).
- **Fields**: `task_id`, `task_type`, `user_goal`, `current_step`, `status`
- **Statuses**: `ACTIVE`, `WAITING_FOR_INPUT`, `COMPLETED`, `CANCELLED`, `FAILED`
- **Expiration**: Tasks expire after 1 hour of inactivity.

### `EntityReference` & `ResultContext`
Buffers recent entities and execution results.
- When a file is created or a plan generated, the Context Manager buffers a reference to it.
- Allows natural follow-ups: *"make it shorter"* or *"open the second one"*.

## Key Capabilities

### Reference Resolution
The `_resolve_references()` method intercepts inputs containing pronouns (`it`, `that`, `this`, `previous`).
1. Scans `recent_results` and `active_task`.
2. If exactly one candidate exists, it appends the context: `"make it shorter [context: the generated document]"`.
3. If multiple conflicting candidates exist, it returns an `AMBIGUOUS_MARKER`.
4. The Orchestrator detects this marker and immediately prompts the user for clarification without invoking the LLM.

### Context Window Summarization
To prevent unbounded context growth and token exhaustion:
- The `_compress_history()` method limits the active window to a configurable number of turns (`max_history_turns`).
- The system retains the `active_task` state independently of the raw chat history, ensuring goal persistence even if older messages are truncated.

### Privacy Boundaries
The Context Manager integrates with the existing `PrivacyBoundary`:
- Raw inputs are scrubbed of secrets before being stored in RAM history (`[REDACTED_SECRET]`).
- The Hybrid Model Router ensures that `CLOUD_ALLOWED` policies apply to the generated context window, never leaking sensitive offline memory to external APIs.

### Multi-Source Management
- Sessions are keyed by `session_id`.
- Voice, Text, and HUD interactions sharing the same `session_id` share the same short-term context, enabling cross-channel continuity (e.g., speak a command, then type a correction).

## Known Limitations

1. **Heuristic Reference Resolution**: The current resolution logic is fast and rule-based. Highly complex references (e.g., "Combine the first paragraph of the second doc with the last paragraph of the third") may require full LLM analysis in the future.
2. **Hard Truncation**: History is currently truncated rather than passed through an LLM for abstract summarization, to save local inference costs.

## Files
- `backend/memory/context_manager.py`: Core implementation.
- `backend/router/context.py`: Updated `ExecutionContext` with `resolved_input` and `active_task_id`.
- `backend/orchestrator/orchestrator.py`: Injects context pre-execution and updates post-execution.
- `backend/core/models.py`: Added `TaskStatus` enum.
- `tests/test_context_manager.py`: 9 comprehensive test scenarios verifying resolution and limits.
