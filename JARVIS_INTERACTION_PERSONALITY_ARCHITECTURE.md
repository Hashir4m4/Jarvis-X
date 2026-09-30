# JARVIS Interaction & Personality Architecture

## Overview

The JARVIS Personality and Adaptive Interaction System makes JARVIS feel like one consistent, sophisticated AI assistant across all channels — chat, voice, and HUD — without replacing any intelligence, safety, or reasoning systems.

**Core principle**: The personality layer *wraps* the Orchestrator. It shapes communication. It does not control decisions, bypass permissions, or replace intelligence.

---

## Pipeline

```
USER INPUT
  │
  ▼
CONTEXT MANAGER (existing — resolves references, retrieves history)
  │
  ▼
INTERACTION PRE-PROCESSING                     [backend/interaction/]
  ├── InteractionStateManager.update_state()   (session-scoped, volatile)
  ├── EmotionalSignalDetector.detect()         (lexical heuristics only)
  └── ResponseStrategyEngine.determine()       (strategy decision table)
  │
  ▼
JARVIS ORCHESTRATOR (existing — unchanged intelligence pipeline)
  ├── Intent routing, skill execution, agent coordination
  ├── Planning, memory, permissions, capability detection
  │
  ▼
INTERACTION POST-PROCESSING                    [backend/interaction/]
  └── ChannelAdapter.adapt()                   (per-channel output formatting)
  │
  ▼
TEXT / VOICE / HUD
```

---

## Component Map

| File | Responsibility |
|------|---------------|
| `backend/interaction/models.py` | All typed enumerations and dataclasses |
| `backend/interaction/personality.py` | Profile registry, loading, switching |
| `backend/interaction/signal_detector.py` | Lexical emotional signal detection |
| `backend/interaction/state_manager.py` | Per-session volatile interaction state |
| `backend/interaction/response_strategy.py` | Strategy decision engine |
| `backend/interaction/channel_adapter.py` | Channel-specific output adaptation |
| `backend/interaction/engine.py` | Central facade (InteractionEngine) |

---

## Personality Profiles

Personality is defined in `PersonalityProfile` dataclasses. All values are enum-typed — no magic strings scattered across the codebase.

### Default JARVIS Profile

| Field | Value | Notes |
|-------|-------|-------|
| `formality` | `PROFESSIONAL` | |
| `verbosity` | `ADAPTIVE` | Adjusts by task |
| `humor_level` | `LOW` | Occasional wit only |
| `technical_depth` | `ADAPTIVE` | Scales to task complexity |
| `warmth_level` | `MODERATE` | Supportive, not excessive |
| `proactivity_level` | `CONTROLLED` | Suggests, doesn't push |
| `voice_style` | `CONVERSATIONAL` | Natural TTS delivery |

### Built-in Profiles

| Profile ID | Use Case |
|-----------|----------|
| `default_jarvis` | General purpose |
| `technical_expert` | Architecture analysis, deep dives |
| `builder` | Creation workflows, action-oriented |
| `focus` | Quiet, concise, no interruptions |

Custom profiles are persisted in `configs/personality_profiles.json`.

Switching: `"switch to builder mode"` → `InteractionEngine.switch_profile("builder")`

---

## Interaction State

`InteractionState` is a **per-session, in-memory-only** structure.

**Never auto-persisted. Never written to Long-Term Memory.**

| Field | Purpose |
|-------|---------|
| `active_task_id` | Current running task |
| `active_task_context` | Task description |
| `recent_tone` | Last detected emotional signal |
| `urgency_level` | 0–2 escalating urgency |
| `frustration_indicators` | Accumulating count (decays) |
| `focus_active` | Focus mode flag |
| `interaction_mode` | STANDARD / TECHNICAL_EXPERT / BUILDER / FOCUS / SOCIAL |
| `correction_frequency` | Number of times user corrected JARVIS |

---

## Emotional Signal Analysis

The `EmotionalSignalDetector` uses **lexical heuristics only** — no LLM, no cloud calls.

### Signal Categories

| Signal | Examples |
|--------|---------|
| `NEUTRAL` | Default, no indicators |
| `FRUSTRATED` | "still broken", "driving me crazy", "ugh" |
| `CONFUSED` | "I don't understand", "what does that mean", "huh?" |
| `EXCITED` | "amazing!", "let's go!", "awesome" |
| `URGENT` | "ASAP", "deadline", "hurry", "right now" |
| `FOCUSED` | "just give me", "short answer", "no explanations" |
| `UNSURE` | "maybe", "I think", "not sure" |

### Confidence Levels

| Confidence | Threshold | Behavior |
|-----------|-----------|----------|
| `HIGH` | Score ≥ 5 | Full tone adaptation |
| `MODERATE` | Score ≥ 3 | Full tone adaptation |
| `LOW` | Score < 3 | Defaults to NEUTRAL, no adaptation |

