# Phase 2 — Prompt 41: Production Configuration & Environment Management

## Executive Summary
This document specifies the production configuration and environment management architecture implemented for JARVIS X. The system establishes a single, authoritative, typed, and validated configuration layer (`backend/config/`) that eliminates hard-coded ports, model names, paths, and unsafe defaults while maintaining 100% backward compatibility with existing subsystems and offline-first capabilities.

---

## 1. Configuration Architecture
JARVIS X uses a centralized configuration system powered by Pydantic v2 schemas:

```
JARVIS CONFIGURATION ARCHITECTURE
==================================================================
                      [ CONFIGURATION SOURCES ]
                     
  Safe Built-in Defaults (schema.py)
            ↓
  Base & Profile JSON (configs/config.json, config.<env>.json)
            ↓
  Environment Variables (.env via python-dotenv, os.environ)
            ↓
  Explicit Runtime Overrides (CLI flags, programmatic kwargs)
            ↓
                  [ CENTRAL CONFIG LOADER ]
                    (backend/config/loader.py)
                            ↓
                    [ JARVIS CONFIG ]
                   (backend/config/schema.py)
           ┌────────────────┼────────────────┐
           ↓                ↓                ↓
   [ STARTUP VALIDATION ] [ BANNER ] [ LEGACY DICT BRIDGE ]
    (validator.py)         (banner.py)  (configs/config_loader.py)
           ↓                                 ↓
   Pass / Fail-Fast                    JARVIS Core & Subsystems
```

### Module Structure
- `backend/config/__init__.py`: Public API exporting `get_config()`, `reload_config()`, `JarvisConfig`, `ConfigValidator`, and `generate_startup_banner`.
- `backend/config/schema.py`: Strictly typed Pydantic models for Environment, Network, Paths, Features, Limits, Local AI, Cloud AI, Routing, Voice, Vision, Memory, Security, and Logging.
- `backend/config/loader.py`: Implements 4-tier precedence, merges legacy JSON with environment variables, and enforces offline boundary rules.
- `backend/config/validator.py`: Performs startup validation on network ports, URL schemes, resource ranges, directory availability, and operating mode consistency.
- `backend/config/banner.py`: Formats secret-safe startup telemetry without exposing private API keys or tokens.
- `configs/config_loader.py`: Backward-compatibility bridge delegating to the centralized loader.

---

## 2. Configuration Precedence
Configuration values are resolved through a strictly defined 4-tier hierarchy:

1. **Tier 1: Safe Built-in Defaults**
   Defined directly within the Pydantic schema models (`schema.py`). Provides production-safe fallbacks for all parameters.
2. **Tier 2: Configuration Files**
   Loaded from `configs/config.json`. If an environment profile is active (`development`, `testing`, `production`), the profile-specific file `configs/config.<profile>.json` is deep-merged over the base.
3. **Tier 3: Environment Variables**
   Loaded from `.env` (if present) and `os.environ`. Mapped into structured configuration blocks. Environment variables override configuration files.
4. **Tier 4: Explicit Runtime Overrides**
   Supplied programmatically via `load_config(overrides={...})` or CLI arguments (`--env`, `--mode`). Runtime overrides take absolute precedence.

---

## 3. Environment Profiles
JARVIS X supports three distinct environment profiles:

| Profile | Purpose | Debug Mode | Default Log Level | Developer Mode |
|---|---|---|---|---|
| `development` | Local engineering, live iteration, HUD debugging | `true` | `DEBUG` | `true` |
| `testing` | Headless automated test execution, mock providers | `true` | `WARNING` | `false` |
| `production` | Stable runtime, hardened network boundaries | `false` | `INFO` | `false` |

Profile selection is controlled via `JARVIS_ENV=production` or `--env production`.

---

## 4. AI Provider Configuration
AI models are configured independently for local offline inference and cloud intelligence.

### Local AI Configuration (`LocalAIConfig`)
- **Provider**: `ollama` (default) or `mock`.
- **Base URL**: `http://localhost:11434` (configurable via `OLLAMA_BASE_URL`).
- **Default Model**: `qwen2.5-coder:7b` (configurable via `OLLAMA_MODEL`).
- **Role Assignments**:
  - General: `LOCAL_GENERAL_MODEL` (`qwen2.5-coder:7b`)
  - Fast: `LOCAL_FAST_MODEL` (`qwen2.5:1.5b`)
  - Reasoning: `LOCAL_REASONING_MODEL` (`deepseek-r1:7b`)
  - Coding: `LOCAL_CODING_MODEL` (`qwen2.5-coder:7b`)
  - Vision: `LOCAL_VISION_MODEL` (`moondream:latest`)
