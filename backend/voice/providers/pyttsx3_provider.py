import logging
import threading
import queue
import re
from typing import Optional, Dict, Any

from backend.voice.interfaces import TTSProvider

logger = logging.getLogger("JARVIS.TTS.Pyttsx3")


class Pyttsx3TTSProvider(TTSProvider):
    """
    PyTTSx3 implementation of TTSProvider.
    Features: asynchronous speech queue, immediate interruption, configurable rate/speed and voice ID.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.speech_queue = queue.Queue()
        self._is_speaking = False
        self._current_speed = self.config.get("speech_rate", 175)
        self._current_voice = self.config.get("voice_id", None)
        self._running = True

        self.worker_thread = threading.Thread(target=self._speak_worker, daemon=True)
        self.worker_thread.start()

    def _speak_worker(self):
        """Worker thread dedicated to pyttsx3 synthesis."""
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", self._current_speed)
            if self._current_voice:
                engine.setProperty("voice", self._current_voice)
        except Exception as e:
            logger.error(f"Failed to initialize pyttsx3 engine in worker: {e}")
            engine = None

        while self._running:
            try:
                item = self.speech_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                break  # Exit signal

            text, voice, speed = item
            if not text or not engine:
                self.speech_queue.task_done()
                continue

            self._is_speaking = True
            try:
                # Apply custom voice or speed if specified for this utterance
                if speed:
                    engine.setProperty("rate", speed)
                elif self._current_speed:
                    engine.setProperty("rate", self._current_speed)

                if voice:
                    engine.setProperty("voice", voice)
                elif self._current_voice:
                    engine.setProperty("voice", self._current_voice)

                logger.info(f"Speaking aloud: '{text[:60]}...'")
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                logger.error(f"Error during pyttsx3 speech output: {e}")
            finally:
                self._is_speaking = False
                self.speech_queue.task_done()

    @staticmethod
    def _clean_text(text: str) -> str:
        """Strips markdown asterisks, hashes, backticks, and links for spoken output."""
        clean = re.sub(r"[#*_`~\[\]]", "", text)
        clean = re.sub(r"\(https?://[^\)]+\)", "", clean)
        return clean.strip()

    def speak(
        self,
        text: str,
        interrupt: bool = False,
        voice: Optional[str] = None,
        speed: Optional[int] = None
    ):
        """Queues text to be spoken, with optional queue interruption."""
        if interrupt:
            self.stop()

        clean = self._clean_text(text)
        if clean:
            self.speech_queue.put((clean, voice, speed))

    def stop(self):
        """Clears pending items from the speech queue."""
        with self.speech_queue.mutex:
            self.speech_queue.queue.clear()
        self._is_speaking = False
        logger.info("Speech queue cleared/interrupted.")

    def set_voice(self, voice_id: str):
        """Configures active voice identifier."""
        self._current_voice = voice_id
        logger.info(f"Set TTS voice to: {voice_id}")

    def set_speed(self, speed: int):
        """Configures speech rate in words per minute."""
        self._current_speed = speed
        logger.info(f"Set TTS speech rate to: {speed}")

    def is_speaking(self) -> bool:
        return self._is_speaking or not self.speech_queue.empty()

    def shutdown(self):
        """Stops worker thread and releases resources."""
        self._running = False
        self.stop()
        self.speech_queue.put(None)
        if self.worker_thread.is_alive():
            self.worker_thread.join(timeout=1.0)
        logger.info("PyTTSx3 provider shut down.")
