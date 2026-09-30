---
name: trends
description: Analyzes historical metrics, command patterns, query frequencies, and system performance trends over time.
version: 1.0.0
permissions:
  - analytics:read
actions:
  - name: get_query_trends
    description: Analyze most frequent user commands and topics over the past sessions
    required_inputs: []
    output_format: json
  - name: get_system_trends
    description: Summarize historical system performance and average load
    required_inputs: []
    output_format: json
---

# Trends Skill

The **Trends Skill** analyzes historical usage patterns, command logs, and telemetry to provide predictive insights and resource optimization recommendations.
