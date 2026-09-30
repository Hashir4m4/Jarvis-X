import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy ML and audio libraries before importing our modules
sys.modules['openwakeword'] = MagicMock()
sys.modules['openwakeword.model'] = MagicMock()
sys.modules['pyaudio'] = MagicMock()
sys.modules['faster_whisper'] = MagicMock()
sys.modules['pyttsx3'] = MagicMock()
sys.modules['speech_recognition'] = MagicMock()

from backend.voice.voice_manager import VoiceManager
from backend.voice.interfaces import VoiceMode
from backend.brain import Brain


class TestVoiceManager(unittest.TestCase):
    def setUp(self):
        self.config = {
            "voice": {
                "wake_word": "jarvis",
                "tts_engine": "mock",
                "stt_engine": "mock"
            },
            "llm": {
                "provider": "test"
            },
            "memory": {}
        }

        self.mock_brain = MagicMock()
        self.mock_brain.chat_sync.return_value = "It is test time."

        self.voice_manager = VoiceManager(self.config, self.mock_brain)

    def test_wake_word_trigger(self):
        self.voice_manager._is_active = True
        self.voice_manager.mode = VoiceMode.MANUAL
        self.voice_manager.stt.listen_and_transcribe = MagicMock(return_value="What time is it?")
        self.voice_manager.tts.speak = MagicMock()

        # Trigger voice cycle
        self.voice_manager._run_voice_cycle()

        # Assertions
        self.voice_manager.stt.listen_and_transcribe.assert_called()


if __name__ == "__main__":
    unittest.main()
