---
name: brief
description: Aggregates morning intelligence brief combining inbox, calendar, memory, project activity, and configured sources.
version: 1.0.0
permissions:
  - memory:read
  - inbox:read
  - system:read
actions:
  - name: get_brief
    description: Generate complete morning intelligence brief
    required_inputs: []
    output_format: text
---

# Morning Brief Skill

Combines available local and external intelligence into a cohesive morning brief:

- **Inbox & Notifications**: Active alerts and unread interaction counts.
- **Calendar**: Connected calendar schedules (reports unavailable if not configured).
- **JARVIS Memory**: Recent user context and stored priorities.
- **Project Activity**: Local repository git status and recent deliverables.
- **Data Feeds**: Configured news and market data streams.
