---
name: plan
description: Synthesizes and manages long-horizon plans, computes critical paths, adapts plans, and organizes daily execution.
version: 2.0.0
permissions:
  - planning:execute
  - plan
  - read_file
  - write_file
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
  - name: plan_today
    description: Formulate Top 3 daily priorities and persist them to Obsidian Daily Vault note
    output_format: text
  - name: synthesize_plan
    description: Synthesize a long-horizon strategic plan from an approved goal
    output_format: json
  - name: view_plan
    description: View details, milestones, and critical path of an existing long-horizon plan
    required_inputs:
      - plan_id
    output_format: text
  - name: list_plans
    description: List all strategic plans with status and critical path duration
    output_format: text
  - name: submit_plan_for_approval
    description: Submit a draft strategic plan for human review and approval
    required_inputs:
      - plan_id
    output_format: text
  - name: approve_plan
    description: Formally approve a proposed strategic plan
    required_inputs:
      - plan_id
    output_format: text
  - name: reject_plan
    description: Reject a proposed strategic plan
    required_inputs:
      - plan_id
    output_format: text
  - name: activate_plan
    description: Activate an approved strategic plan
    required_inputs:
      - plan_id
    output_format: text
  - name: get_critical_path
    description: Calculate and display the critical path milestones and duration for a plan
    required_inputs:
      - plan_id
    output_format: text
  - name: assess_adaptation
    description: Evaluate environmental drift or milestone delays against plan viability
    required_inputs:
      - plan_id
    output_format: json
  - name: propose_revision
    description: Propose an updated plan revision without modifying active baseline
    required_inputs:
      - plan_id
    output_format: json
  - name: approve_revision
    description: Atomically replace plan baseline with approved pending revision
    required_inputs:
      - plan_id
    output_format: text
  - name: reject_revision
    description: Discard pending revision proposal and retain baseline intact
    required_inputs:
      - plan_id
    output_format: text
---

# Plan Skill

The **Plan Skill** serves as the cognitive architect for strategic long-horizon planning, critical-path analysis, adaptive replanning, multi-agent coding breakdowns, and daily agenda structuring in JARVIS X OS.
