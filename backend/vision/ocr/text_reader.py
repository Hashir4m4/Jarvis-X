import logging
import cv2
import numpy as np

try:
    from paddleocr import PaddleOCR
except ImportError:
    PaddleOCR = None

logger = logging.getLogger(__name__)

class TextReader:
    def __init__(self, config: dict):
        self.enabled = config.get("enable_ocr", True)
        self.ocr = None
        
        if self.enabled:
            if PaddleOCR:
                logger.info("Initializing PaddleOCR...")
                try:
                    # use_angle_cls=True allows rotated text to be recognized
                    self.ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=True)
                except Exception as e:
                    logger.error(f"Failed to initialize PaddleOCR (GPU might fail if not configured): {e}")
                    try:
                        self.ocr = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False)
                    except Exception as e2:
                        logger.error(f"Failed to initialize PaddleOCR CPU fallback: {e2}")
            else:
                logger.warning("paddleocr package not found. OCR disabled.")

    def read_text(self, frame: np.ndarray) -> np.ndarray:
        if not self.ocr or not self.enabled:
            return frame

        try:
            result = self.ocr.ocr(frame, cls=True)
            if not result or not result[0]:
                return frame
                
            # Draw bounding boxes and text
            for line in result[0]:
                box = line[0]
                text = line[1][0]
                
                # Convert float coords to int
                box = np.array(box).astype(np.int32)
                
                # Draw polygon and text
                cv2.polylines(frame, [box], True, (0, 255, 0), 2)
                cv2.putText(frame, text, (box[0][0], box[0][1] - 10), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
                
            return frame
        except Exception as e:
            logger.error(f"Error during OCR: {e}")
            return frame
