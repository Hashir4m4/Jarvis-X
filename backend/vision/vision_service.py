import re
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image

from .screen_models import (
    CaptureType, VisionTaskType, ScreenAnalysisResult,
    WindowMetadata, StoragePolicy
)
from .screen_capture import ScreenCaptureProvider, DefaultScreenCaptureProvider
from .ocr_engine import OCREngine, ScreenPrivacyFilter
from backend.llm.model_router import (
    ModelRouter, ModelSelectionRequest, ModelRole,
    PrivacyPolicy, RoutingStatus
)
from backend.core.models import TaskCategory

logger = logging.getLogger("JARVIS.ScreenVisionService")


class ScreenVisionService:
    """
    Coordinates Screen Vision and Computer Understanding:
    1. On-Demand Capture (Full Screen, Active Window, Selected Region)
    2. OCR & Metadata Extraction (Active Application, Window Title)
    3. Privacy & Secret Leak Filtering (Warning before Cloud Upload)
    4. Model Routing (Local vs Cloud VLM based on PrivacyPolicy)
    5. Error Diagnosis & Safe Desktop Action Proposal
    """

    def __init__(
        self,
        capture_provider: Optional[ScreenCaptureProvider] = None,
        ocr_engine: Optional[OCREngine] = None,
        privacy_filter: Optional[ScreenPrivacyFilter] = None,
        model_router: Optional[ModelRouter] = None,
        vlm_client: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        self.config = config or {}
        self.capture_provider = capture_provider or DefaultScreenCaptureProvider()
        self.ocr = ocr_engine or OCREngine()
        self.privacy_filter = privacy_filter or ScreenPrivacyFilter()
        self.model_router = model_router or ModelRouter(self.config)
        self.vlm_client = vlm_client
        self.last_analysis: Optional[ScreenAnalysisResult] = None

    def capture_and_analyze(
        self,
        task_type: VisionTaskType = VisionTaskType.SCREEN_DESCRIPTION,
        capture_type: CaptureType = CaptureType.ACTIVE_WINDOW,
        region: Optional[Tuple[int, int, int, int]] = None,
        privacy_policy: PrivacyPolicy = PrivacyPolicy.PREFER_LOCAL,
        custom_prompt: Optional[str] = None
    ) -> ScreenAnalysisResult:
        """
        Executes an on-demand screen understanding pipeline with privacy safeguards.
        """
        # Setup context and performance tracking
        t0 = time.time()
        
        result = ScreenAnalysisResult(
            source_type=capture_type,
            privacy_level=privacy_policy.value if hasattr(privacy_policy, "value") else str(privacy_policy)
        )

        # 1. Capture on demand
        image: Optional[Image.Image] = None
        window_meta = WindowMetadata()

        if capture_type == CaptureType.ACTIVE_WINDOW:
            image, window_meta = self.capture_provider.capture_active_window()
        elif capture_type == CaptureType.SELECTED_REGION and region:
            image = self.capture_provider.capture_region(*region)
            window_meta = self.capture_provider.get_active_window_metadata() if hasattr(self.capture_provider, "get_active_window_metadata") else WindowMetadata()
        else:
            image = self.capture_provider.capture_screen()
            window_meta = self.capture_provider.get_active_window_metadata() if hasattr(self.capture_provider, "get_active_window_metadata") else WindowMetadata()

        if not image:
            result.summary = "Screen capture is unavailable or failed."
            result.confidence = 0.0
            return result

        result.detected_application = window_meta.app_name or "Unknown Application"
        result.window_title = window_meta.window_title or ""

        t_cap = time.time()
        result.metadata["capture_latency"] = t_cap - t0
        if image:
            result.metadata["screen_resolution"] = f"{image.width}x{image.height}"
            result.metadata["active_monitor"] = "Primary"
        result.metadata["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        # 2. OCR Text Extraction
        extracted = self.ocr.extract_text(image)
        result.extracted_text = extracted

        # 3. Privacy & Secret Filter Check
        has_secrets, categories = self.privacy_filter.scan_for_secrets(extracted + " " + result.window_title)
        result.has_sensitive_data = has_secrets
        result.sensitive_categories = categories

        t_ocr = time.time()
        result.metadata["ocr_latency"] = t_ocr - t_cap

        # Save temporary screenshot if provider supports it
        if hasattr(self.capture_provider, "save_temporary_screenshot"):
            result.image_path = self.capture_provider.save_temporary_screenshot(image, prefix="vision")

        # Config Privacy Flags
        vision_cfg = self.config.get("vision", {})
        online_enabled = vision_cfg.get("online_vision_enabled", False)
        local_enabled = vision_cfg.get("local_vision_enabled", True)

        # 4. Hybrid Model Routing
        context_str = f"Context: resolution={result.metadata.get('screen_resolution')}, app='{result.detected_application}'"
        prompt_with_ctx = f"{(custom_prompt or 'Analyze screen')}\n{context_str}"
        
        routing_req = ModelSelectionRequest(
            task_category=TaskCategory.QUESTION,
            user_input=prompt_with_ctx,
            privacy_level=privacy_policy,
            internet_available=online_enabled,
            local_llm_available=local_enabled,
            cloud_available=True,
            required_capabilities=["vision"]
        )
        routing_res = self.model_router.select(routing_req)
        result.provider = routing_res.provider
        result.model = routing_res.model or "vision"

        # 5. Privacy Enforcement
        # Rule A: LOCAL_ONLY means no cloud vision allowed
        if not local_enabled and not online_enabled:
            result.summary = "Vision analysis is unavailable: Both local and online vision are disabled."
            result.confidence = 0.0
            self.last_analysis = result
            return result
            
        if privacy_policy == PrivacyPolicy.LOCAL_ONLY and routing_res.provider != "local":
            result.summary = "Vision analysis is unavailable: Privacy policy is set to LOCAL_ONLY and no local vision model is available."
            result.confidence = 0.0
            self.last_analysis = result
            return result

        # Rule B: Secret warning before cloud upload
        if has_secrets and routing_res.provider != "local":
            cats_str = ", ".join(categories)
            result.summary = f"Privacy Warning: Sensitive content ({cats_str}) was detected on screen. Cloud vision upload was blocked for your protection."
            result.confidence = 0.0
            self.last_analysis = result
            return result

        # 6. Perform Analysis / Error Diagnosis
        if task_type in (VisionTaskType.ERROR_ANALYSIS, VisionTaskType.CODE_ERROR_ANALYSIS) or "error" in (custom_prompt or "").lower():
            self._diagnose_errors(result)
        elif task_type == VisionTaskType.TEXT_EXTRACTION:
            result.summary = f"Extracted {len(extracted)} characters from {result.detected_application}."
        elif task_type == VisionTaskType.ACTIVE_WINDOW_ANALYSIS:
            result.summary = f"Active window is '{result.window_title}' running under '{result.detected_application}'."
        else:
            # General screen description
            if extracted:
                snippet = extracted[:200].replace("\n", " ")
                result.summary = f"Looking at {result.detected_application} ('{result.window_title}'). Visible content: '{snippet}'."
            else:
                result.summary = f"Looking at {result.detected_application} ({result.window_title})."

        result.metadata["total_latency"] = time.time() - t0
        self.last_analysis = result
        return result

    def _diagnose_errors(self, result: ScreenAnalysisResult):
        """Analyzes extracted text for compiler, runtime, or Python/JS stack traces."""
        text = result.extracted_text or result.window_title
        errors = []

        # Python Tracebacks
        py_match = re.search(r"(?:Traceback \(most recent call last\):.*?)([A-Za-z0-9_]+Error: .+)", text, re.DOTALL)
        if py_match:
            err_line = py_match.group(1).strip().split("\n")[0]
            errors.append({
                "type": "Python Error",
                "message": err_line,
                "raw_trace": py_match.group(0)[:500]
            })

        # General Exception patterns
        for err_type in ["SyntaxError", "NameError", "TypeError", "ValueError", "FileNotFoundError", "ModuleNotFoundError", "ImportError", "ReferenceError"]:
            if err_type in text and not any(e["message"].startswith(err_type) for e in errors):
                errors.append({
                    "type": err_type,
                    "message": f"Detected {err_type} in active screen context."
                })

        # Terminal / Compiler Error
        if "fatal error" in text.lower() or "error: " in text.lower():
            errors.append({
                "type": "Compiler/Terminal Error",
                "message": "Terminal or build failure detected on screen."
            })

        result.detected_errors = errors

        if errors:
            top_err = errors[0]
            err_label = top_err['message'].split(':')[0] if ':' in top_err['message'] else top_err['type']
            result.summary = f"Detected {err_label}: {top_err['message']} in {result.detected_application}."
            
            # Formulate proposed action plan if appropriate
            if "FileNotFoundError" in top_err["type"] or "No such file" in top_err["message"]:
                # Propose creating missing file
                result.suggested_action_plan = {
                    "action_type": "CREATE_FILE",
                    "description": f"Create missing file required by {result.detected_application}.",
                    "risk_level": "MEDIUM",
                    "requires_confirmation": True
                }
            elif "ModuleNotFoundError" in top_err["type"] or "No module named" in top_err["message"]:
                result.suggested_action_plan = {
                    "action_type": "WORKFLOW",
                    "description": "Install missing Python dependency.",
                    "risk_level": "HIGH",
                    "requires_confirmation": True
                }
        else:
            result.summary = f"No explicit errors detected in {result.detected_application}."

    def get_last_analysis(self) -> Optional[ScreenAnalysisResult]:
        """Returns the most recent screen perception result for conversational context."""
        return self.last_analysis
