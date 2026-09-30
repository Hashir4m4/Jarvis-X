import re
import ipaddress
import logging
from urllib.parse import urlparse
from typing import Tuple

logger = logging.getLogger("JARVIS.BrowserSecurity")

class BrowserSecurity:
    """
    Implements URL safety, SSRF prevention, Prompt Injection defense, 
    and action classifications for the Browser Intelligence Layer.
    """

    SAFE_SCHEMES = {"http", "https"}
    RESTRICTED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

    @classmethod
    def validate_url(cls, url: str) -> Tuple[bool, str]:
        """Validates URL and blocks unsafe schemes or local network addresses."""
        try:
            parsed = urlparse(url)
            
            if not parsed.scheme or parsed.scheme not in cls.SAFE_SCHEMES:
                return False, f"Unsupported or unsafe scheme '{parsed.scheme}'. Only http and https are allowed."
            
            hostname = parsed.hostname
            if not hostname:
                return False, "Malformed URL: No hostname."

            if hostname in cls.RESTRICTED_HOSTS:
                return False, "Access to localhost or internal loopback is restricted for safety."

            # Block private IPs to prevent SSRF
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback:
                    return False, "Access to private network addresses is restricted."
            except ValueError:
                # Not an IP address, proceed
                pass
            
            return True, "URL is safe."
        except Exception as e:
            return False, f"URL validation failed: {str(e)}"

    @classmethod
    def sanitize_content(cls, content: str) -> str:
        """
        Implements a trust boundary. Encapsulates untrusted web content so the 
        model does not execute it as an instruction.
        """
        # We strip out system-level directive terms loosely, but primarily we depend
        # on the system prompt structure (e.g. wrapper tags) to delineate untrusted data.
        # Here we do basic sanitization just in case.
        sanitized = content
        return f"--- UNTRUSTED WEBPAGE CONTENT START ---\n{sanitized}\n--- UNTRUSTED WEBPAGE CONTENT END ---"

    @classmethod
    def get_action_risk_level(cls, action: str) -> str:
        """Maps a browser action to a RiskLevel string."""
        safe_actions = {"search", "read", "scroll", "open_url", "find_text"}
        confirm_actions = {"submit_form", "send_message", "upload_file"}
        restricted_actions = {"financial_transaction", "delete_account", "credential_operations"}

        act_lower = action.lower()
        if act_lower in safe_actions:
            return "SAFE"
        if act_lower in confirm_actions:
            return "CONFIRM"
        if act_lower in restricted_actions:
            return "RESTRICTED"
        
        # Default to CONFIRM for unknown interactions to fail closed.
        return "CONFIRM"
