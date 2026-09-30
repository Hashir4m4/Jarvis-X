---
name: metrics
description: Queries system performance metrics, CPU load, memory utilization, swap, temperature, and hardware telemetry.
version: 1.0.0
permissions:
  - telemetry:read
actions:
  - name: get_telemetry
    description: Fetch real-time CPU, RAM, temperature, swap, and uptime snapshot
    required_inputs: []
    output_format: json
  - name: get_cpu_load
    description: Query current CPU utilization percentage
    required_inputs: []
    output_format: json
  - name: get_memory_stats
    description: Query total, used, and free RAM and swap space
    required_inputs: []
    output_format: json
  - name: get_summary
    description: Generate an analytical performance summary for display on the HUD
    required_inputs: []
    output_format: text
---

# Metrics Skill

The **Metrics Skill** gathers performance telemetry, resource bottlenecks, and hardware statistics to power real-time analytics and HUD gauges.

## Capabilities
- Samples CPU utilization across cores.
- Tracks RAM consumption and swap space.
- Calculates estimated core temperature and GPU activity.
- Generates telemetry packets for WebSocket broadcasts.
