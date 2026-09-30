import logging
import pyttsx3
import threading
import queue

logger = logging.getLogger(__name__)

class TextToSpeech:
    def __init__(self, config: dict):
        self.config = config
        self.engine_type = config.get("tts_engine", "pyttsx3")
        self.speech_queue = queue.Queue()
        self.is_speaking = False
        
        # Thread for speaking so it doesn't block the main loop
        self.worker_thread = threading.Thread(target=self._speak_worker, daemon=True)
        self.worker_thread.start()

    def _speak_worker(self):
        # pyttsx3 needs to be initialized in the thread it's used in
        engine = pyttsx3.init()
        # You could configure voice speed, volume, and voice type here based on config
        engine.setProperty('rate', 170)
        
        while True:
            text = self.speech_queue.get()
            if text is None:
                break # Exit signal
            
            self.is_speaking = True
            logger.info(f"Speaking: '{text}'")
            try:
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                logger.error(f"TTS error: {e}")
            finally:
                self.is_speaking = False
                self.speech_queue.task_done()

    def speak(self, text: str):
        """Adds text to the queue to be spoken."""
        # Clean up text (remove markdown etc if needed, though simple models output text)
        clean_text = text.replace("*", "").replace("#", "").strip()
        if clean_text:
            self.speech_queue.put(clean_text)

    def stop(self):
        """Clears the queue. (pyttsx3 is hard to interrupt mid-sentence without process killing, but this stops the next ones)"""
        with self.speech_queue.mutex:
            self.speech_queue.queue.clear()
        
    def shutdown(self):
        self.stop()
        self.speech_queue.put(None)
        self.worker_thread.join(timeout=2)
