---
name: plan
description: Decomposes complex coding and automation objectives into ordered, actionable multi-step execution plans.
version: 1.0.0
permissions:
  - planning:execute
actions:
  - name: create_plan
    description: Decompose a high-level task into implementation steps (CREATE, MODIFY, DELETE, TEST, RUN)
    required_inputs:
      - task
    output_format: json
  - name: explain_plan
    description: Provide a structured technical breakdown of an existing or proposed implementation plan
    required_inputs:
      - task
    output_format: text
---

# Plan Skill

The **Plan Skill** serves as the cognitive architect for multi-agent coding and multi-step PC automations, breaking down tasks into atomic steps with language detection and dependency mapping.
