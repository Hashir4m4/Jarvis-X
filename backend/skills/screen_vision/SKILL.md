---
name: screen_vision
description: Understands and analyzes active windows or full screen on demand with privacy filtering, OCR, error diagnostics, and safe desktop action proposals.
version: 1.0.0
category: system
permissions:
  - execute
supported_modes:
  - LOCAL
  - HYBRID
  - CLOUD
  - OFFLINE
dependencies: []
actions:
  - name: describe_screen
    description: Captures the active window or full screen and explains what is currently visible.
    required_inputs: []
    output_format: json

  - name: explain_error
    description: Extracts visible compiler, terminal, or runtime error text from the screen and explains the cause.
    required_inputs: []
    output_format: json

  - name: extract_text
    description: Extracts text from the screen using OCR.
    required_inputs: []
    output_format: json

  - name: summarize_screen
    description: Summarizes the visible document or page.
    required_inputs: []
    output_format: json

  - name: get_active_window
    description: Returns the title and process of the currently focused window.
    required_inputs: []
    output_format: json

  - name: propose_fix
    description: Proposes a safe, structured desktop automation fix for the visible error.
    required_inputs: []
    output_format: json
---

# Screen Vision & Computer Understanding Skill

Performs on-demand perception of the user's screen.
Never captures screen continuously. Enforces secret filtering before cloud upload and coordinates with Desktop Automation for approved fixes.
