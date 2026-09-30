import logging
import cv2
import time
import threading

from .detectors.object_detector import ObjectDetector
from .detectors.barcode_detector import BarcodeDetector
from .tracking.hand_tracker import HandTracker
from .tracking.face_detector import FaceDetector
from .ocr.text_reader import TextReader

logger = logging.getLogger(__name__)

class VisionManager:
    def __init__(self, config: dict):
        self.config = config.get("vision", {})
        self.camera_index = self.config.get("camera_index", 0)
        self.target_fps = self.config.get("target_fps", 15)
        self.is_running = False
        
        # Initialize modules
        self.object_detector = ObjectDetector(self.config)
        self.barcode_detector = BarcodeDetector(self.config)
        self.hand_tracker = HandTracker(self.config)
        self.face_detector = FaceDetector(self.config)
        self.text_reader = TextReader(self.config)
        
        self.capture = None
        self.thread = None

    def start(self):
        if self.is_running:
            return
            
        self.is_running = True
        self.capture = cv2.VideoCapture(self.camera_index)
        if not self.capture.isOpened():
            logger.error(f"Failed to open camera index {self.camera_index}")
            self.is_running = False
            return
            
        logger.info("Vision Manager started. Webcam is active.")
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()

    def _process_loop(self):
        frame_time = 1.0 / self.target_fps
        
        while self.is_running:
            start_time = time.time()
            
            ret, frame = self.capture.read()
            if not ret:
                logger.error("Failed to read from camera.")
                break
            
            # Create a copy so we don't modify the original unpredictably
            annotated_frame = frame.copy()
            
            # Apply pipelines (sequence matters)
            annotated_frame = self.object_detector.detect(annotated_frame)
            annotated_frame = self.hand_tracker.track(annotated_frame)
            annotated_frame = self.face_detector.detect(annotated_frame)
            annotated_frame = self.barcode_detector.detect(annotated_frame)
            annotated_frame = self.text_reader.read_text(annotated_frame)
            
            # Provide an option to view the frame (for debugging/manual verification)
            # In a real background service, we might stream this via WebSocket instead of cv2.imshow
            # But for testing Phase 3, imshow is perfect.
            cv2.imshow('Jarvis Vision AI', annotated_frame)
            
            # Allow quitting the window with 'q'
            if cv2.waitKey(1) & 0xFF == ord('q'):
                self.is_running = False
                break
                
            elapsed = time.time() - start_time
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                
        self._cleanup()

    def _cleanup(self):
        self.is_running = False
        if self.capture:
            self.capture.release()
        cv2.destroyAllWindows()
        logger.info("Vision Manager stopped.")

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=2)
