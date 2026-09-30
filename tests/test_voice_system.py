import unittest
import asyncio
import os
import sys
import tempfile
import shutil
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock external hardware/audio dependencies
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['pycaw'] = MagicMock()
sys.modules['pycaw.pycaw'] = MagicMock()
sys.modules['comtypes'] = MagicMock()
sys.modules['pyttsx3'] = MagicMock()
sys.modules['faster_whisper'] = MagicMock()
sys.modules['speech_recognition'] = MagicMock()

from backend.voice.interfaces import VoiceState, STTProvider, TTSProvider
from backend.voice.providers.whisper_provider import FasterWhisperSTTProvider
from backend.voice.providers.pyttsx3_provider import Pyttsx3TTSProvider
from backend.voice.voice_manager import VoiceManager
from backend.core.models import UserInput, InputChannel
from backend.router.context import RouterExecutionResult


class MockSTT(STTProvider):
    def __init__(self, sample_text="Show my system status."):
        self.sample_text = sample_text
        self.transcribed = False
        self.cancelled = False

    def transcribe(self, audio_data=None, source="mic"):
        self.transcribed = True
        return self.sample_text

    def listen_and_transcribe(self, timeout=5, phrase_time_limit=15):
        self.transcribed = True
        return self.sample_text

    def cancel(self):
        self.cancelled = True


class MockTTS(TTSProvider):
    def __init__(self):
        self.spoken_texts = []
        self.stopped = False
        self.current_speed = 175
        self.current_voice = None
        self._is_speaking = False

    def speak(self, text, interrupt=False, voice=None, speed=None):
        if interrupt:
            self.stop()
        self.spoken_texts.append(text)

    def stop(self):
        self.stopped = True

    def set_voice(self, voice_id):
        self.current_voice = voice_id

    def set_speed(self, speed):
        self.current_speed = speed

    def is_speaking(self):
        return self._is_speaking

    def shutdown(self):
        self.stop()


class TestVoiceSystem(unittest.TestCase):
    def setUp(self):
        self.config = {
            "voice": {
                "wake_word": "jarvis",
                "tts_engine": "pyttsx3",
                "stt_engine": "whisper",
                "whisper_model": "base"
            }
        }
        self.state_transitions = []
        def state_cb(payload):
            self.state_transitions.append(payload.get("state"))

        self.mock_stt = MockSTT("Show my system status.")
        self.mock_tts = MockTTS()

        self.mock_router = MagicMock()
        async def mock_execute(user_input):
            return RouterExecutionResult(
                intent={"type": "system_control", "skill": "system", "action": "get_system_info"},
                skill="system",
                status="success",
                response="System status: CPU is 12%, RAM is 45%.",
                actions=["get_system_info"],
                memory_updates=[],
                execution_time_ms=15.0,
                request_id=user_input.request_id
            )
        self.mock_router.execute = mock_execute

        self.voice_manager = VoiceManager(
            config=self.config,
            router=self.mock_router,
            stt_provider=self.mock_stt,
            tts_provider=self.mock_tts,
            state_callback=state_cb
        )

    def test_voice_states_enum(self):
        """Verify all required voice states exist."""
        required = {
            "IDLE", "WAKE_LISTENING", "WAKE_DETECTED", "LISTENING", "SPEECH_DETECTED",
            "TRANSCRIBING", "PROCESSING", "RESPONDING", "SPEAKING", "WAITING_FOR_FOLLOWUP",
            "ERROR", "CANCELLED"
        }
        actual = {state.name for state in VoiceState}
        self.assertEqual(required, actual)

    def test_voice_pipeline_end_to_end(self):
        """
        Verify: MIC -> STT -> JARVIS ROUTER -> EXECUTION -> RESPONSE -> TTS -> SPEAKER
        """
        # Execute voice command pipeline
        response = self.voice_manager.process_voice_input_sync("Show my system status.")

        # 1. Verify router was invoked
        self.assertIn("CPU is 12%", response)

        # 2. Verify TTS received the response text
        self.assertTrue(len(self.mock_tts.spoken_texts) > 0)
        self.assertIn("CPU is 12%", self.mock_tts.spoken_texts[0])

        # Verify state transitions occurred
        self.assertIn("PROCESSING", self.state_transitions)
        self.assertIn("RESPONDING", self.state_transitions)
        self.assertIn("SPEAKING", self.state_transitions)
        self.assertEqual(self.voice_manager.state, VoiceState.SPEAKING)

    def test_push_to_talk(self):
        """Verify push-to-talk trigger transcribes and executes."""
        self.mock_stt.sample_text = "Summarize my metrics."
        res = self.voice_manager.trigger_push_to_talk()

        self.assertEqual(res, "Summarize my metrics.")
        self.assertTrue(self.mock_stt.transcribed)
        self.assertIn("LISTENING", self.state_transitions)

    def test_interruption_and_cancellation(self):
        """Verify speech interruption and cancellation."""
        self.voice_manager.interrupt_speech()
        self.assertTrue(self.mock_tts.stopped)
        self.assertEqual(self.voice_manager.state, VoiceState.IDLE)

        self.voice_manager.cancel()
        self.assertTrue(self.mock_stt.cancelled)
        self.assertTrue(self.mock_tts.stopped)

    def test_tts_configuration(self):
        """Verify voice and speed configuration on TTS provider."""
        self.mock_tts.set_voice("David")
        self.mock_tts.set_speed(190)

        self.assertEqual(self.mock_tts.current_voice, "David")
        self.assertEqual(self.mock_tts.current_speed, 190)

    def test_error_state_recovery(self):
        """Verify error state is handled cleanly without crashing."""
        # Force router to fail
        async def failing_exec(user_input):
            raise RuntimeError("Database connection timed out")
        self.mock_router.execute = failing_exec

        res = self.voice_manager.process_voice_input_sync("Invalid command")
        self.assertIsNone(res)
        self.assertIn("ERROR", self.state_transitions)
        self.assertEqual(self.voice_manager.state, VoiceState.IDLE)


if __name__ == "__main__":
    unittest.main()
