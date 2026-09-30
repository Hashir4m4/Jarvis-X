---
name: coding
description: Autonomous multi-agent software engineering pipeline (Planner -> Coder -> Reviewer -> Executor).
version: 1.0.0
permissions:
  - code:plan
  - code:write
  - code:execute
actions:
  - name: run_task
    description: Execute a complete multi-step software development or script task
    required_inputs:
      - task
    output_format: json
  - name: generate_code
    description: Generate standalone source code for a specific file or feature
    required_inputs:
      - task
    output_format: text
  - name: review_code
    description: Perform AST and security code review on a file or code block
    required_inputs:
      - code
    output_format: json
  - name: run_code
    description: Safely run a Python or shell script in the execution sandbox
    required_inputs:
      - script
    output_format: json
---

# Coding Skill (Multi-Agent Swarm)

The **Coding Skill** orchestrates an autonomous 4-stage multi-agent pipeline:

1. **Planner Agent**: Decomposes high-level coding tasks into ordered, atomic implementation steps.
2. **Coder Agent**: Synthesizes clean, production-grade source code with language detection.
3. **Reviewer Agent**: Audits code for syntax errors, logic flaws, security vulnerabilities, and quality.
4. **Executor Agent**: Runs and validates code deliverables in a secure workspace sandbox.

## Security & Execution Policies
- Prohibits destructive file operations and unauthorized system modifications without confirmation.
- Emits real-time state telemetry (`PLANNING`, `CODING`, `REVIEWING`, `EXECUTING`) to the HUD.
- Enforces strict execution timeouts and cancellation tokens.
