# Screen Vision & Computer Understanding Architecture

## Executive Overview
The **Screen Vision and Computer Understanding System** empowers JARVIS OS to perceive, analyze, and comprehend what is visible on the host computer's screen on an **on-demand, privacy-first** basis.

The architecture enforces strict separation of responsibilities:
1. **Screen Vision (`ScreenVisionService` & `ScreenCaptureProvider`)**: Provides **PERCEPTION** (on-demand captures, OCR, active window metadata, and error diagnostics).
2. **JARVIS Orchestrator & Context Manager**: Coordinates conversational context and reference resolution (e.g. resolving *"Explain this error"* -> *"How do I fix it?"*).
3. **Hybrid Model Router & Privacy Boundary**: Enforces **INTELLIGENCE & PRIVACY** policies (`LOCAL_ONLY`, `PREFER_LOCAL`, `CLOUD_ALLOWED`, secret scanning).
4. **Security Proxy**: Controls **AUTHORITY** (validating risk levels and requesting elevated confirmation before sensitive operations).
5. **Desktop Controller**: Executes safe **ACTIONS** (the vision model never has direct OS authority or shell command capability).

---

## Architecture Flow

```
                     USER REQUEST (Voice / Text)
              "What am I looking at?" / "Explain this error"
                                   │
                                   ▼
                       JARVIS ORCHESTRATOR
                                   │
                                   ▼
                         SCREEN VISION SKILL
                                   │
                                   ▼
                        SCREEN CAPTURE PROVIDER
                 (Full Screen / Active Window / Region)
                                   │
                                   ▼
                         SCREEN PRIVACY FILTER
                     (Detects Tokens, Passwords, Keys)
                   ┌───────────────┴───────────────┐
                   ▼                               ▼
       [Sensitive Secrets Found]        [No Secrets Found]
                   │                               │
        Warn & Block Cloud Upload                  ▼
                                          HYBRID MODEL ROUTER
                                          (Local vs Cloud VLM)
                                                   │
                                                   ▼
                                         VISION MODEL / OCR
                                                   │
                                                   ▼
                                       STRUCTURED SCREEN CONTEXT
                                       (App, Title, Text, Errors)
                                                   │
                                                   ▼
                                          OPTIONAL ACTION PLAN
                                                   │
                                                   ▼
                                         SECURITY PROXY / HUD
                                       (Confirmation Required)
                                                   │
                                                   ▼
                                        DESKTOP CONTROLLER (Safe Action)
```

---

## Core Capabilities

### 1. Screen Capture Abstraction (`backend/vision/screen_capture.py`)
- **On-Demand Only**: Never runs continuous background recording or unsolicited streaming.
- **Capture Modes**:
  - `FULL_SCREEN`: Captures primary display.
  - `ACTIVE_WINDOW`: Focuses specifically on the active foreground application window using Win32 API rects.
  - `SELECTED_REGION`: Bounding rectangle capture `(x, y, width, height)`.
- **Storage Policies**:
  - `DO_NOT_STORE`: In-memory analysis only; no file is written to disk.
  - `TEMPORARY`: Saved to isolated temporary directory (`logs/screenshots/`) with automatic time-based purging (`max_temp_age_seconds = 300`).
  - `USER_APPROVED_SAVE`: Persisted only when explicitly requested.

### 2. OCR and Text Extraction (`backend/vision/ocr_engine.py`)
- Extracts readable textual content from application windows, terminal traces, and document pages.
- Pluggable backend support for `PaddleOCR` and `Pytesseract` with internal fallback for headless and test environments.

### 3. Privacy Boundary & Secret Leak Prevention
- **`ScreenPrivacyFilter`**:
  - Scans extracted screen text and active window titles against regular expression patterns for:
    - API keys (e.g. `sk-...`)
    - Bearer tokens
    - Password prompts
    - Private SSH/RSA keys
    - GitHub personal access tokens
    - AWS secret keys
- **Cloud Blocking**:
  - If secrets are detected on screen, cloud upload is strictly blocked, and a privacy warning is issued to the user.
  - In `LOCAL_ONLY` mode, screen data is never transmitted across the network. If no local vision model is available, JARVIS clearly informs the user instead of violating the privacy policy.

### 4. Active Window Context & Error Diagnostics
- **Window Metadata**: Captures executable process name (e.g. `Code.exe`, `chrome.exe`, `WindowsTerminal.exe`), window title, and bounding dimensions via Win32 / `psutil`.
- **Diagnostic Engine**:
  - Identifies Python stack traces (`Traceback ... ModuleNotFoundError`, `FileNotFoundError`, `TypeError`, `SyntaxError`).
  - Identifies compiler, terminal, and build errors.
  - Automatically drafts a structured desktop action proposal (e.g. `CREATE_FILE`, dependency installation workflow) that requires explicit user confirmation before executing.

### 5. Conversational Context Integration
- Integrates with `ContextManager` and `SessionContext`.
- When a user asks:
  1. *"Explain this error."* -> JARVIS analyzes the error and saves the structured context.
  2. *"How do I fix it?"* -> The reference resolution layer maps *"it"* to the recent error diagnosis and presents the proposed resolution plan.

---

## Offline & Local Operation
- When Ollama with `moondream` or `llava` is installed locally, screen description and image reasoning run 100% offline.
- When local models are absent, the system gracefully utilizes local OCR and active window heuristics without crashing or making external network calls.

---

## Testing & Verification
Automated test suite (`tests/test_screen_vision.py`) covers all 16 required verification scenarios:
1. Full-screen capture request.
2. Active-window capture request.
3. Selected-region request.
4. OCR text extraction.
5. Error analysis workflow (Python traceback identified & explained).
6. Local vision routing.
7. Cloud vision routing (when allowed).
8. `LOCAL_ONLY` privacy policy enforcement.
9. Cloud upload blocked when local vision unavailable in `LOCAL_ONLY` mode.
10. Screenshot temporary storage.
11. Screenshot cleanup (expired files deleted).
12. Sensitive content warning (API keys / password prompt detected).
13. Vision unavailable fallback.
14. Screen context follow-up request ("How do I fix it?").
15. Vision result to desktop action proposal.
16. Permission required before action execution.

All 16 unit tests and all 280+ total project regression tests pass cleanly.
