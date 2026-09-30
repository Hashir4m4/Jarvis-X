import logging
import cv2
import numpy as np

try:
    import mediapipe as mp
except ImportError:
    mp = None

logger = logging.getLogger(__name__)

class HandTracker:
    def __init__(self, config: dict):
        self.enabled = config.get("enable_hand_tracking", True)
        self.hands = None
        self.mp_draw = None
        
        if self.enabled:
            if mp:
                logger.info("Initializing MediaPipe Hand Tracker")
                self.mp_hands = mp.solutions.hands
                self.hands = self.mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=2,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
                self.mp_draw = mp.solutions.drawing_utils
            else:
                logger.warning("mediapipe package not found. Hand tracking disabled.")

    def track(self, frame: np.ndarray) -> np.ndarray:
        if not self.hands or not self.enabled:
            return frame

        try:
            # Convert the BGR image to RGB before processing
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.hands.process(rgb_frame)

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    self.mp_draw.draw_landmarks(
                        frame, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
            
            return frame
        except Exception as e:
            logger.error(f"Error during hand tracking: {e}")
            return frame
