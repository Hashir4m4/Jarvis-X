import logging
from typing import Dict, Any, List, Optional

from .base_skill import BaseSkill
from backend.core.models import Intent, SkillResult
from backend.vision.screen_models import (
    CaptureType, VisionTaskType, ScreenAnalysisResult
)
from backend.vision.vision_service import ScreenVisionService
from backend.llm.model_router import PrivacyPolicy

logger = logging.getLogger("JARVIS.ScreenVisionSkill")


class ScreenVisionSkill(BaseSkill):
    """
    Skill for On-Demand Screen Vision and Computer Understanding.
    Provides perception, OCR, error diagnostics, and safe action proposals.
    Integrates with the ContextManager and DesktopAutomation system.
    """

    def __init__(
        self,
        vision_service: Optional[ScreenVisionService] = None,
        metadata=None
    ):
        super().__init__(metadata=metadata)
        self.vision_service = vision_service or ScreenVisionService()

    def _notify_vision_state(self, state: str):
        # Broadcasts state changes to HUD or telemetry hooks
        logger.info(f"VISION_STATE: {state}")

    @property
    def name(self) -> str:
        return "screen_vision"

    @property
    def description(self) -> str:
        return "Understands screen content on demand, extracts text, diagnoses errors, and proposes fixes."

    @property
    def supported_actions(self) -> List[str]:
        return [
            "describe_screen",
            "explain_error",
            "extract_text",
            "summarize_screen",
            "get_active_window",
            "propose_fix",
            "fix_problem"
        ]

    def execute(self, intent: Intent, context: Dict[str, Any] = None) -> SkillResult:
        action = intent.action.lower()
        params = intent.parameters or {}

        # Determine capture type from intent
        c_type_str = params.get("capture_type", "ACTIVE_WINDOW").upper()
        try:
            c_type = CaptureType(c_type_str)
        except ValueError:
            c_type = CaptureType.ACTIVE_WINDOW

        # Determine PrivacyPolicy from context or parameters
        p_policy = PrivacyPolicy.PREFER_LOCAL
        if context and "privacy_policy" in context:
            try:
                p_policy = PrivacyPolicy(context["privacy_policy"])
            except ValueError:
                p_policy = PrivacyPolicy.PREFER_LOCAL

        # Check for conversational follow-up ("How do I fix it?", "Fix this")
        last_analysis = self.vision_service.get_last_analysis()

        if action in ("propose_fix", "fix_problem") or "fix" in intent.raw_input.lower():
            if last_analysis and last_analysis.suggested_action_plan:
                plan = last_analysis.suggested_action_plan
                msg = f"Based on the visible {last_analysis.detected_application} error, I propose [{plan['action_type']}]: {plan['description']}. This action requires your confirmation."
                return SkillResult(
                    success=True,
                    data={"action_plan": plan, "analysis": last_analysis.to_dict()},
                    message=msg,
                    output_text=msg
                )
            elif last_analysis and not last_analysis.detected_errors:
                return SkillResult(
                    success=True,
                    data={},
                    message="No visible error was detected to fix in the recent screen analysis.",
                    output_text="There are no visible errors on the screen that need fixing."
                )

        # Map intent action to VisionTaskType
        if action == "explain_error":
            v_task = VisionTaskType.ERROR_ANALYSIS
        elif action == "extract_text":
            v_task = VisionTaskType.TEXT_EXTRACTION
        elif action == "summarize_screen":
            v_task = VisionTaskType.DOCUMENT_SUMMARY
        elif action == "get_active_window":
            v_task = VisionTaskType.ACTIVE_WINDOW_ANALYSIS
        elif "where" in intent.raw_input.lower() or "locate" in intent.raw_input.lower():
            v_task = VisionTaskType.OBJECT_IDENTIFICATION
        else:
            v_task = VisionTaskType.SCREEN_DESCRIPTION

        # Execute capture and analysis
        self._notify_vision_state("VISION: ACTIVE")
        self._notify_vision_state("VISION: CAPTURING")
        
        try:
            # Note: actual capturing happens inside capture_and_analyze, but we emit analyzing immediately after
            self._notify_vision_state("VISION: ANALYZING")
            analysis: ScreenAnalysisResult = self.vision_service.capture_and_analyze(
                task_type=v_task,
                capture_type=c_type,
                privacy_policy=p_policy,
                custom_prompt=intent.raw_input
            )
            
            # Confidence Threshold Enforcement
            if analysis.confidence < 0.8 and v_task == VisionTaskType.OBJECT_IDENTIFICATION:
                self._notify_vision_state("VISION: COMPLETE")
                self._notify_vision_state("VISION: IDLE")
                return SkillResult(
                    success=False,
                    data=analysis.to_dict(),
                    message="I'm not confident enough to safely interact with that element.",
                    output_text="I'm not confident enough to safely interact with that element."
                )
                
            # Coordinate-based Desktop Interaction
            if analysis.target_coordinates and v_task == VisionTaskType.OBJECT_IDENTIFICATION:
                # Trigger action safely
                plan = {
                    "action_type": "GUI_ACTION",
                    "target": "click",
                    "coordinates": analysis.target_coordinates
                }
                msg = f"I found the target at {analysis.target_coordinates}. Generating action plan."
                self._notify_vision_state("VISION: COMPLETE")
                self._notify_vision_state("VISION: IDLE")
                return SkillResult(
                    success=True,
                    data={"action_plan": plan, "analysis": analysis.to_dict()},
                    message=msg,
                    output_text=msg
                )

            self._notify_vision_state("VISION: COMPLETE")
            self._notify_vision_state("VISION: IDLE")
            return SkillResult(
                success=analysis.confidence > 0.0 or bool(analysis.summary),
                data=analysis.to_dict(),
                message=analysis.summary,
                output_text=analysis.summary
            )
            
        except Exception as e:
            logger.error(f"Vision skill failed: {e}")
            self._notify_vision_state("VISION: ERROR")
            self._notify_vision_state("VISION: IDLE")
            return SkillResult(
                success=False,
                message=f"Vision analysis failed: {str(e)}",
                output_text="I encountered an error while trying to look at the screen."
            )