**Design constraint**: A single sentence is insufficient for HIGH confidence. Evidence compounds across history window and session count.

### Always included in result
- `signal` — enum category
- `confidence` — HIGH / MODERATE / LOW
- `evidence_summary` — human-readable explanation of indicators

---

## Response Strategy Engine

The `ResponseStrategyEngine` maps inputs to a `ResponseStrategy` using a priority-ordered decision table.

### Priority Order (highest first)

1. **Critical / Error** — overrides everything (no humor, PROFESSIONAL tone, MEDIUM length)
2. **Focus Mode** — SHORT, DIRECT, no suggestions, no humor
3. **Emotional Signal** (if actionable confidence) — tone and depth adaptation
4. **Interaction Mode** — TECHNICAL_EXPERT, BUILDER, SOCIAL overrides
5. **Task Category** — length and depth defaults
6. **Personality Profile** — baseline

### Signal → Strategy Mapping

| Signal | Tone | Humor | Length | Suggestions |
|--------|------|-------|--------|-------------|
| FRUSTRATED | CALM | NONE | MEDIUM | Yes (solutions) |
| CONFUSED | SUPPORTIVE | NONE | MEDIUM | Yes |
| URGENT | DIRECT | NONE | SHORT | No |
| FOCUSED | DIRECT | NONE | SHORT | No |
| EXCITED | WARM | LOW | MEDIUM | Profile default |
| UNSURE | SUPPORTIVE | Profile | MEDIUM | Yes |

---

## Channel Adaptation

The `ChannelAdapter` produces distinct output for each channel from a single raw response.

| Channel | Behavior |
|---------|----------|
| **TEXT** | Full response, length per strategy (SHORT/MEDIUM/LONG/ADAPTIVE) |
| **VOICE** | Strips markdown, headings, code blocks, tables. Trimmed to ≤300 chars for conversational style, ≤1 sentence for STATUS |
| **HUD** | First sentence, truncated to ≤12 words |

### Error Communication

Raw technical errors are reformatted to human-readable messages:
- AI service offline → "The AI service is unavailable right now. The local fallback is ready."
- Timeout → "The operation timed out. Try breaking the task into smaller steps."
- Permission denied → "The action was not permitted under the current security policy."

Causes are **never fabricated**. Only available information is presented.

### Confidence-Aware Language

| Certainty | Language |
|----------|----------|
| High (success) | Direct: "The local model server is offline." |
| Moderate (partial_failure) | Hedged: "The connection failure may be caused by..." |
| Low / Unknown | Cautious: "I cannot confirm the cause yet." |

### Controlled Wit

Humor is injected only when:
- `humor_level != NONE`
- Not in a critical/error situation
- Signal is not FRUSTRATED, URGENT, CONFUSED, or FOCUSED
- Mode is not TECHNICAL_EXPERT

Maximum one wit remark per response, appended — never replacing substantive content.

---

## Voice Personality

TTS delivery adapts to the response context:

| Context | Voice Style | Behavior |
|---------|------------|----------|
| System status | STATUS | Single sentence, direct |
| Conversation | CONVERSATIONAL | 1–2 sentences, stripped markdown |
| Alert/Error | ALERT | Clear, urgent but calm |
| Technical | NEUTRAL | Minimal phrasing |

Long documents are **never read aloud** unless explicitly requested. Code blocks are replaced with "(code block omitted)".

---

## Interaction Modes

| Mode | Characteristics |
|------|----------------|
| `STANDARD` | Balanced defaults from profile |
| `TECHNICAL_EXPERT` | EXPERT depth, LONG length, no humor, structured reasoning |
| `BUILDER` | Action-oriented, EXPERT depth, MEDIUM length, collaborative |
| `FOCUS` | SHORT, DIRECT, no humor, no suggestions |
| `SOCIAL` | SHORT, WARM, no tools activated |

Modes are set via:
```python
engine.set_interaction_mode(session_id, InteractionMode.BUILDER)
# or natural language:
engine.switch_profile("builder")  # fuzzy matches profile name
```

---

## Social Interaction

Greetings ("how are you", "hey", "good morning") are handled in a social short-circuit before the Orchestrator executes. **No tools, agents, or skills are activated.**

JARVIS does **not** pretend to have human feelings:
- ✅ "Operational and ready. What would you like to work on?"
- ❌ "I'm doing great, thanks for asking!"

---

## Clarification Policy

| Situation | Behavior |
|----------|---------|
| `"continue"` + active task | Continues without asking |
| `"open it"` + no context | Asks: "Which item would you like me to open?" |
| Multiple matching objects | Always asks |
| Clear intent, no ambiguity | Proceeds directly |

---

## Interruption Handling

