# Safe Computer Control & Desktop Automation Architecture

## Executive Overview
The **Safe Computer Control and Desktop Automation** system enables JARVIS OS to perform deterministic, audited, and approved actions on the host computer (Windows, macOS, Linux) without giving the AI unrestricted operating system authority.

The system enforces a strict separation of concerns:
1. **AI / Orchestrator**: Decides *WHAT* the user wants (intent classification, parameter parsing, workflow planning).
2. **Permission Gatekeeper (`SecurityProxy`)**: Determines *IF* and *UNDER WHAT PRIVILEGES* the action is authorized (`READ`, `WRITE`, `EXECUTE`, `DESTRUCTIVE`).
3. **Desktop Controller (`DesktopController` & `WindowsDesktopController`)**: Decides *HOW* the action is executed safely using rigid, platform-specific APIs.
4. **Action Queue & Verification (`ActionQueueManager`)**: Executes actions sequentially, validates completion after every step, and aborts immediately upon verification failure or emergency stop.

---

## Architecture Diagram

```
                 USER (Voice / Text / API)
                            │
                            ▼
              JARVIS INTELLIGENCE ORCHESTRATOR
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      INTENT ROUTER              CONTEXT MANAGER
 (Pattern & Semantic Match)  (Reference Resolution)
              │
              ▼
        DESKTOP SKILL (Offline & Deterministic)
              │
              ▼
     ACTION QUEUE MANAGER (Step-by-step Plan)
              │
              ▼
   SECURITY PROXY (Permission Check & Audit Log)
   ┌──────────────────────┬──────────────────────┐
   │ [LOW / MEDIUM Risk]  │   [HIGH-RISK / DESTRUCTIVE]
   │ Auto-allowed         │   User Confirmation Prompt
   └──────────┬───────────┴──────────┬───────────┘
              │                      │ (Approved)
              └──────────┬───────────┘
                         ▼
             DESKTOP CONTROLLER (OS Abstraction)
             ├── WindowsDesktopController
             └── UnsupportedDesktopController
                         │
                         ▼
                  OPERATING SYSTEM
         (Shell / Process / Win32 / Filesystem)
                         │
                         ▼
             RESULT VERIFICATION (Post-Check)
         (Check file exists, process runs, etc.)
                         │
                         ▼
                 HUD / USER RESPONSE
```

---

## Core Components

### 1. Desktop Action Abstraction (`backend/automation/desktop_models.py`)
Encapsulates all desktop control into strongly typed models:
- **`ActionType`**: `OPEN_APPLICATION`, `CLOSE_APPLICATION`, `OPEN_FILE`, `OPEN_FOLDER`, `CREATE_FOLDER`, `CREATE_FILE`, `RENAME_FILE`, `MOVE_FILE`, `COPY_FILE`, `DELETE_FILE`, `LIST_DIRECTORY`, `ORGANIZE_FILES`, `GET_SYSTEM_INFO`, `WINDOW_ACTION`, `GUI_ACTION`, `AUTOMATION_WORKFLOW`.
- **`RiskLevel`**:
  - `LOW`: Safe read-only operations (e.g., get system info, list directory, launch registered application, window minimize).
  - `MEDIUM`: Reversible modifications (e.g., create single folder, create file, rename single file, move single file).
  - `HIGH`: Destructive or bulk operations (e.g., delete file, bulk move/organize, close application/process).
- **`DesktopAction`**: Defines `action_id`, `action_type`, `target`, `parameters`, `risk_level`, `requires_confirmation`, `status`, `source`, `timestamp`.
- **`DesktopActionResult`**: Returns `success`, `action_id`, `message`, `data`, `verified`, `risk_level`, `status`.

### 2. Platform Abstraction Layer (`DesktopController`)
- **`backend/automation/desktop_controller.py`**: Abstract base class declaring the cross-platform contract:
  - `open_application(app_name, parameters)`
  - `close_application(process_or_title)`
  - `open_file(file_path)` & `open_folder(folder_path)`
  - `create_folder(folder_path)` & `create_file(file_path, content)`
  - `rename_file(src, dest)` & `move_file(src, dest)` & `copy_file(src, dest)`
  - `delete_file(file_path)`
  - `list_directory(folder_path)` & `organize_directory(folder_path, rules)`
  - `window_action(action: WindowActionType, target_title)`
  - `get_system_info()`
  - `gui_action(action_name, params)`
  - `verify_action(action: DesktopAction)`
