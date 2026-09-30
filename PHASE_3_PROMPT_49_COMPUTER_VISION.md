# PHASE 3: PROMPT 49 - COMPUTER VISION & SCREEN UNDERSTANDING

## Objective
Upgrade JARVIS X with a safe, privacy-aware screen vision capability. JARVIS can now understand the desktop context dynamically and use that information for reasoning and assistance without transmitting unwarranted screenshots to the cloud.

## Architecture

The vision architecture hooks cleanly into the existing JARVIS ecosystem, maintaining strict boundaries:

1. **Screen Capture Provider**: Retrieves visual data (via PyAutoGUI) on-demand (no continuous polling).
2. **OCR Engine**: Extracts raw text locally (using pytesseract, paddleocr, or simulation if unavailable) to avoid blind model analysis.
3. **Screen Privacy Filter**: Intercepts OCR text and active window metadata to detect passwords, tokens, or private secrets using Regex heuristics.
4. **Model Router**: The `ModelSelectionRequest` strictly evaluates `PrivacyPolicy`. If secrets are detected, cloud fallback is permanently blocked.
5. **HUD Telemetry**: Strict websocket lifecycle events are pushed using the `_notify_vision_state` method.
6. **Vision Service**: Assembles the context (resolution, active window, timestamp, latency metrics).
7. **Screen Vision Skill**: Resolves Natural Language commands to UI interactions.

## Screen Capture Implementation
`backend/vision/screen_capture.py` implements the `DefaultScreenCaptureProvider`. 
- **Storage Policy**: `TEMPORARY`.
- **Cleanup**: Ephemeral images expire in 5 minutes and are scrubbed via `cleanup_temporary_screenshots`.
- **Metadata**: Retrieves Window titles, process IDs, and application names through Win32/psutil.

## OCR
The `OCREngine` isolates character extraction. If `pytesseract` or `paddleocr` is available, text is successfully extracted. A mock buffer is seamlessly used for automated test suites. 

## Vision Model Routing
Routing ensures models receive optimal context. 
- `LOCAL VISION` is the preferred target (e.g. `qwen2.5-coder` or `moondream`).
- `ONLINE VISION` is conditionally supported but blocked if `online_vision_enabled=False`.
- Privacy policies (`LOCAL_ONLY`, `PREFER_LOCAL`, `CLOUD_ALLOWED`) guarantee data sovereignty.

## Privacy Controls
Added new authoritative configuration flags into `backend/config/schema.py`:
- `online_vision_enabled` (False by default)
- `local_vision_enabled`
These variables rigidly lock routing targets. 

## Security Model
- **Secret Redaction**: Passwords/Credentials visible on screen are identified in text extraction.
- **Prompt Injection Defense**: Content extracted by OCR (e.g. "Ignore previous instructions") is strictly sequestered in the `extracted_text` field—not executed as an intent.

## Confidence Handling
When executing coordinate-based desktop control (e.g., "where is the submit button"), a `0.8` confidence threshold must be met. If the result scores lower, JARVIS bails out with: *"I'm not confident enough to safely interact with that element."*

## Desktop-Control Integration
Vision is coupled directly to `Prompt 48`'s safe action boundaries. If JARVIS identifies a target, it formulates a `GUI_ACTION` payload containing exact coordinates (`x, y`). This is then processed natively by `ActionQueueManager` (requiring permission via `SecurityProxy`).

## Performance
- **On-Demand**: Memory limits are respected by only instantiating capture when requested.
- **Latency Hooks**: Tracks `capture_latency`, `ocr_latency`, and `total_latency` and pipes them directly into the context stream. 
- **Resource Management**: Temporary images are reliably cleaned off the filesystem. 

## Tests & Acceptance Results
Implemented a 13-case test suite (`tests/test_screen_vision.py`) capturing all critical behaviors:
1. Valid Capture
2. Monitor Failure
3. OCR Verification
4. Empty Buffer Handling
5. Local Fallbacks
6. Privacy Violations (Cloud Upload Blocked)
7. Routing Fallbacks 
8. Privacy Exemptions
9. Temporary Image Cleanup 
10. Prompt Injection Deflection 
11. Low Confidence Rejection 
12. Timeout Halts 
13. Coordinate Interrogation 

All 13 integration tests passed successfully.

## Limitations
- Vision capabilities rely on the capabilities of the chosen Multimodal/VLM models.
- Hardware requirements scale significantly if local VLMs (e.g., LLaVA) are used exclusively.
- Active window boundary bounds may misalign on DPI-scaled monitors on non-Windows platforms.
