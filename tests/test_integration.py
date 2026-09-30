import unittest
import sys
import os
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock dependencies
sys.modules['chromadb'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
sys.modules['psutil'] = MagicMock()
sys.modules['cv2'] = MagicMock()

from backend.brain import Brain
from backend.plugins.plugin_manager import PluginManager

class TestJarvisOSIntegration(unittest.TestCase):
    def setUp(self):
        self.config = {
            "llm": {
                "provider": "ollama",
                "model": "qwen"
            },
            "memory": {
                "db_path": ":memory:" # Use in-memory SQLite for tests
            }
        }
        
    @patch('backend.brain.LLMClient')
    def test_end_to_end_plugin_call(self, MockLLMClient):
        # Mock the LLM to output a plugin tool call
        mock_llm_instance = MockLLMClient.return_value
        mock_llm_instance.chat_stream.return_value = ["[TOOL] hello_greet"]
        
        # Instantiate Brain (this auto-loads the real hello_world plugin)
        brain = Brain(self.config)
        
        # Run chat stream
        output = ""
        for chunk in brain.chat_stream("Say hello"):
            output += chunk
            
        # The Brain should have parsed [TOOL] hello_greet, executed via the real plugin
        self.assertIn("Tool Result", output)
        self.assertIn("Greetings from the Hello World Plugin", output)

if __name__ == "__main__":
    unittest.main()
