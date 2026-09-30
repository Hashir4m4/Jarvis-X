---
name: desktop
description: Controls desktop operations including application launch, file management, window control, system info, and controlled GUI interactions.
version: 1.0.0
category: system
permissions:
  - execute
  - destructive
supported_modes:
  - OFFLINE
  - LOCAL
  - HYBRID
dependencies: []
actions:
  - name: open_application
    description: Opens an application by friendly alias, process name, or system path.
    required_inputs:
      - app_name
    output_format: json

  - name: close_application
    description: Closes an application safely by process name.
    required_inputs:
      - process_name
    output_format: json

  - name: open_file
    description: Opens a file using the operating system's default program.
    required_inputs:
      - file_path
    output_format: json

  - name: open_folder
    description: Opens a directory in File Explorer.
    required_inputs:
      - folder_path
    output_format: json

  - name: create_folder
    description: Creates a new folder at the specified path.
    required_inputs:
      - folder_path
    output_format: json

  - name: rename_file
    description: Renames an existing file or directory.
    required_inputs:
      - src
      - dest
    output_format: json

  - name: move_file
    description: Moves a file or directory to a new location.
    required_inputs:
      - src
      - dest
    output_format: json

  - name: copy_file
    description: Copies a file or directory.
    required_inputs:
      - src
      - dest
    output_format: json

  - name: delete_file
    description: Deletes a file after user confirmation.
    required_inputs:
      - file_path
    output_format: json

  - name: list_directory
    description: Lists files and subfolders in a directory.
    required_inputs:
      - folder_path
    output_format: json

  - name: organize_directory
    description: Categorizes and organizes files in a directory.
    required_inputs:
      - folder_path
    output_format: json

  - name: get_system_info
    description: Returns system hardware metrics (CPU, RAM, Disk, OS).
    required_inputs: []
    output_format: json

  - name: window_action
    description: Controls windows (minimize, maximize, restore, close).
    required_inputs:
      - window_action
    output_format: json

  - name: emergency_stop
    description: Immediately halts all active and queued desktop automation actions.
    required_inputs: []
    output_format: json
---

# Desktop Automation & Computer Control Skill

Provides safe, controlled, and deterministic computer control for JARVIS OS.
Enforces permission checks, step-by-step verification, and voice-accessible emergency stop.