- **Parameters**: Temperature (0.7), timeout (60s), context length (8192).

### Cloud AI Configuration (`CloudAIConfig`)
- **Enabled**: Explicit boolean flag (`CLOUD_PROVIDER_ENABLED`).
- **Supported Providers**: OpenAI (`gpt-4o-mini`), Anthropic (`claude-3-5-sonnet-20241022`), Google Gemini (`gemini-1.5-flash`), Groq (`llama-3.3-70b-versatile`).
- **Role Assignments**: Configurable models for general, reasoning, coding, fast, and vision tasks.

---

## 5. Offline / Online / Hybrid Policy
The system enforces strict behavioral boundaries depending on `JARVIS_MODE`:

### OFFLINE Mode
- **Policy**: 100% local operation.
- **Enforcement**: `cloud_ai_enabled` and `cloud_ai.enabled` are forced to `false`. Privacy policy is locked to `LOCAL_ONLY`.
- **Security Boundary**: If a local model or Ollama service is unavailable, JARVIS falls back to deterministic local skills. It will **never** silently make outbound cloud API calls in offline mode.

### ONLINE Mode
- **Policy**: Cloud intelligence permitted and prioritized.
- **Enforcement**: Privacy policy allows `CLOUD_ALLOWED`. Cloud provider health is verified at startup.

### HYBRID Mode (Default)
- **Policy**: Local and cloud models coexist.
- **Enforcement**: The `ModelRouter` inspects task category, complexity, and context privacy level (`PREFER_LOCAL`) to route queries locally whenever feasible, leveraging cloud models only when explicitly permitted.

---

## 6. Network Configuration
All network interfaces, ports, and endpoints are centralized:

- **Backend Host**: `127.0.0.1` (configurable via `FASTAPI_HOST`).
- **Backend Port**: `8000` (configurable via `FASTAPI_PORT`).
- **WebSocket Endpoint**: `ws://127.0.0.1:8000/ws/chat` (configurable via `VITE_WS_URL`).
- **Frontend Port**: `5173` (configurable via `HUD_PORT`).
- **CORS Allowed Origins**: Strict local whitelist (`localhost:5173`, `127.0.0.1:5173`, `localhost:8000`, `127.0.0.1:8000`).
- **Request Timeout**: 30.0 seconds.

---

## 7. Filesystem Paths
All paths are dynamically resolved relative to `project_root` (identified by repository root or `JARVIS_ROOT`), eliminating developer-specific absolute paths:

- `logs/`: `logs/jarvis.log`, `logs/automation_audit.log`, `logs/security_audit.jsonl`
- `data/`: `memory/database_storage/jarvis.sqlite`, `memory/database_storage/chroma`
- `vault/`: `vault/` (Obsidian markdown files)
- `plugins/`: `backend/plugins/`
- `skills/`: `skills/`
- `temp/`: `temp/`

---

## 8. Feature Flags
Centrally accessible boolean flags control subsystem activation:

- `voice_enabled`: Enables microphone STT and speaker TTS.
- `vision_enabled`: Enables screen capture and camera processing.
- `browser_enabled`: Enables browser automation tools.
- `automation_enabled`: Enables desktop and keyboard/mouse control.
- `plugins_enabled`: Enables plugin discovery and loading.
- `memory_enabled`: Enables SQLite, ChromaDB, and Vault storage.
- `proactive_enabled`: Enables proactive background event monitors.
- `local_ai_enabled`: Enables local Ollama execution.
- `cloud_ai_enabled`: Enables cloud AI provider dispatch.
- `hybrid_mode_enabled`: Enables dynamic model routing.
- `diagnostics_enabled`: Enables self-healing diagnostic engine.
- `developer_mode`: Enables verbose developer diagnostics.

---

## 9. Resource Limits
Configurable limits prevent denial of service, memory exhaustion, and runaway execution:

- **LLM Timeout**: 60 seconds
- **Tool Timeout**: 30 seconds
- **Agent Timeout**: 120 seconds
- **Maximum Concurrent Agents**: 4
- **Maximum Task Depth**: 2 (prevents recursive agent loops)
- **Maximum Tool Calls per Intent**: 20
- **Maximum Retrieval Results**: 3
- **Maximum File Upload Size**: 50 MB
- **Maximum Log File Size**: 10 MB (with rolling 5-backup rotation)

