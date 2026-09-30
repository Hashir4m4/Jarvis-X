import logging
import io
import wave
import speech_recognition as sr
from faster_whisper import WhisperModel
from typing import Optional

logger = logging.getLogger(__name__)

class SpeechToText:
    def __init__(self, config: dict):
        self.config = config
        self.model_size = config.get("whisper_model", "base")
        
        logger.info(f"Loading faster-whisper model '{self.model_size}'...")
        try:
            # Load model on GPU if available, else CPU
            self.model = WhisperModel(self.model_size, device="auto", compute_type="default")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            self.model = None

        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = config.get("energy_threshold", 300)
        self.recognizer.dynamic_energy_threshold = config.get("dynamic_energy_threshold", True)
        self.recognizer.pause_threshold = config.get("pause_threshold", 0.8)

    def listen_and_transcribe(self) -> Optional[str]:
        """
        Listens to the microphone until the user stops speaking, 
        then transcribes the audio using faster-whisper.
        """
        if not self.model:
            logger.error("Whisper model is not loaded.")
            return None

        with sr.Microphone(sample_rate=16000) as source:
            logger.info("Listening for command...")
            # Adjust for ambient noise if dynamic threshold is true
            if self.recognizer.dynamic_energy_threshold:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            
            try:
                # Listen until silence
                audio_data = self.recognizer.listen(source, timeout=5, phrase_time_limit=15)
                logger.info("Processing speech...")
                
                # Convert to wav bytes for faster-whisper
                wav_data = audio_data.get_wav_data()
                
                # Use faster-whisper to transcribe from memory
                segments, info = self.model.transcribe(io.BytesIO(wav_data), beam_size=5)
                
                text = " ".join([segment.text for segment in segments]).strip()
                logger.info(f"Transcribed: '{text}'")
                return text if text else None
                
            except sr.WaitTimeoutError:
                logger.info("Listening timed out.")
                return None
            except Exception as e:
                logger.error(f"Error during transcription: {e}")
                return None
