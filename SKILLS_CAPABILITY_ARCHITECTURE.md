# Advanced Skills and Capability Architecture

## Overview

JARVIS OS implements a strict separation of concerns between orchestration, intelligence routing, and capability execution. The **Advanced Skills and Capability System** provides a robust, standardized way to define, discover, validate, and safely execute domain-specific functionality.

## Core Principles

1. **Focused Capabilities**: Skills are tools. They do not plan or coordinate multi-step workflows. That is the job of the `JarvisOrchestrator`.
2. **Safe Execution**: A failed skill must never crash the assistant. All executions are wrapped, sandboxed, and return a standardized `SkillResult`.
3. **Capability Discovery**: JARVIS knows what it can do before it tries to do it. Dependencies (like internet, local AI, or camera) are checked against the system's `CapabilityState`.
4. **Input Validation**: Skills enforce strict schemas before execution, blocking malformed requests.

## Architecture

```
USER REQUEST
      │
JARVIS ORCHESTRATOR
      │
[ CapabilityDetector -> Generates CapabilityState ]
      │
SKILL REGISTRY + CAPABILITY REGISTRY
      ├── Checks Dependencies (Internet, LLM, Cloud)
      ├── Checks Modes (ONLINE, OFFLINE, HYBRID)
      ├── Checks Permissions (SecurityProxy)
      └── Validates Input Schema
      │
      ▼
SKILL EXECUTION
      │
      ▼
SKILL RESULT (Success, Artifacts, Execution Time)
      │
      ▼
ORCHESTRATOR -> MEMORY -> HUD
```

## Capability States

A skill is always in one of five explicit states managed by the `CapabilityRegistry`:

- **REGISTERED**: The skill exists and metadata is loaded, but availability has not been evaluated against the current system state.
- **AVAILABLE**: All declared dependencies (e.g., internet connection, cloud API key) are met.
- **UNAVAILABLE**: A required dependency is missing. The Orchestrator will avoid routing here.
- **DISABLED**: Administratively turned off.
- **FAILED**: The skill experienced a critical runtime failure and is temporarily quarantined.

## Creating a New Skill

Creating a new skill requires zero modification to the JARVIS core. 

1. Create a directory for your skill (e.g., `plugins/my_skill/`).
2. Add a `SKILL.md` file containing YAML frontmatter:
```yaml
---
name: my_skill
description: "Does something awesome."
version: 1.0.0
category: productivity
supported_modes:
  - CLOUD
  - HYBRID
dependencies:
  - internet
permissions:
  - user_read
actions:
  - name: do_thing
    description: "Executes the thing."
    required_inputs:
      - query
    input_schema:
      type: object
      properties:
        query:
          type: string
---
Documentation goes here.
```
3. Implement the `BaseSkill` interface in Python.
4. Drop it into the `backend/skills/` directory (or register dynamically via a Plugin). The `SkillRegistry` will discover it automatically on startup.

## Testing Strategy

The Capability System is rigorously tested via isolated unit tests and full system regression tests. Mocks are used to simulate missing dependencies (like offline testing) without requiring network interruptions.
