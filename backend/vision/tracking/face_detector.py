import logging
import cv2
import numpy as np

try:
    import mediapipe as mp
except ImportError:
    mp = None

logger = logging.getLogger(__name__)

class FaceDetector:
    def __init__(self, config: dict):
        self.enabled = config.get("enable_face_detection", True)
        self.face_detection = None
        self.mp_draw = None
        
        if self.enabled:
            if mp:
                logger.info("Initializing MediaPipe Face Detector")
                self.mp_face = mp.solutions.face_detection
                self.face_detection = self.mp_face.FaceDetection(
                    model_selection=0, min_detection_confidence=0.5
                )
                self.mp_draw = mp.solutions.drawing_utils
            else:
                logger.warning("mediapipe package not found. Face detection disabled.")

    def detect(self, frame: np.ndarray) -> np.ndarray:
        if not self.face_detection or not self.enabled:
            return frame

        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_detection.process(rgb_frame)

            if results.detections:
                for detection in results.detections:
                    self.mp_draw.draw_detection(frame, detection)
            
            return frame
        except Exception as e:
            logger.error(f"Error during face detection: {e}")
            return frame
