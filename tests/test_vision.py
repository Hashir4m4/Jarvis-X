import unittest
import sys
import os
import numpy as np
from unittest.mock import MagicMock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock heavy ML and vision libraries
sys.modules['cv2'] = MagicMock()
sys.modules['ultralytics'] = MagicMock()
sys.modules['mediapipe'] = MagicMock()
sys.modules['paddleocr'] = MagicMock()
sys.modules['pyzbar'] = MagicMock()
sys.modules['pyzbar.pyzbar'] = MagicMock()

from backend.vision.vision_manager import VisionManager

class TestVisionManager(unittest.TestCase):
    def setUp(self):
        self.config = {
            "vision": {
                "camera_index": 0,
                "target_fps": 30,
                "enable_object_detection": True,
                "enable_face_detection": True,
                "enable_hand_tracking": True,
                "enable_ocr": True,
                "enable_barcode": True,
                "yolo_model": "yolo11n.pt"
            }
        }
        self.vision_manager = VisionManager(self.config)
        # Mock capture
        self.vision_manager.capture = MagicMock()
        self.vision_manager.capture.isOpened.return_value = True
        
        # Create a dummy frame (e.g., 100x100 RGB image)
        self.dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)

    @patch('backend.vision.vision_manager.cv2')
    def test_processing_pipeline(self, mock_cv2):
        self.vision_manager.capture.read.return_value = (True, self.dummy_frame)
        
        # We manually call _process_loop for one iteration to test
        # We mock cv2.waitKey to return ord('q') so it breaks immediately
        mock_cv2.waitKey.return_value = ord('q')
        
        # Call process loop directly
        self.vision_manager.is_running = True
        self.vision_manager._process_loop()
        
        # Assertions to ensure it broke out and read from camera
        self.vision_manager.capture.read.assert_called_once()
        self.assertFalse(self.vision_manager.is_running)

if __name__ == "__main__":
    unittest.main()
