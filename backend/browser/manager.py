import time
import uuid
import logging
from typing import Dict, Any, Optional

from .session import BrowserSession
from .navigation import BrowserNavigation
from .reader import BrowserReader
from .search import BrowserSearch
from .interaction import BrowserInteraction
from .security import BrowserSecurity

logger = logging.getLogger("JARVIS.BrowserManager")

class BrowserManager:
    """
    Core orchestrator for browser intelligence. Manages sessions, handles offline mode,
    enforces URL safety, and collects latency telemetry.
    """
    
    def __init__(self, offline_mode: bool = False):
        self.offline_mode = offline_mode
        self.sessions: Dict[str, BrowserSession] = {}
        self.telemetry = {
            "session_count": 0,
            "errors": 0,
            "total_latency_ms": 0
        }
        self.state_callback = None
        
    def set_state_callback(self, callback):
        """Callback to emit HUD events like BROWSER: SEARCHING"""
        self.state_callback = callback
        
    def _emit(self, state: str):
        if self.state_callback:
            self.state_callback(state)
        else:
            logger.info(f"[{state}]")

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        session = BrowserSession(session_id)
        self.sessions[session_id] = session
        self.telemetry["session_count"] += 1
        self._emit("BROWSER: OPENING")
        self._emit("BROWSER: IDLE")
        return session_id
        
    def get_session(self, session_id: str) -> Optional[BrowserSession]:
        return self.sessions.get(session_id)
        
    def close_session(self, session_id: str):
        session = self.get_session(session_id)
        if session:
            session.close()
            del self.sessions[session_id]
            self._emit("BROWSER: COMPLETE")
            self._emit("BROWSER: IDLE")

    def read_page(self, session_id: str, url: str) -> Dict[str, Any]:
        """Navigates to and reads a webpage securely."""
        if self.offline_mode:
            self._emit("BROWSER: ERROR")
            return {"success": False, "error": "Live web access is unavailable (Offline Mode)."}
            
        start_time = time.time()
        self._emit("BROWSER: OPENING")
        
        session = self.get_session(session_id)
        if not session:
            session_id = self.create_session()
            session = self.get_session(session_id)
            
        # Validation
        nav_result = BrowserNavigation.validate_and_format_url(url)
        if not nav_result["success"]:
            self.telemetry["errors"] += 1
            self._emit("BROWSER: ERROR")
            return nav_result
            
        safe_url = nav_result["url"]
        self._emit("BROWSER: READING")
        
        # Reader extraction
        result = BrowserReader.read_page(safe_url)
        
        latency_ms = int((time.time() - start_time) * 1000)
        self.telemetry["total_latency_ms"] += latency_ms
        
        if result["success"]:
            session.navigate(safe_url)
            # Apply prompt injection defense wrapping to the content
            raw_content = result["content"]
            result["content"] = BrowserSecurity.sanitize_content(raw_content)
            result["latency_ms"] = latency_ms
            self._emit("BROWSER: ANALYZING")
            self._emit("BROWSER: COMPLETE")
        else:
            self.telemetry["errors"] += 1
            self._emit("BROWSER: ERROR")
            
        self._emit("BROWSER: IDLE")
        return result

    def search_web(self, session_id: str, query: str) -> Dict[str, Any]:
        if self.offline_mode:
            self._emit("BROWSER: ERROR")
            return {"success": False, "error": "Live web access is unavailable (Offline Mode)."}
            
        start_time = time.time()
        self._emit("BROWSER: SEARCHING")
        
        result = BrowserSearch.search_web(query)
        
        latency_ms = int((time.time() - start_time) * 1000)
        self.telemetry["total_latency_ms"] += latency_ms
        
        if result["success"]:
            result["latency_ms"] = latency_ms
            self._emit("BROWSER: COMPLETE")
        else:
            self.telemetry["errors"] += 1
            self._emit("BROWSER: ERROR")
            
        self._emit("BROWSER: IDLE")
        return result

    def interact(self, session_id: str, action: str, target: str, data: str = "") -> Dict[str, Any]:
        if self.offline_mode:
            return {"success": False, "error": "Offline mode active."}
            
        # Ensure safe routing. SecurityProxy should have confirmed already if action was RESTRICTED/CONFIRM
        self._emit("BROWSER: EXECUTING")
        res = BrowserInteraction.interact(action, target, data)
        self._emit("BROWSER: COMPLETE")
        self._emit("BROWSER: IDLE")
        return res
