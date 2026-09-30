# OFFLINE LOCAL AI BRAIN ARCHITECTURE

## 1. Executive Summary

JARVIS OS incorporates an autonomous, privacy-first **Offline Local AI Brain** capable of operating continuously without internet access. When disconnected from the internet, JARVIS automatically adapts its operating mode, routes conversation and cognitive workloads to local Ollama models, leverages on-device SQLite and Obsidian Vault memory, and executes local system automation without data leakage or cloud dependency.

---

## 2. Intelligence & Routing Flow

```
                      ┌────────────────────────────┐
                      │    USER / VOICE / HUD      │
                      └─────────────┬──────────────┘
                                    │
                                    ▼
                      ┌────────────────────────────┐
                      │     JARVIS CORE ENGINE     │
                      └─────────────┬──────────────┘
                                    │
                                    ▼
                      ┌────────────────────────────┐
                      │    CAPABILITY DETECTOR     │
                      │  (Socket DNS Check & TTL)  │
                      └─────────────┬──────────────┘
                                    │
                   ┌────────────────┴────────────────┐
                   │                                 │
           [Internet Online]                 [Internet Offline]
                   │                                 │
                   ▼                                 ▼
      ┌─────────────────────────┐       ┌─────────────────────────┐
      │       HYBRID MODE       │       │    LOCAL / OFFLINE      │
      │ • Cloud AI Providers    │       │ • Ollama Local Daemon   │
      │ • Web Search / APIs     │       │ • Local Quantized LLMs  │
      │ • Live Weather & News   │       │ • Obsidian Vault Memory │
      └────────────┬────────────┘       │ • Local Automation/Tools│
                   │                    └────────────┬────────────┘
                   │                                 │
                   └────────────────┬────────────────┘
                                    │
                                    ▼
                      ┌────────────────────────────┐
                      │    CENTRAL ORCHESTRATOR    │
                      │  (8-Stage Context Pipeline)│
                      └─────────────┬──────────────┘
                                    │
                                    ▼
                      ┌────────────────────────────┐
                      │  UNIFIED RESPONSE / HUD    │
                      └────────────────────────────┘
```

---

## 3. Operating Modes (`AIMode`)

The system dynamically classifies its operational state into 5 discrete modes via `backend/core/capability_detector.py`:

| Mode | Internet | Local LLM | Memory API | Primary Capabilities |
| :--- | :---: | :---: | :---: | :--- |
| **`LOCAL`** | ❌ | ✅ | ✅ | Full local AI dialogue, local memory, computer control, vision |
| **`HYBRID`** | ✅ | ✅ | ✅ | Intelligent routing between local models and online APIs |
| **`CLOUD`** | ✅ | ❌ | ✅ | Cloud API fallback when local daemon is unavailable |
| **`OFFLINE`** | ❌ | ❌ | ✅ | Deterministic skill execution (volume, apps, notes, metrics) |
| **`DEGRADED`** | ❌ | ❌ | ❌ | Minimal survival state with core diagnostics |

---

## 4. Local Model Roles & Task Specialization

Configured in `backend/llm/local_models.py`, JARVIS specializes local models according to task requirements and hardware capacities:

| Role | Default Model | Alternate | Specialized Tasks |
| :--- | :--- | :--- | :--- |
| **`LOCAL_GENERAL_MODEL`** | `qwen2.5-coder:7b` | `llama3.2:3b` | Conversational dialogue, general queries |
| **`LOCAL_FAST_MODEL`** | `qwen2.5:1.5b` | `llama3.2:1b` | Low-latency intent parsing, system commands |
| **`LOCAL_REASONING_MODEL`**| `deepseek-r1:7b` | `qwen2.5:7b` | Complex planning, multi-step agent reasoning |
| **`LOCAL_CODING_MODEL`** | `qwen2.5-coder:7b` | `qwen2.5-coder:14b` | Code synthesis, refactoring, bug auditing |
| **`LOCAL_VISION_MODEL`** | `moondream:latest` | `llama3.2-vision` | Screen analysis, visual inspection |

### Hardware Profiling & RAM Tiers
```python
def detect_hardware_profile():
    # Detects RAM and CPU cores to recommend model quantization tiers
    # >= 32GB RAM -> 14B - 32B models
    # >= 16GB RAM -> 7B - 8B models
    # >= 8GB RAM  -> 3B - 7B (Q4_K_M quantized)
    # < 8GB RAM   -> 1B - 3B models
```

---

## 5. Local Provider Adapter (`OllamaProvider`)

The `OllamaProvider` in `backend/llm/providers/ollama_provider.py` connects directly to the local Ollama daemon without external API keys:

- **Endpoint**: `http://localhost:11434`
- **Supported APIs**:
  - `/api/chat`: Synchronous and streaming conversation with system prompts and context.
  - `/api/generate`: Raw prompt completions for agents and tools.
  - `/api/tags`: Real-time model enumeration and daemon health verification.
- **Resilience & Error Handling**:
  - `LLMErrorType.TIMEOUT`: Non-fatal timeout notification on slow hardware.
  - `LLMErrorType.MODEL_UNAVAILABLE`: Friendly guidance instructing user to `ollama pull <model>`.
  - `LLMErrorType.PROVIDER_UNAVAILABLE`: Graceful fallback to deterministic skill handlers without system crash.

---

## 6. Non-Hallucinatory Offline Integrity

A foundational principle of JARVIS OS is absolute truthfulness regarding offline capabilities:
1. **Never Fabricate Live Data**: When offline, requests requiring real-time web data ("search the web", "latest news", "current stock price") will **never** generate hallucinated search results.
2. **Transparent Notification**: Returns:
   > *"Internet connection is currently unavailable (Offline Mode). Cannot perform live web research. Local memory, file operations, system tools, and offline planning remain available."*
3. **Local Alternatives**: Automatically offers local Obsidian Vault searches or SQLite historical retrieval as an alternative.

---

## 7. Offline Boot & Quickstart

To run JARVIS OS 100% offline:

1. **Start Ollama Service**:
   ```powershell
   ollama serve
   ```

2. **Pull Recommended Models**:
   ```powershell
   ollama pull qwen2.5-coder:7b
   ollama pull qwen2.5:1.5b
   ollama pull deepseek-r1:7b
   ollama pull moondream:latest
   ```

3. **Launch JARVIS OS**:
   ```powershell
   python -m backend.main
   ```

4. **Verify Offline Test Suite**:
   ```powershell
   python -m unittest tests/test_offline_local_ai.py
   ```
