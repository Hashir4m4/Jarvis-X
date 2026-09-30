import logging
from typing import Dict, Any
from .security import BrowserSecurity

logger = logging.getLogger("JARVIS.BrowserNavigation")

class BrowserNavigation:
    """
    Handles URL validation, SSRF prevention, and URL canonicalization.
    """

    @classmethod
    def validate_and_format_url(cls, url: str) -> Dict[str, Any]:
        """Ensures the URL is valid and safe to navigate."""
        url = url.strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            url = "https://" + url

        is_safe, reason = BrowserSecurity.validate_url(url)
        if not is_safe:
            logger.warning(f"Navigation blocked to {url}: {reason}")
            return {"success": False, "url": url, "error": reason}

        return {"success": True, "url": url}
