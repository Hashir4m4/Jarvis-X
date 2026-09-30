import logging
import cv2
import numpy as np

try:
    from pyzbar import pyzbar
except ImportError:
    pyzbar = None

logger = logging.getLogger(__name__)

class BarcodeDetector:
    def __init__(self, config: dict):
        self.enabled = config.get("enable_barcode", True)
        if self.enabled and not pyzbar:
            logger.warning("pyzbar package not found. Barcode detection disabled.")

    def detect(self, frame: np.ndarray) -> np.ndarray:
        if not pyzbar or not self.enabled:
            return frame

        try:
            barcodes = pyzbar.decode(frame)
            for barcode in barcodes:
                (x, y, w, h) = barcode.rect
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                
                barcode_data = barcode.data.decode("utf-8")
                barcode_type = barcode.type
                text = f"{barcode_data} ({barcode_type})"
                
                cv2.putText(frame, text, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            return frame
        except Exception as e:
            logger.error(f"Error during barcode detection: {e}")
            return frame
