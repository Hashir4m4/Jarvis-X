---
name: close_day
description: End-of-day closing workflow summarizing completed tasks, reflections, updating the daily note, and defining tomorrow's priorities.
version: 1.0.0
permissions:
  - memory:read
  - memory:write
actions:
  - name: close_the_day
    description: Generate daily recap, capture reflections, update Obsidian daily note, and draft tomorrow's priorities
    required_inputs: []
    output_format: text
---

# Close The Day Skill

Executes the evening shutdown and reflection routine:

- **Completed Work**: Synthesizes tasks completed today across OS subsystems.
- **Reflection**: Records key outcomes, challenges, and system metrics.
- **Daily Note**: Updates the Obsidian daily note in `vault/daily/`.
- **Tomorrow's Priorities**: Establishes 3 core focus areas for the next morning.
