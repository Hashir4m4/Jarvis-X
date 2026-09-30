import logging
import cv2
import numpy as np

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

logger = logging.getLogger(__name__)

class ObjectDetector:
    def __init__(self, config: dict):
        self.model_name = config.get("yolo_model", "yolo11n.pt")
        self.enabled = config.get("enable_object_detection", True)
        self.model = None
        
        if self.enabled:
            if YOLO:
                logger.info(f"Loading YOLO model: {self.model_name}")
                try:
                    # device="cuda" will use GPU if PyTorch is configured for it
                    self.model = YOLO(self.model_name)
                except Exception as e:
                    logger.error(f"Failed to load YOLO model: {e}")
            else:
                logger.warning("ultralytics package not found. Object detection disabled.")

    def detect(self, frame: np.ndarray) -> np.ndarray:
        if not self.model or not self.enabled:
            return frame

        try:
            results = self.model(frame, verbose=False)
            
            # The 'plot' method draws bounding boxes and labels on the image
            annotated_frame = results[0].plot()
            return annotated_frame
        except Exception as e:
            logger.error(f"Error during object detection: {e}")
            return frame