---

## 10. Configuration Validation
`ConfigValidator` runs at startup and enforces fail-fast error detection:

1. **Port Checks**: Validates that ports are integers within `1..65535` and ensures `backend_port != frontend_port`.
2. **URL Checks**: Validates that `ollama_url`, `websocket_url`, and `frontend_url` possess valid schemes (`http`, `https`, `ws`, `wss`) and hosts.
3. **Offline Invariant**: Asserts that `cloud_ai` is not active in `OFFLINE` mode.
4. **Directory Checks**: Automatically creates essential runtime directories (`logs/`, `memory/database_storage/`, `temp/`).
5. **Config Version**: Verifies compatibility with version `2.0`.

---

## 11. Safe Startup & Banner
When JARVIS boots via `python start_jarvis.py` or `python backend/main.py`, a sanitized telemetry banner is generated:

```
============================================================
                     JARVIS X OS v2.0                       
============================================================
  Environment Profile : DEVELOPMENT
  Operating Mode      : HYBRID
  Local AI Engine     : ENABLED (Ollama @ http://localhost:11434, qwen2.5-coder:7b)
  Cloud AI Providers  : DISABLED ([NONE CONFIGURED])
  Backend Endpoint    : http://127.0.0.1:8000
  HUD Frontend Port   : 5173
  Voice Subsystem     : ENABLED (whisper / jarvis)
  Vision Subsystem    : ENABLED (15 FPS)
  Memory & Vault      : ENABLED (SQLite + Chroma)
  Automation Control  : ENABLED (SecurityProxy Active)
  Self-Diagnostics    : ENABLED
============================================================
```
Private keys, tokens, and authorization credentials are never displayed in the banner or stored in plain text logs.

---

## 12. Frontend & Electron Integration
- **Electron Shell (`electron_app.js`)**: Dynamically resolves the HUD window URL from `process.env.HUD_URL` or `process.env.HUD_PORT`, removing hardcoded `http://localhost:5173` dependencies.
- **React Frontend (`useWebSocket.js`)**: Dynamically resolves WebSocket connectivity through `import.meta.env.VITE_WS_URL` or `window.__JARVIS_CONFIG__?.wsUrl` with fallback to port 8000.
- **Child Process Propagation**: `start_jarvis.py` exports `FASTAPI_HOST`, `FASTAPI_PORT`, `HUD_PORT`, `HUD_URL`, `JARVIS_ENV`, and `JARVIS_MODE` to child processes.

---

## 13. Testing Verification
A comprehensive test suite `tests/test_configuration.py` validates all 18 specified scenarios:

1. `test_01_default_configuration`: Built-in safe defaults.
2. `test_02_development_configuration`: Development profile settings.
3. `test_03_testing_configuration`: Testing profile settings.
4. `test_04_production_configuration`: Production profile and local host binding.
5. `test_05_offline_configuration`: Offline mode preventing cloud AI.
6. `test_06_online_configuration`: Online mode enabling cloud capabilities.
7. `test_07_hybrid_configuration`: Hybrid mode smart routing.
8. `test_08_environment_variable_overrides`: Environment variable precedence over JSON.
9. `test_09_invalid_ports`: Rejection of ports <1, >65535, and port conflicts.
10. `test_10_invalid_urls`: Rejection of malformed URLs and invalid schemes.
11. `test_11_invalid_provider`: Warning on unrecognized AI providers.
12. `test_12_missing_required_cloud_credentials`: Warning when online mode lacks keys.
13. `test_13_offline_mode_preventing_cloud_usage`: Offline mode violation detection.
14. `test_14_feature_flags`: Feature flag toggling and string parsing.
15. `test_15_path_resolution`: Project-root relative cross-platform resolution.
16. `test_16_secret_redaction`: Masking of secrets in sanitized dumps and banners.
17. `test_17_configuration_precedence`: 4-tier precedence verification.
18. `test_18_startup_validation`: Fail-fast execution on critical errors.

**Result**: 18/18 tests passed in 0.153s.

---

## 14. Migration Notes
- **Existing Installations**: Continue to work without modification. `configs/config.json` is automatically loaded and mapped to the schema.
- **Legacy Callers**: Functions calling `from configs.config_loader import load_config` receive a dictionary matching the historical schema structure.
- **Environment Profiles**: To switch profiles, set `JARVIS_ENV=production` or pass `--env production` to `python start_jarvis.py`.
