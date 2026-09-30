import logging
import requests
import json
from typing import Optional

logger = logging.getLogger(__name__)

class VLMClient:
    """Client for interacting with Vision Language Models via Ollama."""

    def __init__(self, config: dict):
        vlm_config = config.get("vlm", {})
        self.model = vlm_config.get("model", "moondream")
        self.host = vlm_config.get("host", "http://localhost:11434")
        self.generate_endpoint = f"{self.host}/api/generate"

    def ask(self, prompt: str, image_b64: str) -> Optional[str]:
        """
        Sends a prompt and a base64 encoded image to the VLM.
        Returns the text response.
        """
        if not image_b64:
            logger.error("No image data provided to VLM.")
            return "Error: No image data provided."

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "images": [image_b64]
        }

        try:
            logger.info(f"Sending request to VLM model: {self.model}")
            response = requests.post(self.generate_endpoint, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            return data.get("response", "").strip()
        except requests.exceptions.RequestException as e:
            logger.error(f"VLM API request failed: {e}")
            return f"Error: Failed to connect to VLM ({self.model}). Is Ollama running?"
        except json.JSONDecodeError:
            logger.error("Failed to parse VLM API response as JSON.")
            return "Error: Invalid response from VLM."
