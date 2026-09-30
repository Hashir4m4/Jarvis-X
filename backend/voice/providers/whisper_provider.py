import io
import logging
from typing import Optional, Dict, Any

from backend.voice.interfaces import STTProvider

logger = logging.getLogger("JARVIS.STT.Whisper")


class FasterWhisperSTTProvider(STTProvider):
    """
    Faster-Whisper implementation of STTProvider.
    Supports live microphone transcription, push-to-talk, cancellation, and error handling.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.model_size = self.config.get("whisper_model", "base")
        self._cancelled = False
        self.model = None
        self.recognizer = None

        self._initialize_engine()

    def _initialize_engine(self):
        """Loads WhisperModel and SpeechRecognition gracefully."""
        try:
            from faster_whisper import WhisperModel
            import speech_recognition as sr

            logger.info(f"Initializing faster-whisper model '{self.model_size}'...")
            self.model = WhisperModel(self.model_size, device="auto", compute_type="default")
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = self.config.get("energy_threshold", 300)
            self.recognizer.dynamic_energy_threshold = self.config.get("dynamic_energy_threshold", True)
            self.recognizer.pause_threshold = self.config.get("pause_threshold", 0.8)
        except Exception as e:
            logger.error(f"Failed to load faster-whisper engine: {e}")
            self.model = None
            self.recognizer = None

    def is_available(self) -> bool:
        return self.model is not None and self.recognizer is not None

    def cancel(self):
        """Cancels an ongoing listening/transcription operation."""
        self._cancelled = True
        logger.info("STT cancellation requested.")

    def transcribe(self, audio_data: Optional[bytes] = None, source: str = "mic") -> Optional[str]:
        """Transcribes raw WAV audio bytes using faster-whisper."""
        if not self.is_available():
            logger.error("Whisper STT model not available.")
            return None

        if not audio_data:
            return self.listen_and_transcribe()

        self._cancelled = False
        try:
            logger.info("STT_STARTED")
            segments, _ = self.model.transcribe(io.BytesIO(audio_data), beam_size=5)
            text = " ".join([segment.text for segment in segments]).strip()
            logger.info("STT_COMPLETED")
            logger.info(f"TRANSCRIPT: {text}")
            return text if text else None
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    def listen_and_transcribe(self, timeout: int = 5, phrase_time_limit: int = 15) -> Optional[str]:
        """Listens from the default microphone and transcribes captured speech."""
        if not self.is_available():
            logger.error("Whisper STT model not available.")
            return None

        import speech_recognition as sr

        self._cancelled = False
        try:
            with sr.Microphone(sample_rate=16000) as mic_source:
                logger.info("MIC_STARTED")
                if self.recognizer.dynamic_energy_threshold:
                    self.recognizer.adjust_for_ambient_noise(mic_source, duration=0.4)

                actual_timeout = self.config.get("listen_timeout", timeout)
                actual_phrase_limit = self.config.get("phrase_time_limit", phrase_time_limit)

                logger.info("SPEECH_DETECTED")
                audio_data = self.recognizer.listen(mic_source, timeout=actual_timeout, phrase_time_limit=actual_phrase_limit)

                logger.info("SPEECH_ENDED")

                if self._cancelled:
                    logger.info("Listening cancelled.")
                    return None

                logger.info("AUDIO: FINALIZED")
                wav_bytes = audio_data.get_wav_data()
                return self.transcribe(wav_bytes)

        except sr.WaitTimeoutError:
            logger.info("Voice listening timed out (no speech detected).")
            logger.info("SPEECH_ENDED")
            return None
        except Exception as e:
            logger.error(f"Voice input error: {e}")
            logger.info("STT_ERROR")
            return None
