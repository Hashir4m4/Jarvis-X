# CLOUD AI PROVIDER ARCHITECTURE

## 1. Executive Summary

JARVIS OS incorporates a modular, privacy-first **Online Cloud AI Provider Layer** designed to interface with advanced commercial cloud intelligence models when internet connectivity and valid provider credentials are available.

The cloud AI architecture operates as a peer to the **Offline Local AI Brain**, abstracting provider-specific protocols away from the Central Intelligence Orchestrator. All communications strictly enforce the **Privacy Boundary**, redacting secrets, authentication tokens, and private environment variables prior to transmission.

---

## 2. Target Architecture

```
                    ┌────────────────────────────┐
                    │    JARVIS ORCHESTRATOR     │
                    │ (8-Stage Execution Engine) │
                    └─────────────┬──────────────┘
                                  │
                                  ▼
                    ┌────────────────────────────┐
                    │      MODEL LAYER / HUB     │
                    └───────┬────────────┬───────┘
                            │            │
             ┌──────────────┘            └──────────────┐
             │                                          │
             ▼                                          ▼
   ┌───────────────────┐                      ┌───────────────────┐
   │  LOCAL PROVIDERS  │                      │  CLOUD PROVIDERS  │
   │  • Ollama Daemon  │                      │• Cloud Manager Hub│
   │  • Local Quantized│                      └─────────┬─────────┘
   └───────────────────┘                                │
                          ┌─────────────────────────────┼─────────────────────────────┐
                          │                             │                             │
                          ▼                             ▼                             ▼
               ┌─────────────────────┐       ┌─────────────────────┐       ┌─────────────────────┐
               │  OpenAI-Compatible  │       │  Anthropic Claude   │       │    Google Gemini    │
               │ • OpenAI (GPT-4o)   │       │ • Claude 3.5 Sonnet │       │ • Gemini 1.5 Pro    │
               │ • Groq / DeepSeek   │       │ • Claude 3.5 Haiku  │       │ • Gemini 2.0 Flash  │
               │ • vLLM / LM Studio  │       │ • Messages API      │       │ • REST SSE API      │
               └─────────────────────┘       └─────────────────────┘       └─────────────────────┘
```

---

## 3. Provider Abstraction & Capabilities

All cloud and local AI adapters adhere to the unified `LLMProvider` interface in `backend/llm/interfaces.py`:

```python
class LLMProvider(ABC):
    @property
    def name(self) -> str: ...
    @property
    def model_name(self) -> str: ...
    def is_available(self) -> bool: ...
    def chat_sync(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse: ...
    def chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[str, None, None]: ...
    def generate(self, prompt: str, system_prompt: Optional[str] = None, **kwargs) -> LLMResponse: ...
    def list_models(self) -> List[str]: ...
    def supports_streaming(self) -> bool: ...
    def supports_tools(self) -> bool: ...
    def supports_vision(self) -> bool: ...
    def get_capabilities(self) -> Dict[str, bool]: ...
    def health_check(self) -> Dict[str, Any]: ...
```

### Structured Provider Statuses (`ProviderStatus`)
- **`AVAILABLE`**: Valid credentials, reachable network endpoint, healthy response.
- **`UNAVAILABLE`**: Network timeout, DNS failure, endpoint down (HTTP 500/502/503).
- **`MISCONFIGURED`**: Missing API key or malformed configuration URL.
- **`AUTHENTICATION_ERROR`**: Invalid/expired API key (HTTP 401/403).
- **`RATE_LIMITED`**: Provider quota or request limit exceeded (HTTP 429).
- **`DEGRADED`**: Partial functionality or non-critical latency.

---

## 4. Supported Cloud Provider Adapters

### 1. OpenAI-Compatible Adapter (`OpenAICompatibleProvider`)
- **File**: `backend/llm/providers/openai_provider.py`
- **Supported Backends**: OpenAI, Groq, DeepSeek, Together, OpenRouter, self-hosted vLLM, LM Studio.
- **Protocols**: REST `/chat/completions`, `/models`, Server-Sent Events (SSE) streaming.

### 2. Anthropic Claude Adapter (`AnthropicProvider`)
- **File**: `backend/llm/providers/anthropic_provider.py`
- **Supported Backends**: Anthropic Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus.
- **Protocols**: Messages API (`/v1/messages`), header-based system prompts, `content_block_delta` SSE streaming.

