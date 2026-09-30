import time
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("JARVIS.BrowserSession")

class BrowserSession:
    """
    Maintains active tabs, history, and state for a browsing session.
    Cookies are explicitly NOT exposed to the LLM to prevent exfiltration.
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.current_url: Optional[str] = None
        self.history: List[str] = []
        self.history_index: int = -1
        self.created_at = time.time()
        self.last_active = time.time()
        self.state = "SESSION_CREATED"  # SESSION_CREATED, SESSION_ACTIVE, SESSION_IDLE, SESSION_CLOSED
        
    def navigate(self, url: str):
        """Records navigation history."""
        self.current_url = url
        # Truncate forward history if we navigated to a new page
        if self.history_index < len(self.history) - 1:
            self.history = self.history[:self.history_index + 1]
            
        self.history.append(url)
        self.history_index += 1
        self.last_active = time.time()
        self.state = "SESSION_ACTIVE"

    def go_back(self) -> Optional[str]:
        if self.history_index > 0:
            self.history_index -= 1
            self.current_url = self.history[self.history_index]
            self.last_active = time.time()
            return self.current_url
        return None

    def go_forward(self) -> Optional[str]:
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.current_url = self.history[self.history_index]
            self.last_active = time.time()
            return self.current_url
        return None

    def close(self):
        self.state = "SESSION_CLOSED"
        self.current_url = None
        self.last_active = time.time()
        logger.info(f"Browser Session {self.session_id} closed.")

    def update_idle_state(self, timeout_seconds: float = 300):
        if self.state == "SESSION_ACTIVE" and (time.time() - self.last_active) > timeout_seconds:
            self.state = "SESSION_IDLE"
