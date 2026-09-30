---
name: system
description: Controls PC hardware settings, volume, brightness, battery, WiFi, and system processes.
version: 1.0.0
permissions:
  - system:read
  - system:write
actions:
  - name: get_system_info
    description: Get operating system details, machine architecture, and general status
    required_inputs: []
    output_format: json
  - name: get_volume
    description: Get current audio volume level and mute status
    required_inputs: []
    output_format: json
  - name: set_volume
    description: Set master audio volume level (0-100)
    required_inputs:
      - level
    output_format: text
  - name: mute_volume
    description: Mute master audio output
    required_inputs: []
    output_format: text
  - name: unmute_volume
    description: Unmute master audio output
    required_inputs: []
    output_format: text
  - name: get_brightness
    description: Get display brightness percentage
    required_inputs: []
    output_format: json
  - name: set_brightness
    description: Set display brightness percentage (0-100)
    required_inputs:
      - level
    output_format: text
  - name: get_battery
    description: Get battery percentage and power plugged state
    required_inputs: []
    output_format: json
  - name: get_wifi_status
    description: Check WiFi connection and network adapter state
    required_inputs: []
    output_format: json
  - name: list_processes
    description: List top running processes by resource consumption
    required_inputs: []
    output_format: json
  - name: kill_process
    description: Terminate a specific process by PID
    required_inputs:
      - pid
    output_format: text
---

# System Skill

The **System Skill** provides direct, secure access to host operating system controls and hardware settings on Windows.

## Capabilities
- Adjust master volume (get, set, mute, unmute) via PyCAW.
- Control screen brightness via Screen Brightness Control.
- Query battery state, power sources, and WiFi adapters.
- Inspect and manage active OS processes.
