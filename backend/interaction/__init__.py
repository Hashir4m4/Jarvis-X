"""
JARVIS Interaction System

Public API for the Personality and Adaptive Interaction System.
"""
from .engine import InteractionEngine
from .models import (
    PersonalityProfile, InteractionState, EmotionalSignalResult, ResponseStrategy,
    ChannelOutput, CommunicationStyle, FormalityLevel, HumorLevel, VerbosityLevel,
    TechnicalDepth, WarmthLevel, ProactivityLevel, EmotionalSignal, SignalConfidence,
    InteractionMode, ResponseLength, ToneStyle, VoiceStyle, HUDStyle
)
from .personality import PersonalityRegistry, DEFAULT_JARVIS_PROFILE, BUILT_IN_PROFILES
from .signal_detector import EmotionalSignalDetector
from .state_manager import InteractionStateManager
from .response_strategy import ResponseStrategyEngine
from .channel_adapter import ChannelAdapter

__all__ = [
    # Main engine
    "InteractionEngine",
    # Models
    "PersonalityProfile", "InteractionState", "EmotionalSignalResult",
    "ResponseStrategy", "ChannelOutput",
    # Enumerations
    "CommunicationStyle", "FormalityLevel", "HumorLevel", "VerbosityLevel",
    "TechnicalDepth", "WarmthLevel", "ProactivityLevel", "EmotionalSignal",
    "SignalConfidence", "InteractionMode", "ResponseLength", "ToneStyle",
    "VoiceStyle", "HUDStyle",
    # Components
    "PersonalityRegistry", "DEFAULT_JARVIS_PROFILE", "BUILT_IN_PROFILES",
    "EmotionalSignalDetector", "InteractionStateManager",
    "ResponseStrategyEngine", "ChannelAdapter",
]
