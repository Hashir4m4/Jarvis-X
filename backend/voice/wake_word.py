import logging
import time
from typing import Callable, Any, Dict

from backend.voice.interfaces import WakeWordProvider

logger = logging.getLogger("JARVIS.WakeWord")


class WakeWordDetector(WakeWordProvider):
    """
    Listens continuously in a background thread for the wake word ('Jarvis').
    Uses OpenWakeWord when available, with graceful fallback.
    """

    def __init__(self, config: dict, callback: Callable[[], Any]):
        self.callback = callback
        self.is_listening = False
        self.model = None
        self.audio = None
        self.stream = None
        
        # Internal configuration defaults
        self.wake_word_enabled = True
        self.wake_word = "jarvis"
        self.sensitivity = 0.5
        self.cooldown_period = 2.0
        self.last_trigger_time = 0.0
        
        self.configure(config)
        self._initialize()

    def configure(self, config: Dict[str, Any]):
        """Updates configuration for the wake word engine."""
        self.wake_word_enabled = config.get("wake_word_enabled", True)
        self.wake_word = config.get("wake_word", "jarvis")
        self.sensitivity = config.get("wake_word_sensitivity", 0.5)
        self.cooldown_period = config.get("cooldown_period", 2.0)

    def is_available(self) -> bool:
        """Returns True if the wake word engine is loaded and operational."""
        return self.model is not None and self.audio is not None

    def health_check(self) -> Dict[str, Any]:
        """Returns diagnostic information about the wake word engine."""
        return {
            "available": self.is_available(),
            "enabled": self.wake_word_enabled,
            "wake_word": self.wake_word,
            "sensitivity": self.sensitivity,
            "listening": self.is_listening
        }

    def _initialize(self):
        try:
            import pyaudio
            import numpy as np
            import openwakeword
            from openwakeword.model import Model

            logger.info("Initializing OpenWakeWord model...")
            try:
                openwakeword.utils.download_models()
                self.model = Model(inference_framework="onnx")
            except Exception as e:
                logger.warning(f"Could not load pre-trained wake word weights: {e}")
                self.model = None

            self.FORMAT = pyaudio.paInt16
            self.CHANNELS = 1
            self.RATE = 16000
            self.CHUNK = 1280
            self.audio = pyaudio.PyAudio()
        except ImportError as e:
            logger.info(f"OpenWakeWord/PyAudio not available: {e}. Wake word background listener disabled.")
            self.model = None
            self.audio = None

    def start(self):
        if not self.wake_word_enabled:
            logger.info("Wake word is disabled in configuration. Not starting listener.")
            return

        if not self.is_available():
            logger.debug("Wake word model or audio stream not available. Cannot start background listener.")
            return

        import numpy as np

        self.is_listening = True
        try:
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )

            logger.info(f"Listening for wake word '{self.wake_word}'...")

            while self.is_listening:
                try:
                    audio_data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                    audio_np = np.frombuffer(audio_data, dtype=np.int16)

                    # Feed to model
                    prediction = self.model.predict(audio_np)

                    # Check scores
                    for mdl in self.model.prediction_buffer.keys():
                        scores = list(self.model.prediction_buffer[mdl])
                        if scores and scores[-1] > self.sensitivity:
                            now = time.time()
                            if now - self.last_trigger_time > self.cooldown_period:
                                logger.info(f"Wake word detected! ({mdl}: {scores[-1]:.2f} > {self.sensitivity})")
                                self.last_trigger_time = now
                                self.callback()
                            else:
                                logger.debug(f"Wake word detected but suppressed by cooldown ({mdl})")
                            break

                except Exception as e:
                    if self.is_listening:
                        logger.error(f"Error reading audio stream: {e}")
                    break
        except Exception as e:
            logger.error(f"Failed to open audio input stream: {e}")
        finally:
            self.stop()

    def stop(self):
        self.is_listening = False
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if self.audio:
            try:
                self.audio.terminate()
            except Exception:
                pass
            self.audio = None
        logger.debug("WakeWordDetector stopped.")
