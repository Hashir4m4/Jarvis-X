"""
JARVIS Interaction System — Core Data Models

Defines all typed models for personality profiles, interaction state,
emotional signal detection, response strategy, and channel-adapted output.

These are pure data containers. No business logic lives here.
"""
import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────────────────────────────────────

class CommunicationStyle(str, enum.Enum):
    """Overall communication approach."""
    CONCISE = "CONCISE"
    BALANCED = "BALANCED"
    DETAILED = "DETAILED"


class FormalityLevel(str, enum.Enum):
    """Formality register for responses."""
    CASUAL = "CASUAL"
    PROFESSIONAL = "PROFESSIONAL"
    TECHNICAL = "TECHNICAL"


class HumorLevel(str, enum.Enum):
    """How much controlled wit is permitted."""
    NONE = "NONE"
    LOW = "LOW"
    MODERATE = "MODERATE"


class VerbosityLevel(str, enum.Enum):
    """Default response length bias."""
    CONCISE = "CONCISE"
    ADAPTIVE = "ADAPTIVE"
    DETAILED = "DETAILED"


class TechnicalDepth(str, enum.Enum):
    """Degree of technical terminology and detail."""
    SIMPLE = "SIMPLE"
    ADAPTIVE = "ADAPTIVE"
    EXPERT = "EXPERT"


class WarmthLevel(str, enum.Enum):
    """Friendliness tone."""
    MINIMAL = "MINIMAL"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class ProactivityLevel(str, enum.Enum):
    """How often JARVIS volunteers information."""
    MINIMAL = "MINIMAL"
    CONTROLLED = "CONTROLLED"
    PROACTIVE = "PROACTIVE"


class EmotionalSignal(str, enum.Enum):
    """
    Lightweight communication-signal categories.

    IMPORTANT: These are communication signals, not psychological diagnoses.
    They inform tone adaptation only. Confidence thresholds prevent over-inference.
    """
    NEUTRAL = "NEUTRAL"
    FRUSTRATED = "FRUSTRATED"
    CONFUSED = "CONFUSED"
    EXCITED = "EXCITED"
    URGENT = "URGENT"
    FOCUSED = "FOCUSED"
    UNSURE = "UNSURE"


class SignalConfidence(str, enum.Enum):
    """How confident the detector is about a signal classification."""
    HIGH = "HIGH"
    MODERATE = "MODERATE"
    LOW = "LOW"


class InteractionMode(str, enum.Enum):
    """Active interaction context that shapes response style."""
    STANDARD = "STANDARD"
    TECHNICAL_EXPERT = "TECHNICAL_EXPERT"
    BUILDER = "BUILDER"
    FOCUS = "FOCUS"
    SOCIAL = "SOCIAL"


class ResponseLength(str, enum.Enum):
    """Target length for the response."""
    SHORT = "SHORT"          # 1-2 sentences
    MEDIUM = "MEDIUM"        # 3-5 sentences
    LONG = "LONG"            # Paragraphs / structured sections
    ADAPTIVE = "ADAPTIVE"    # System decides per context


class ToneStyle(str, enum.Enum):
    """Emotional register of the response."""
    CALM = "CALM"
    PROFESSIONAL = "PROFESSIONAL"
    WARM = "WARM"
    DIRECT = "DIRECT"
    SUPPORTIVE = "SUPPORTIVE"


class VoiceStyle(str, enum.Enum):
    """TTS delivery style for voice channel."""
    NEUTRAL = "NEUTRAL"
    STATUS = "STATUS"        # Brief system status
    CONVERSATIONAL = "CONVERSATIONAL"
    ALERT = "ALERT"          # Urgent notification


class HUDStyle(str, enum.Enum):
    """Display style for HUD channel."""
    STATUS = "STATUS"
    NOTIFICATION = "NOTIFICATION"
    ERROR = "ERROR"
    PROGRESS = "PROGRESS"


# ─────────────────────────────────────────────────────────────────────────────
# PersonalityProfile
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PersonalityProfile:
    """
    Configurable JARVIS personality definition.

    All values are enum-typed to prevent arbitrary string drift.
    Profiles are loaded from config — never hard-coded throughout the codebase.
    """
    profile_id: str = field(default_factory=lambda: f"profile_{uuid.uuid4().hex[:6]}")
    name: str = "Default JARVIS"
    communication_style: CommunicationStyle = CommunicationStyle.BALANCED
    formality: FormalityLevel = FormalityLevel.PROFESSIONAL
    verbosity: VerbosityLevel = VerbosityLevel.ADAPTIVE
    humor_level: HumorLevel = HumorLevel.LOW
    technical_depth: TechnicalDepth = TechnicalDepth.ADAPTIVE
    warmth_level: WarmthLevel = WarmthLevel.MODERATE
    proactivity_level: ProactivityLevel = ProactivityLevel.CONTROLLED
    voice_style: VoiceStyle = VoiceStyle.CONVERSATIONAL
    preferred_response_patterns: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "communication_style": self.communication_style.value,
            "formality": self.formality.value,
            "verbosity": self.verbosity.value,
            "humor_level": self.humor_level.value,
            "technical_depth": self.technical_depth.value,
            "warmth_level": self.warmth_level.value,
            "proactivity_level": self.proactivity_level.value,
            "voice_style": self.voice_style.value,
            "preferred_response_patterns": self.preferred_response_patterns
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalityProfile":
        try:
            return cls(
                profile_id=data.get("profile_id", f"profile_{uuid.uuid4().hex[:6]}"),
                name=data.get("name", "Default JARVIS"),
                communication_style=CommunicationStyle(data.get("communication_style", "BALANCED")),
                formality=FormalityLevel(data.get("formality", "PROFESSIONAL")),
                verbosity=VerbosityLevel(data.get("verbosity", "ADAPTIVE")),
                humor_level=HumorLevel(data.get("humor_level", "LOW")),
                technical_depth=TechnicalDepth(data.get("technical_depth", "ADAPTIVE")),
                warmth_level=WarmthLevel(data.get("warmth_level", "MODERATE")),
                proactivity_level=ProactivityLevel(data.get("proactivity_level", "CONTROLLED")),
                voice_style=VoiceStyle(data.get("voice_style", "CONVERSATIONAL")),
                preferred_response_patterns=data.get("preferred_response_patterns", [])
            )
        except Exception:
            return cls()  # Fail safe to default