| Input | Voice | Task |
|-------|-------|------|
| "stop talking" | Stops | Unchanged |
| "be quiet" | Stops | Unchanged |
| "cancel the task" | Stops | Cancelled |
| "stop the task" | Stops | Cancelled |
| "stop everything" | Stops | Cancelled |

Interruption detection uses `EmotionalSignalDetector.is_interruption_command()` **before** the Orchestrator pipeline.

---

## Privacy Protections

| Guarantee | Mechanism |
|----------|-----------|
| Emotional signals are session-only | `InteractionState` is in-memory only |
| No auto-persistence to Long-Term Memory | State never writes to MemoryAPI automatically |
| No psychological profiling | Only communication signals (7 categories), never diagnoses |
| No mental health inference | Explicit design constraint in detector |
| Explicit preferences only | Only `record_user_preference()` calls write to MemoryAPI |
| Profile changes require explicit action | `switch_profile()` or `record_user_preference()` |

---

## Memory Boundaries

| Stored | Not Stored |
|--------|-----------|
| Explicit user preferences ("always technical") | Temporary frustration signals |
| Profile selection (active_profile_id) | Emotional state at any given turn |
| Custom profiles | Casual mood or excited responses |

---

## Personality Consistency

Personality is applied **after** execution, regardless of which model was used.

```
local model → raw response → ChannelAdapter → JARVIS voice
cloud model → raw response → ChannelAdapter → JARVIS voice
```

The final user experience is always the same JARVIS voice.

Agents produce structured findings. JARVIS applies personality to the synthesis. The user experiences **one assistant**.

---

## Proactive Communication

Notifications from the Proactive Engine are adapted through `InteractionEngine.adapt_notification()`:
- In **FOCUS mode**: shortened, voice-only, no suggestions
- In **QUIET mode**: standard, no additions
- In **DO_NOT_DISTURB**: suppressed unless CRITICAL priority

---

## Integration Points

| Component | Change |
|----------|--------|
| `backend/interaction/` | **New package** |
| `backend/core/core.py` | Instantiates `InteractionEngine`, injects into Orchestrator |
| `backend/orchestrator/orchestrator.py` | `pre_process()` at Step 1c, `post_process()` at Step 10 |
| `backend/router/context.py` | Added `interaction_strategy` and `interaction_channel_output` fields |

All integration is **non-breaking** — the Orchestrator functions identically if `InteractionEngine` is absent (all blocks are guarded with `if self.interaction_engine:`).

---

## Testing Strategy

`tests/test_personality_interaction.py` — 39 tests, 0 cloud AI required.

All model outputs are mocked strings. Tests verify:
- Profile loading and serialization
- Strategy determination for each signal category
- Clarification policy
- Channel adaptation (text, voice, HUD)
- Error reformatting
- Confidence language
- Humor suppression
- Social short-circuit
- Interruption semantics
- Focus Mode
- Privacy constraints

---

## Known Limitations

1. **Signal detection is lexical only** — cannot detect frustration in polite but persistently repeated corrections without history context.
2. **Voice adaptation is rule-based** — no TTS prosody control (speed, pitch). Those are TTS provider concerns.
3. **Single active profile** — no multi-profile blending. Builder mode completely replaces Default JARVIS profile fields.
4. **Humor library is small** — 5 trigger phrases currently. Expand `_WIT_SUFFIXES` in `channel_adapter.py` to grow the library.
5. **No sentiment memory across sessions** — frustration accumulates within a session only. A new session starts from NEUTRAL.
6. **HUD truncation is word-count based** — no semantic summarization. Very long first sentences may still produce long HUD strings if they have no mid-sentence breaks.

---

## Testing the Personality System

### Run automated tests
```bash
python -m pytest tests/test_personality_interaction.py -v
```

### Manual Verification Scenarios

**Scenario 1 — Simple question**
```
Input: "What's the battery level?"
Expected: 1–2 sentence response. No preamble.
```

**Scenario 2 — Technical question**
```
Input: "Explain the architecture of the RAG system."
Expected: Structured, detailed, technical response with section headers.
Voice: Summary of first 1–2 key points only.
```

**Scenario 3 — Frustration**
```
Input: "This error is driving me crazy!"
Expected: CALM tone. No humor. "Let's narrow this down step by step."
NOT: "I know exactly how you feel!"
```

**Scenario 4 — Context-aware continue**
```
Active task: "Refactoring authentication"
Input: "Continue."
Expected: Continues task. Does not ask "Continue what?"
```

**Scenario 5 — Voice stop only**
```
Input: "Stop talking."
Expected: Voice stops. Task remains active.
```

**Scenario 6 — Critical warning**
```
Context: Critical system error
Expected: Professional, concise. No humor. No witty remarks.
```

**Scenario 7 — Model switch consistency**
```
Switch from cloud model to local model.
Expected: JARVIS response tone and style remain identical.
```
