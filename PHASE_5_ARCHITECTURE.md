# PHASE 5 ARCHITECTURE SPECIFICATION
## ADVANCED JARVIS EXPERIENCE (PROMPTS 66–75)

### 1. Architectural Layers & Component Interactions

```mermaid
flowchart TD
    User([User / Human Operator])
    
    subgraph Presentation ["Desktop Experience & HUD"]
        HUD[HUD 2.0 Dashboard]
        Deck[Command Center Console]
        Telemetry[System Telemetry Panel]
        NotifUI[Notification Feed]
    end
    
    subgraph CoreServices ["Phase 5 Experience Services"]
        HUDService[HUD State Aggregator]
        CommandService[Desktop Command Center]
        VizService[System Visualization Service]
        NotifService[Notification Service]
        MultiModal[Multimodal Orchestrator]
        Workspace[Workspace Intelligence]
        Ambient[Ambient Intelligence]
    end
    
    subgraph CoreSystem ["JARVIS OS Kernel & Phase 4 Subsystems"]
        Core[JarvisCore]
        Container[AppContainer]
        Control[Autonomous Control Framework]
        Router[IntentRouter & CentralRouter]
        VoiceMgr[Voice Manager]
        Workflows[Workflow Engine]
    end

    User -->|Voice / PTT| VoiceMgr
    User -->|Type Command| Deck
    User -->|View Live State| HUD
    
    Deck --> CommandService
    HUD --> HUDService
    Telemetry --> VizService
    NotifUI --> NotifService
    
    CommandService -->|Validate & Check Emergency Stop| Control
    CommandService -->|Execute UserInput| Core
    HUDService -->|Aggregate Status| Core
    HUDService -->|Query Telemetry| VizService
    HUDService -->|Fetch Alerts| NotifService
    
    Core --> Router
    Core --> VoiceMgr
    Core --> MultiModal
    Core --> Workspace
    Core --> Ambient
    
    Ambient -->|Context Suggestions| NotifService
    MultiModal -->|Check Camera Permission| User
    Workspace -->|Confined File Indexing| User
```

### 2. Service Responsibilities & Boundaries
1. **HUD 2.0**: Read-only state aggregation across all modules. If any subsystem is uninitialized or in an error state, it is recorded in `degraded_services` and does not throw exceptions.
2. **Command Center**: Strictly validates command input against dangerous shell execution (`rm -rf`, `del /s`, `format`, `eval`, `exec`). Checks the `AutonomousControlFramework` emergency stop state before dispatching.
3. **System Visualization**: Real-time bounded telemetry metrics using `psutil`. Bounded deques ensure zero memory accumulation. Transparently declares unavailable metrics.
4. **Notification Service**: Central routing of alerts with deduplication, quiet hours filtering, and unread management. Actions are non-authorizing.
5. **Multimodal Orchestrator**: Fuses audio transcripts and visual payloads into structured prompts. Enforces strict camera permission verification.
6. **Workspace Intelligence**: Scans and indexes local files strictly within authorized workspace roots. Rejects path traversal and auto-ignores `.env`, keys, and binary caches.
7. **Ambient Intelligence**: Opt-in ambient assistance. Default-disabled, zero keylogging, zero hidden camera/mic surveillance, schedule-bounded, and kill-switch enabled.
