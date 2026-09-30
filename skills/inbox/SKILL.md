---
name: inbox
description: Manages incoming messages, queued agent notifications, alerts, and unread task items.
version: 1.0.0
permissions:
  - inbox:read
  - inbox:write
actions:
  - name: list_messages
    description: List recent messages and notification items from the dialogue store
    required_inputs: []
    output_format: json
  - name: count_unread
    description: Count pending alerts and unread system notifications
    required_inputs: []
    output_format: json
  - name: clear_inbox
    description: Clear transient notifications and acknowledge alerts
    required_inputs: []
    output_format: text
---

# Inbox Skill

The **Inbox Skill** aggregates system alerts, background task completions, agent status updates, and user communications into an actionable queue.
