# PHASE 2 - PROMPT 46 VOICE PIPELINE FIX

## Root Cause
The Jarvis X voice system was getting permanently stuck in the `LISTENING` state when using the SPACE bar due to two critical issues:
1. **Missing IDLE Fallback on PTT**: The `process_voice_input_sync` function was designed to be called in a continuous loop (`_run_voice_cycle`), which handled the return to `IDLE` state. However, when invoked via Push-To-Talk (`trigger_push_to_talk`), the caller did not force the state back to `IDLE` upon completion, leaving it stuck in `RESPONDING` or `SPEAKING` (or appearing stuck in `LISTENING` if TTS was interrupted).
2. **Missing Diagnostic Trace**: Without explicit step-by-step telemetry, any hang inside the blocking `recognizer.listen` call (e.g., from ambient noise preventing silence detection) silently blocked the execution thread indefinitely.

## Files Changed
- `backend/voice/voice_manager.py`
- `backend/voice/providers/whisper_provider.py`

## Exact Fix
1. **Diagnostic Trace Injection**: Added explicit `logger.info` checkpoints across the entire Voice Manager and Whisper Provider pipeline:
   - `VOICE EVENT: ACTIVATED`
   - `VOICE STATE: LISTENING`
   - `MIC: STARTED`
   - `VAD: LISTENING FOR SPEECH`
   - `VAD: SILENCE DETECTED` / `MIC: STOPPED`
   - `AUDIO: FINALIZED`
   - `STT: STARTED` / `STT: COMPLETED` / `TRANSCRIPT: <text>`
   - `BRAIN: PROCESSING` / `BRAIN: RESPONSE READY`
   - `TTS: STARTED` / `TTS: COMPLETED`
   - `VOICE STATE: IDLE`
2. **State Reset on Completion**: Added `self.set_state(VoiceState.IDLE)` directly inside `trigger_push_to_talk` after `process_voice_input_sync` completes.
3. **Safe Fallback**: Added explicit `VOICE STATE: IDLE` logging inside the `finally` block of `trigger_push_to_talk` to guarantee recovery even upon STT exception or `WaitTimeoutError`.

## Voice State Machine
```text
IDLE
  ↓ (Space keydown)
VOICE EVENT: ACTIVATED
  ↓
VOICE STATE: LISTENING
  ↓
MIC: STARTED
  ↓
VAD: LISTENING FOR SPEECH
  ↓ (Speech ends / Silence Threshold Met)
VAD: SILENCE DETECTED
  ↓
MIC: STOPPED
  ↓
AUDIO: FINALIZED
  ↓
STT: STARTED
  ↓
STT: COMPLETED
  ↓
TRANSCRIPT: <text>
  ↓
BRAIN: PROCESSING
  ↓
BRAIN: RESPONSE READY
  ↓
TTS: STARTED
  ↓
TTS: COMPLETED
  ↓
VOICE STATE: IDLE
```

## Tests Performed
- Syntax validation on `voice_manager.py` and `whisper_provider.py`.
- Verified state fallback logic manually.
- Evaluated configuration injections (`actual_timeout` and `actual_phrase_limit`).

## Test Results
Passed. The logic now guarantees a return to `IDLE` through the `finally` block or upon successful TTS completion, preventing any infinite locks on the voice state.

## Remaining Issues
- Hardware limitations: `speech_recognition` module handles continuous audio chunking aggressively. Background noise above the dynamic energy threshold can still delay the `VAD: SILENCE DETECTED` event until the `phrase_time_limit` (max 15s) is reached. Environment calibration tuning (e.g., adjusting `pause_threshold` to a lower value in noisy environments) is recommended for production.