### 3. Google Gemini Adapter (`GeminiProvider`)
- **File**: `backend/llm/providers/gemini_provider.py`
- **Supported Backends**: Gemini 1.5 Pro, Gemini 1.5 Flash, Gemini 2.0 Flash.
- **Protocols**: Google AI REST API (`generateContent`, `streamGenerateContent`), multi-part JSON bodies.

---

## 5. Configurable Cloud Model Roles

Managed via `backend/llm/cloud_models.py` to decouple task requirements from hardcoded commercial models:

| Role | Environment Variable | Default Model | Task Scope |
| :--- | :--- | :--- | :--- |
| **`CLOUD_GENERAL_MODEL`** | `CLOUD_GENERAL_MODEL` | `gpt-4o-mini` | Conversational dialogue, general assistance |
| **`CLOUD_REASONING_MODEL`**| `CLOUD_REASONING_MODEL`| `o3-mini` | Deep analysis, planning, multi-agent logic |
| **`CLOUD_CODING_MODEL`** | `CLOUD_CODING_MODEL` | `claude-3-5-sonnet-20241022` | Code generation, architectural refactoring |
| **`CLOUD_FAST_MODEL`** | `CLOUD_FAST_MODEL` | `gpt-4o-mini` | Low-latency parsing, fast tool classification |
| **`CLOUD_VISION_MODEL`** | `CLOUD_VISION_MODEL` | `gpt-4o` | Multimodal screen analysis, image inspection |

---

## 6. Privacy & Context Isolation Boundary

Implemented in `backend/llm/privacy_boundary.py`, the Privacy Boundary enforces strict data hygiene before any payload is dispatched over the internet:

### Privacy Classifications
1. **`LOCAL_CONTEXT`**: Strictly retained on-device (system credentials, local SQLite paths, private Obsidian logs).
2. **`CLOUD_ALLOWED_CONTEXT`**: Cleaned, sanitized user prompt & essential dialogue context.
3. **`SENSITIVE_LOCAL_CONTEXT`**: Explicitly sensitive files (`.env`, `config.json`, raw tokens).

### Automatic Secret & Credential Redaction
Regex patterns automatically detect and replace sensitive values with `[REDACTED_SECRET]`:
- OpenAI / Anthropic / Gemini / Groq API keys (`sk-...`, `ant-api...`, `AIzaSy...`, `gsk_...`)
- GitHub / Slack tokens (`ghp_...`, `github_pat_...`, `xoxb-...`)
- AWS access keys (`AKIA...`)
- Bearer tokens & Authorization headers
- Private Key PEM blocks (`-----BEGIN PRIVATE KEY-----`)
- Password / token key-value strings

---

## 7. Connection & Health Management

- **Non-Blocking Initialization**: JARVIS boots instantly regardless of cloud provider connectivity.
- **TTL Status Caching**: Health checks are cached (default 30s) to prevent blocking request lifecycles with redundant health pings.
- **HUD Telemetry**: `CloudProviderManager.to_hud_payload()` publishes sanitized provider status summaries (counts, statuses, models) to the HUD without exposing secrets or API keys.

---

## 8. How to Configure Cloud AI

1. Copy `.env.example` to `.env`:
   ```powershell
   cp .env.example .env
   ```

2. Add your provider credentials:
   ```env
   # Enable Cloud AI
   CLOUD_PROVIDER_ENABLED=true

   # OpenAI
   OPENAI_API_KEY=sk-your-openai-api-key-here
   OPENAI_MODEL=gpt-4o-mini

   # Anthropic Claude
   ANTHROPIC_API_KEY=ant-api-your-anthropic-key-here
   ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

   # Google Gemini
   GEMINI_API_KEY=AIzaSy-your-gemini-key-here
   GEMINI_MODEL=gemini-1.5-flash
   ```

3. **To Completely Disable Cloud AI**:
   ```env
   CLOUD_PROVIDER_ENABLED=false
   ```

---

## 9. How to Add a Future Cloud Provider

1. Inherit from `LLMProvider` in `backend/llm/providers/new_provider.py`.
2. Implement `chat_sync()`, `chat_stream()`, and `is_available()`.
3. Register the new provider in `CloudProviderManager._initialize_providers()` and `backend/llm/factory.py`.
4. Add unit test assertions in `tests/test_cloud_ai_providers.py`.
