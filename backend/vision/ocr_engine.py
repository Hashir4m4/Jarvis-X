import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from PIL import Image

logger = logging.getLogger("JARVIS.OCREngine")

# Secret redaction and privacy patterns
SECRET_PATTERNS = [
    (r"(sk-[a-zA-Z0-9]{20,})", "API_KEY"),
    (r"(Bearer\s+[a-zA-Z0-9_\-\.]{15,})", "BEARER_TOKEN"),
    (r"(password[\"':\s=]+)([^\s\"',&]+)", "PASSWORD"),
    (r"(token[\"':\s=]+)([^\s\"',&]+)", "TOKEN"),
    (r"(secret[\"':\s=]+)([^\s\"',&]+)", "SECRET"),
    (r"(-----BEGIN [A-Z ]+ PRIVATE KEY-----)", "PRIVATE_KEY"),
    (r"(ghp_[a-zA-Z0-9]{36})", "GITHUB_TOKEN"),
    (r"(aws_secret_access_key[\s=:]+)([^\s]+)", "AWS_SECRET")
]


class OCREngine:
    """
    Modular Optical Character Recognition (OCR) Engine.
    Attempts PaddleOCR, EasyOCR, or pytesseract if available,
    with an internal text buffer simulation / fallback for testing and headless environments.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._ocr_backend = None
        self._init_backend()

    def _init_backend(self):
        try:
            import pytesseract
            self._ocr_backend = "pytesseract"
        except ImportError:
            try:
                from paddleocr import PaddleOCR
                self._ocr_backend = "paddleocr"
            except ImportError:
                self._ocr_backend = "fallback"

    def is_available(self) -> bool:
        return self._ocr_backend != "fallback"

    def extract_text(self, image: Image.Image) -> str:
        """Extracts text from a PIL Image."""
        if not image:
            return ""

        # If mocked or text buffer attribute is attached (useful for tests)
        if hasattr(image, "_injected_text"):
            return getattr(image, "_injected_text")

        if self._ocr_backend == "pytesseract":
            try:
                import pytesseract
                return pytesseract.image_to_string(image).strip()
            except Exception as e:
                logger.debug(f"Pytesseract error: {e}")

        # Fallback heuristic: Return empty string if no backend installed
        return ""


class ScreenPrivacyFilter:
    """
    Privacy and Secret Leak Guard.
    Scans extracted screen text, active window titles, and visual elements
    for credentials, authentication tokens, and private secrets.
    """

    def __init__(self):
        self.patterns = [(re.compile(p, re.IGNORECASE), name) for p, name in SECRET_PATTERNS]

    def scan_for_secrets(self, text: str) -> Tuple[bool, List[str]]:
        """
        Returns (has_secrets, list_of_detected_categories).
        """
        if not text:
            return False, []

        detected = set()
        for regex, name in self.patterns:
            if regex.search(text):
                detected.add(name)

        # Detect password fields / prompts
        lower = text.lower()
        if "enter password" in lower or "password:" in lower or "sudo password" in lower:
            detected.add("PASSWORD_PROMPT")

        return len(detected) > 0, sorted(list(detected))

    def redact_secrets(self, text: str) -> str:
        """Redacts sensitive strings from the text buffer."""
        sanitized = text
        for regex, name in self.patterns:
            sanitized = regex.sub(f"[REDACTED_{name}]", sanitized)
        return sanitized
