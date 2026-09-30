# JARVIS X - User Guide

## Introduction
JARVIS X is a secure, hybrid AI assistant that seamlessly interacts with your operating system, browser, and codebase while maintaining strict privacy boundaries and hardware awareness.

## Starting the System
Run the unified bootloader:
```bash
python start_jarvis.py --env production --mode hybrid
```
The bootloader will perform a sequence of subsystem tests (AI, Vision, Voice) before launching the FastAPI backend and React/Electron HUD.

## Core Interactions

### Voice Commands
Activate voice mode via the desktop shell.
- Say **"JARVIS"** to wake the assistant.
- Say **"Stop listening"** to cancel the current stream and return to IDLE.

### AI Routing Commands
You can explicitly override the automatic model router:
- *"Use offline mode."* (Blocks all cloud API calls)
- *"Use online mode."*
- *"Use hybrid mode."* (Default: Task-aware routing)
- *"Use local AI."*
- *"Don't send this online."* (Forces the request into LOCAL_ONLY privacy mode)

### Task Management (Prompt 52)
You can assign complex goals to JARVIS X:
- *"JARVIS, prepare my development environment."*
- *"Cancel task."*
- *"Pause task."* / *"Resume task."*
- *"What is the current task?"*

### Proactive Intelligence (Prompt 53)
JARVIS monitors system health in the background.
- *"Quiet mode."* (Suppresses non-critical notifications)
- *"Resume notifications."*
- *"What are you doing?"*

### Transparency
JARVIS exposes its reasoning to you:
- *"What model are you using?"*
- *"Why did you choose this model?"*
- *"Show system status."* (Updates the HUD with telemetry)

## Important Limitations
JARVIS X operates via a **Security Proxy**. It will **NOT** blindly execute destructive OS commands. When a potentially dangerous action is requested, JARVIS will pause and require explicit user approval (Y/N) before proceeding.
