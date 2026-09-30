import unittest
import sys
import os
import io
from PIL import Image
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock dependencies that might not be installed or need hardware
sys.modules['cv2'] = MagicMock()
sys.modules['pyautogui'] = MagicMock()
import requests

from backend.vlm.image_utils import ImageUtils
from backend.vlm.vlm_client import VLMClient
from backend.vlm.vlm_manager import VLMManager

class TestImageUtils(unittest.TestCase):
    def setUp(self):
        # Create a dummy image
        self.dummy_img = Image.new('RGB', (1000, 1000), color='red')
        
    def test_resize_image(self):
        resized = ImageUtils.resize_image(self.dummy_img.copy(), (500, 500))
        self.assertEqual(resized.size, (500, 500))
        
    def test_to_base64(self):
        b64 = ImageUtils.to_base64(self.dummy_img)
        self.assertTrue(isinstance(b64, str))
        self.assertTrue(len(b64) > 0)
        
    @patch('backend.vlm.image_utils.Image.open')
    def test_load_from_file(self, mock_open):
        mock_open.return_value.convert.return_value = self.dummy_img
        img = ImageUtils.load_from_file("dummy.jpg")
        self.assertIsNotNone(img)

class TestVLMClient(unittest.TestCase):
    def setUp(self):
        self.config = {"vlm": {"model": "test_model", "host": "http://test"}}
        self.client = VLMClient(self.config)
        
    @patch('requests.post')
    def test_ask_success(self, mock_post):
        # Mock successful JSON response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "I see a red square"}
        mock_resp.raise_for_status.return_value = None
        mock_post.return_value = mock_resp
        
        resp = self.client.ask("What is this?", "dummy_b64")
        self.assertEqual(resp, "I see a red square")
        
    @patch('requests.post')
    def test_ask_failure(self, mock_post):
        # Mock connection error
        mock_post.side_effect = requests.exceptions.ConnectionError()
        resp = self.client.ask("What is this?", "dummy_b64")
        self.assertIn("Error", resp)

class TestVLMManager(unittest.TestCase):
    def setUp(self):
        self.config = {"vlm": {"model": "test_model"}}
        self.manager = VLMManager(self.config)
        self.dummy_img = Image.new('RGB', (100, 100), color='blue')
        
    @patch('backend.vlm.vlm_manager.ImageUtils.capture_screenshot')
    @patch('backend.vlm.vlm_manager.VLMClient.ask')
    def test_ask_about_screenshot(self, mock_ask, mock_capture):
        mock_capture.return_value = self.dummy_img
        mock_ask.return_value = "A blue screen"
        
        resp = self.manager.ask_about_screenshot()
        self.assertEqual(resp, "A blue screen")

if __name__ == "__main__":
    unittest.main()
