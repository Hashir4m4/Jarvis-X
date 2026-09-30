import logging
import asyncio
import threading
import time
from typing import Optional, Dict, Any, Callable

from backend.voice.interfaces import VoiceState, VoiceMode, STTProvider, TTSProvider
from backend.voice.providers.whisper_provider import FasterWhisperSTTProvider
from backend.voice.providers.pyttsx3_provider import Pyttsx3TTSProvider
from backend.core.models import UserInput, InputChannel, CoreResponse
from backend.voice.wake_word import WakeWordDetector
import uuid

logger = logging.getLogger("JARVIS.VoiceManager")


class VoiceManager:
    """
    Master Voice Subsystem Orchestrator for JARVIS OS.
    Implements the full unified voice pipeline:
    MIC -> STT -> JARVIS ROUTER -> EXECUTION -> RESPONSE -> TTS -> SPEAKER
    """

    def __init__(
        self,
        config: Dict[str, Any],
        router: Optional[Any] = None,
        stt_provider: Optional[STTProvider] = None,
        tts_provider: Optional[TTSProvider] = None,
        state_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        self.config = config
        self.router = router
        self.voice_config = config.get("voice", {})
        self.state_callback = state_callback

        # 1. Provider Layer (decoupled from direct library dependencies)
        self.stt: STTProvider = stt_provider or FasterWhisperSTTProvider(self.voice_config)
        self.tts: TTSProvider = tts_provider or Pyttsx3TTSProvider(self.voice_config)

        # 2. Wake Word Detector
        self.wake_word_detector = WakeWordDetector(self.voice_config, self._on_wake_word)
        self.wake_word_thread: Optional[threading.Thread] = None

        self._state: VoiceState = VoiceState.IDLE
        self.mode: VoiceMode = VoiceMode(self.voice_config.get("mode", "CONTINUOUS"))
        self._is_active = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._current_session_id: str = str(uuid.uuid4())

        logger.info(f"Unified Voice Manager initialized with {self.stt.__class__.__name__} and {self.tts.__class__.__name__}.")

    @property
    def state(self) -> VoiceState:
        return self._state

    def set_state(self, new_state: VoiceState, details: Optional[Dict[str, Any]] = None):
        """Updates internal voice state and broadcasts telemetry to HUD WebSocket."""
        self._state = new_state
        payload = {
            "type": "voice_state",
            "state": new_state.value,
            "details": details or {},
            "timestamp": time.time()
        }
        logger.debug(f"[VOICE STATE] -> {new_state.value}")
        if self.state_callback:
            try:
                self.state_callback(payload)
            except Exception as e:
                logger.debug(f"Voice state callback exception: {e}")

    def start(self, event_loop: Optional[asyncio.AbstractEventLoop] = None):
        """Starts the voice listener and wake word monitoring thread."""
        if self._is_active:
            return

        self._is_active = True
        self._loop = event_loop
        
        if self.wake_word_detector.wake_word_enabled:
            self.set_state(VoiceState.WAKE_LISTENING)
            self.wake_word_thread = threading.Thread(target=self.wake_word_detector.start, daemon=True)
            self.wake_word_thread.start()
            logger.info("Voice Subsystem ONLINE. Listening for wake word...")
            self.tts.speak("Voice interface online.")
        else:
            self.set_state(VoiceState.IDLE)
            logger.info("Voice Subsystem ONLINE. Wake word disabled.")
            self.tts.speak("Voice interface online. Wake word disabled.")

    def stop(self):
        """Halts voice monitoring and shuts down audio providers."""
        self._is_active = False
        self.wake_word_detector.stop()
        self.stt.cancel()
        self.tts.stop()
        self.tts.shutdown()
        self.set_state(VoiceState.IDLE)
        logger.info("Voice Subsystem stopped.")

    def _on_wake_word(self):
        """Callback invoked when wake word ('Jarvis') is heard."""
        if not self._is_active:
            return

        logger.info("Wake word triggered. Transitioning to WAKE_DETECTED.")
        self.set_state(VoiceState.WAKE_DETECTED)
        self.tts.stop()  # Interrupt any active speech
        
        # Play activation feedback (a short TTS or sound)
        try:
            self.tts.speak("Yes?", interrupt=True)
        except Exception:
            pass

        # Execute voice interaction in worker thread to not block wake word engine
        threading.Thread(target=self._run_voice_cycle, daemon=True).start()

    def _run_voice_cycle(self):
        """Runs the sequential voice cycle: Listen -> Transcribe -> Route -> Speak -> Followup."""
        if self.mode == VoiceMode.DISABLED:
            logger.info("Voice mode is DISABLED. Ignoring wake word.")
            return

        # Start a new session for this continuous run
        self._current_session_id = str(uuid.uuid4())
        
        while self._is_active and self.mode in (VoiceMode.CONTINUOUS, VoiceMode.MANUAL):
            try:
                # 1. LISTENING
                self.set_state(VoiceState.LISTENING)
                if self.mode == VoiceMode.MANUAL and self.state != VoiceState.WAKE_DETECTED:
                    self.tts.speak("Yes, sir?", interrupt=True)
                    time.sleep(0.5)

                # 2. TRANSCRIBING
                self.set_state(VoiceState.TRANSCRIBING)
                # Shorter timeouts if we are continuously looping
                timeout = 5 if self.mode == VoiceMode.MANUAL else 3
                transcript = self.stt.listen_and_transcribe(timeout=timeout, phrase_time_limit=15)

                if not transcript or not isinstance(transcript, str) or not transcript.strip():
                    logger.info("No speech detected.")
                    if self.wake_word_detector.wake_word_enabled:
                        self.set_state(VoiceState.WAKE_LISTENING)
                    else:
                        self.set_state(VoiceState.IDLE)
                    break

                logger.info(f"Transcribed voice input: '{transcript}'")
                
                # Check for interruption hot-commands
                cleaned = transcript.lower().strip().rstrip(".!?")
                if cleaned in ["stop", "cancel", "shut up", "pause"]:
                    self.set_state(VoiceState.CANCELLED)
                    self.interrupt_speech()
                    break

                self.set_state(VoiceState.SPEECH_DETECTED)
                self.process_voice_input_sync(transcript)

                if self.mode == VoiceMode.MANUAL:
                    break
                else:
                    self.set_state(VoiceState.WAITING_FOR_FOLLOWUP)

            except Exception as e:
                logger.error(f"Error during voice cycle: {e}", exc_info=True)
                self.set_state(VoiceState.ERROR, {"error": str(e)})
                time.sleep(1.0)
                if self.wake_word_detector.wake_word_enabled:
                    self.set_state(VoiceState.WAKE_LISTENING)
                else:
                    self.set_state(VoiceState.IDLE)
                break

    def trigger_push_to_talk(self) -> Optional[str]:
        """Push-to-talk trigger from HUD button."""
        if self.state in [VoiceState.LISTENING, VoiceState.TRANSCRIBING, VoiceState.PROCESSING]:
            logger.warning("Already processing voice input. Ignoring duplicate PTT trigger.")
            return None

        self.tts.stop()
        logger.info("VOICE_SESSION_STARTED")
        self.set_state(VoiceState.LISTENING)
        logger.info("VOICE STATE: LISTENING")
        transcript = None
        try:
            transcript = self.stt.listen_and_transcribe(timeout=6, phrase_time_limit=15)
        except Exception as e:
            logger.error(f"Error during PTT listening: {e}")
        finally:
            if not transcript:
                if self.state in [VoiceState.LISTENING, VoiceState.TRANSCRIBING]:
                    self.set_state(VoiceState.IDLE)
                    logger.info("VOICE STATE: IDLE")
                    logger.info("VOICE_SESSION_COMPLETED")

        if transcript:
            logger.info("TRANSCRIPT_RECEIVED")
            self.process_voice_input_sync(transcript)
            self.set_state(VoiceState.IDLE)
            logger.info("VOICE STATE: IDLE")
            logger.info("VOICE_SESSION_COMPLETED")
            return transcript
        return None

    def stop_push_to_talk(self):
        """Called when PTT button is released."""
        logger.info("PTT button released. Stopping capture.")
        if hasattr(self.stt, "stop_listening"):
            self.stt.stop_listening()
        else:
            self.stt.cancel()

    def process_voice_input_sync(self, text_or_audio: Any) -> Optional[str]:
        """
        Synchronously coordinates:
        STT Text (or raw audio) -> Central Router -> Execution -> Response -> TTS
        """
        try:
            if isinstance(text_or_audio, (bytes, bytearray)):
                self.set_state(VoiceState.TRANSCRIBING)
                text = self.stt.transcribe(text_or_audio)
            else:
                text = str(text_or_audio)

            if not text or not text.strip():
                self.set_state(VoiceState.IDLE)
                return None

            # 3. PROCESSING
            self.set_state(VoiceState.PROCESSING, {"query": text})
            logger.info("BRAIN: PROCESSING")
            # Link voice context with the current session
            user_input = UserInput(content=text, channel=InputChannel.VOICE, session_id=self._current_session_id)

            response_text = ""
            if self.router:
                if hasattr(self.router, "execute"):
                    # Check if running inside asyncio loop or thread
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    if loop.is_running():
                        future = asyncio.run_coroutine_threadsafe(self.router.execute(user_input), loop)
                        exec_result = future.result(timeout=30)
                    else:
                        exec_result = loop.run_until_complete(self.router.execute(user_input))

                    response_text = exec_result.response if hasattr(exec_result, "response") else str(exec_result)
                elif hasattr(self.router, "process_input"):
                    # JarvisCore wrapper
                    try:
                        loop = asyncio.get_event_loop()
                    except RuntimeError:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)

                    if loop.is_running():
                        future = asyncio.run_coroutine_threadsafe(self.router.process_input(user_input), loop)
                        core_res: CoreResponse = future.result(timeout=30)
                    else:
                        core_res: CoreResponse = loop.run_until_complete(self.router.process_input(user_input))
                    response_text = core_res.text
            else:
                response_text = "Router not attached."

            logger.info("BRAIN: RESPONSE READY")

            # 6. RESPONDING & SPEAKING
            if response_text and self.tts:
                self.set_state(VoiceState.RESPONDING)
                
                # Format response to prevent 10-minute monologues
                tts_text = response_text
                if len(tts_text) > 300:
                    sentences = [s.strip() for s in tts_text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
                    summary = ". ".join(sentences[:2]) + "." if sentences else tts_text[:300] + "..."
                    tts_text = f"{summary} I have displayed the full details on your screen."
                
                self.set_state(VoiceState.SPEAKING, {"response": tts_text})
                try:
                    logger.info("TTS_STARTED")
                    self.tts.speak(tts_text)
                    logger.info("TTS_COMPLETED")
                except Exception as tts_err:
                    logger.warning(f"TTS_ERROR: {tts_err}")
                
                # Do not immediately return to IDLE here, caller handles transition
                return response_text
            else:
                self.set_state(VoiceState.IDLE)
                return response_text or None

        except Exception as e:
            logger.error(f"VOICE_ERROR: {e}", exc_info=True)
            self.set_state(VoiceState.ERROR, {"error": str(e)})
            try:
                self.tts.speak("I encountered an error executing your command.")
            except Exception:
                pass
            self.set_state(VoiceState.IDLE)
            return None

    def interrupt_speech(self):
        """Immediately silences the TTS voice."""
        logger.info("TTS STOP")
        self.tts.stop()
        logger.info("SPEAKING CANCELLED")
        self.set_state(VoiceState.IDLE)

    def cancel(self):
        """Cancels any ongoing voice capture or synthesis."""
        self.stt.cancel()
        self.tts.stop()
        self.set_state(VoiceState.IDLE)
