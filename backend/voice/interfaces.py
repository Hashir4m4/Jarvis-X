from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional, Callable, Dict, Any, List


class VoiceMode(str, Enum):
    """Modes for voice interaction."""
    MANUAL = "MANUAL"
    CONTINUOUS = "CONTINUOUS"
    DISABLED = "DISABLED"


class VoiceState(str, Enum):
    """Real-time voice state indicators displayed on the HUD."""
    IDLE = "IDLE"
    WAKE_LISTENING = "WAKE_LISTENING"
    WAKE_DETECTED = "WAKE_DETECTED"
    LISTENING = "LISTENING"
    SPEECH_DETECTED = "SPEECH_DETECTED"
    TRANSCRIBING = "TRANSCRIBING"
    PROCESSING = "PROCESSING"
    RESPONDING = "RESPONDING"
    SPEAKING = "SPEAKING"
    WAITING_FOR_FOLLOWUP = "WAITING_FOR_FOLLOWUP"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"


class STTProvider(ABC):
    """
    Abstract Speech-to-Text Provider Interface.
    Decouples JARVIS Core from concrete speech recognition implementations.
    """

    @abstractmethod
    def transcribe(self, audio_data: Optional[bytes] = None, source: str = "mic") -> Optional[str]:
        """Transcribes raw audio bytes or active microphone feed to text."""
        pass

    @abstractmethod
    def listen_and_transcribe(self, timeout: int = 5, phrase_time_limit: int = 15) -> Optional[str]:
        """Listens from microphone until silence and transcribes speech."""
        pass

    def cancel(self):
        """Cancels an ongoing listening or transcription process."""
        pass

    def is_available(self) -> bool:
        """Returns True if the STT engine is loaded and operational."""
        return True


class TTSProvider(ABC):
    """
    Abstract Text-to-Speech Provider Interface.
    Decouples JARVIS Core from concrete speech synthesis implementations.
    """

    @abstractmethod
    def speak(
        self,
        text: str,
        interrupt: bool = False,
        voice: Optional[str] = None,
        speed: Optional[int] = None
    ):
        """Synthesizes text to speech and outputs to speaker."""
        pass

    @abstractmethod
    def stop(self):
        """Interrupts ongoing speech and clears speech queue."""
        pass

    @abstractmethod
    def set_voice(self, voice_id: str):
        """Sets active voice character/accent."""
        pass

    @abstractmethod
    def set_speed(self, speed: int):
        """Sets speech rate (words per minute)."""
        pass

    @abstractmethod
    def is_speaking(self) -> bool:
        """Returns True if currently speaking audio."""
        pass

    @abstractmethod
    def shutdown(self):
        """Releases audio resources and terminates worker threads."""
        pass


class WakeWordProvider(ABC):
    """
    Abstract Wake Word Provider Interface.
    Decouples JARVIS Core from concrete wake word engines.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the wake word engine is loaded and operational."""
        pass

    @abstractmethod
    def start(self):
        """Starts the background listening thread for the wake word."""
        pass

    @abstractmethod
    def stop(self):
        """Stops the background listening thread."""
        pass

    @abstractmethod
    def configure(self, config: Dict[str, Any]):
        """Updates configuration for the wake word engine."""
        pass

    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Returns diagnostic information about the wake word engine."""
        pass