- **`backend/automation/windows_controller.py`**:
  - Aliases: Maps "browser" -> "chrome", "vs code" -> "code", "notepad", "calculator", "explorer", "spotify", etc.
  - Safe launch via `subprocess.Popen` without shell injection.
  - Window control via Win32 API (`ctypes.windll.user32.ShowWindow`).
  - System telemetry via `psutil` (CPU %, RAM %, disk %, battery, active processes).
- **`backend/automation/unsupported_controller.py`**:
  - Explicit stub for unsupported platforms. Reports capability limitations rather than pretending features exist or crashing.

### 3. Action Queue & Verification Engine (`backend/automation/action_queue.py`)
- **Execution Pipeline**: `PLAN -> VALIDATE -> PERMISSION CHECK -> EXECUTE STEP -> VERIFY RESULT -> NEXT STEP`.
- **Post-Action Verification**:
  - `CREATE_FOLDER`: Verifies directory exists on disk.
  - `MOVE_FILE` / `RENAME_FILE`: Verifies destination path exists and source path no longer exists.
  - `DELETE_FILE`: Verifies target path is gone.
  - `OPEN_APPLICATION`: Confirms process appears in running process table or launch request returned 0.
- **Fail-Safe Mechanism**: If post-verification fails on any step, the pipeline immediately halts and flags an error without continuing to make blind assumptions.

### 4. Security & Risk Governance (`backend/automation/security_proxy.py`)
- **Risk Classification**:
  - `READ` / `LOW`: Auto-executed and logged.
  - `WRITE` / `MEDIUM`: Executed safely and logged.
  - `DESTRUCTIVE` / `HIGH`: Pauses pipeline, emits `WAITING_FOR_CONFIRMATION` event, and prompts the user for explicit approval (`[Y/N]` or interactive callback). The AI cannot approve its own action.
- **Audit Logging**: Structured plain text and JSONL logs (`logs/automation_audit.log` and `logs/security_audit.jsonl`).
- **Secret Redaction**: API keys, bearer tokens, passwords, and private tokens are automatically redacted via regex before being written to disk or shown in prompts.

### 5. Emergency Stop (`emergency_stop`)
- Can be activated at any time via text or continuous voice:
  - *"Stop."*
  - *"Cancel that."*
  - *"Abort automation."*
  - *"Emergency stop."*
- Instantly triggers `ActionQueueManager.trigger_emergency_stop()`, marks current and pending actions as `CANCELLED`, and halts the controller thread.

---

## Offline Capabilities
Core desktop automation operates 100% offline:
- Opening registered applications via aliases.
- File and folder operations (create, rename, move, delete, list, organize).
- System diagnostics and hardware telemetry.
- Window management and GUI interactions.
Deterministic regex patterns in `IntentRouter` route requests directly to `DesktopSkill` without requiring cloud AI or active internet connectivity.

---

## Supported Operating Systems
| Operating System | Support Level | Notes |
|---|---|---|
| **Windows 10 / 11** | Full Production | Win32 API, `taskkill`, `explorer`, `psutil`, PowerShell alias resolution. |
| **macOS** | Architecture Ready | Abstracted via `DesktopController`. Fallback reports capability status. |
| **Linux** | Architecture Ready | Abstracted via `DesktopController`. Fallback reports capability status. |

---

## Known Limitations
1. **Window Control on Non-Windows Platforms**: Window minimization/maximization relies on Win32 API on Windows; other platforms require platform-specific window managers (e.g., `xdotool` or AppleScript).
2. **Screen Coordinate GUI Automation**: While `pyautogui` is supported for fallback keystrokes and clicks, structured OS APIs are strictly preferred over brittle coordinate clicking.
3. **Unsaved Application State**: Force-closing an application via `close_application` terminates the process (`taskkill /F`), which will discard unsaved files. It is categorized as `HIGH` risk for this reason.