# ─────────────────────────────────────────────────────────────────────────────
# InteractionState  (short-term, per-session, never auto-persisted)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class InteractionState:
    """
    Short-term interaction context within a session.

    This is a volatile, in-memory structure. It is NEVER automatically
    written to Long-Term Memory or the Personal Knowledge Base.
    Only explicit user preferences may be forwarded to MemoryAPI with permission.
    """
    session_id: str = "default"
    active_task_context: Optional[str] = None     # Active task description if any
    active_task_id: Optional[str] = None          # Task plan ID if running
    recent_tone: EmotionalSignal = EmotionalSignal.NEUTRAL
    urgency_level: int = 0                        # 0=normal, 1=elevated, 2=urgent
    correction_frequency: int = 0                 # How often user has corrected JARVIS
    frustration_indicators: int = 0               # Count of frustration signals this session
    interrupt_state: bool = False                 # Whether voice is being interrupted
    focus_active: bool = False                    # Whether Focus Mode is on
    interaction_mode: InteractionMode = InteractionMode.STANDARD
    last_activity: float = field(default_factory=time.time)
    conversation_turn: int = 0

    def reset_emotional_counters(self):
        """Clears per-session signal counters without losing task context."""
        self.correction_frequency = 0
        self.frustration_indicators = 0
        self.recent_tone = EmotionalSignal.NEUTRAL


# ─────────────────────────────────────────────────────────────────────────────
# EmotionalSignalResult
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EmotionalSignalResult:
    """
    Cautious classification of a communication signal.

    Confidence is always included. Evidence is always summarized.
    The system NEVER presents a LOW-confidence signal as fact.
    """
    signal: EmotionalSignal = EmotionalSignal.NEUTRAL
    confidence: SignalConfidence = SignalConfidence.LOW
    evidence_summary: str = ""
    raw_indicators: List[str] = field(default_factory=list)

    def is_actionable(self) -> bool:
        """Only HIGH or MODERATE confidence signals trigger tone adaptation."""
        return self.confidence in (SignalConfidence.HIGH, SignalConfidence.MODERATE)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal": self.signal.value,
            "confidence": self.confidence.value,
            "evidence_summary": self.evidence_summary,
            "raw_indicators": self.raw_indicators
        }


# ─────────────────────────────────────────────────────────────────────────────
# ResponseStrategy
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ResponseStrategy:
    """
    Concrete communication plan determined before final response generation.

    Produced by ResponseStrategyEngine and consumed by ChannelAdapter.
    """
    response_length: ResponseLength = ResponseLength.ADAPTIVE
    tone: ToneStyle = ToneStyle.PROFESSIONAL
    technical_depth: TechnicalDepth = TechnicalDepth.ADAPTIVE
    humor_level: HumorLevel = HumorLevel.NONE
    proactive_suggestions: bool = True
    clarification_needed: bool = False
    voice_style: VoiceStyle = VoiceStyle.CONVERSATIONAL
    hud_style: HUDStyle = HUDStyle.STATUS
    interaction_mode: InteractionMode = InteractionMode.STANDARD
    signal: EmotionalSignal = EmotionalSignal.NEUTRAL
    is_critical: bool = False       # Forces no humor, concise, professional
    is_error: bool = False          # Triggers error communication reformatter

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_length": self.response_length.value,
            "tone": self.tone.value,
            "technical_depth": self.technical_depth.value,
            "humor_level": self.humor_level.value,
            "proactive_suggestions": self.proactive_suggestions,
            "clarification_needed": self.clarification_needed,
            "voice_style": self.voice_style.value,
            "hud_style": self.hud_style.value,
            "interaction_mode": self.interaction_mode.value,
            "signal": self.signal.value,
            "is_critical": self.is_critical,
            "is_error": self.is_error
        }


# ─────────────────────────────────────────────────────────────────────────────
# ChannelOutput
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ChannelOutput:
    """
    Final adapted content for each output channel.

    TEXT, VOICE, and HUD may differ. The same information need not be
    delivered identically across channels.
    """
    text: str = ""     # Full text response for chat/API
    voice: str = ""    # Shorter, spoken-natural version for TTS
    hud: str = ""      # ≤12 word status for HUD display
    strategy: Optional[ResponseStrategy] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "voice": self.voice,
            "hud": self.hud,
            "strategy": self.strategy.to_dict() if self.strategy else {}
        }
