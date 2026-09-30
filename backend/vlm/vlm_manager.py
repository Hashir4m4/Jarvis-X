import logging
from .vlm_client import VLMClient
from .image_utils import ImageUtils

logger = logging.getLogger(__name__)

class VLMManager:
    """Orchestrates image capture and Vision Language Model interactions."""

    def __init__(self, config: dict):
        self.client = VLMClient(config)
        self.max_size = tuple(config.get("vlm", {}).get("max_image_size", [800, 800]))
        self.camera_index = config.get("vision", {}).get("camera_index", 0)

    def ask_about_webcam(self, prompt: str = "Describe what you see in this image in detail.") -> str:
        """Captures a frame from the webcam and asks the VLM about it."""
        logger.info("Capturing webcam image for VLM...")
        image = ImageUtils.capture_webcam(self.camera_index)
        if not image:
            return "Error: Could not capture image from webcam."
        
        return self._process_image(image, prompt)

    def ask_about_screenshot(self, prompt: str = "Describe what is on my screen right now.") -> str:
        """Captures a screenshot and asks the VLM about it."""
        logger.info("Capturing screenshot for VLM...")
        image = ImageUtils.capture_screenshot()
        if not image:
            return "Error: Could not capture screenshot."
        
        return self._process_image(image, prompt)

    def ask_about_file(self, filepath: str, prompt: str = "Analyze this image.") -> str:
        """Loads an image from a file and asks the VLM about it."""
        logger.info(f"Loading image from file for VLM: {filepath}")
        image = ImageUtils.load_from_file(filepath)
        if not image:
            return f"Error: Could not load image from {filepath}"
        
        return self._process_image(image, prompt)

    def _process_image(self, image, prompt: str) -> str:
        """Resizes, encodes, and sends the image to the VLM."""
        image = ImageUtils.resize_image(image, self.max_size)
        b64_image = ImageUtils.to_base64(image)
        
        if not b64_image:
            return "Error: Failed to process image data."
            
        logger.info(f"Sending prompt to VLM: '{prompt}'")
        return self.client.ask(prompt, b64_image)
