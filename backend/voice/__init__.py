from .interfaces import VoiceState, STTProvider, TTSProvider
from .providers.whisper_provider import FasterWhisperSTTProvider
from .providers.pyttsx3_provider import Pyttsx3TTSProvider
from .voice_manager import VoiceManager

# Backward compatibility aliases
SpeechToText = FasterWhisperSTTProvider
TextToSpeech = Pyttsx3TTSProvider

__all__ = [
    "VoiceState",
    "STTProvider",
    "TTSProvider",
    "FasterWhisperSTTProvider",
    "Pyttsx3TTSProvider",
    "VoiceManager",
    "SpeechToText",
    "TextToSpeech",
]
