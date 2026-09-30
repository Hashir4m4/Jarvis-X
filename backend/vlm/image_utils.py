import base64
import logging
import io

try:
    import cv2
    _CV2 = True
except ImportError:
    _CV2 = False

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

logger = logging.getLogger(__name__)

class ImageUtils:
    @staticmethod
    def capture_webcam(camera_index: int = 0):
        """Captures a single frame from the webcam and returns a PIL Image."""
        if not _CV2 or not _PIL:
            logger.error("OpenCV or PIL not installed for webcam capture")
            return None
        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                logger.error(f"Cannot open webcam {camera_index}")
                return None
            
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                logger.error("Failed to read frame from webcam")
                return None
            
            # Convert BGR (OpenCV) to RGB (PIL)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            return Image.fromarray(rgb_frame)
        except Exception as e:
            logger.error(f"Webcam capture error: {e}")
            return None

    @staticmethod
    def capture_screenshot() -> Image.Image:
        """Captures the current screen."""
        if not _PYAUTOGUI:
            logger.error("pyautogui not installed")
            return None
        try:
            return pyautogui.screenshot()
        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None

    @staticmethod
    def load_from_file(filepath: str) -> Image.Image:
        """Loads an image from a file path."""
        try:
            return Image.open(filepath).convert("RGB")
        except Exception as e:
            logger.error(f"File load error: {e}")
            return None

    @staticmethod
    def to_base64(image: Image.Image, format: str = "JPEG", quality: int = 80) -> str:
        """Converts a PIL Image to a base64 encoded string."""
        if image is None:
            return ""
        try:
            buffered = io.BytesIO()
            # Ensure it's RGB for JPEG
            if image.mode != "RGB":
                image = image.convert("RGB")
            
            image.save(buffered, format=format, quality=quality)
            img_bytes = buffered.getvalue()
            return base64.b64encode(img_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Base64 conversion error: {e}")
            return ""

    @staticmethod
    def resize_image(image: Image.Image, max_size: tuple = (800, 800)) -> Image.Image:
        """Resizes an image maintaining aspect ratio if it exceeds max_size."""
        if image is None:
            return None
        try:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            return image
        except Exception as e:
            logger.error(f"Resize error: {e}")
            return image
