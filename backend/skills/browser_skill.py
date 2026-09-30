import logging
from typing import Dict, Any, List

from .base_skill import BaseSkill, SkillResult
from ..core.models import Intent
from ..automation.security_proxy import SecurityProxy
from ..browser.manager import BrowserManager
from ..browser.security import BrowserSecurity

logger = logging.getLogger("JARVIS.BrowserSkill")

class BrowserSkill(BaseSkill):
    """
    Skill layer for Browser Intelligence (Prompt 50).
    Routes browser intents safely, enforcing confirmations via SecurityProxy.
    """

    def __init__(self, security_proxy: SecurityProxy = None, browser_manager: BrowserManager = None, metadata=None):
        super().__init__(metadata=metadata)
        self.security_proxy = security_proxy or SecurityProxy()
        self.browser_manager = browser_manager or BrowserManager()
        
        # We hook into the action queue or HUD logic by using a callback
        self.browser_manager.set_state_callback(self._notify_browser_state)

    def _notify_browser_state(self, state: str):
        # In a real setup, this goes to WebSocket. We'll use logger for now.
        logger.info(f"BROWSER_STATE: {state}")
        # Note: server.py handles these logs if intercepted by telemetry

    @property
    def name(self) -> str:
        return "browser"

    @property
    def description(self) -> str:
        return "Provides web intelligence, reading, searching, and safe browser interactions."

    @property
    def supported_actions(self) -> List[str]:
        return ["search", "read_page", "open_url", "interact"]

    def can_handle(self, intent: Intent) -> bool:
        if intent.skill_name == self.name or intent.action in self.supported_actions:
            return True
        raw = intent.raw_input.lower()
        if any(w in raw for w in ["search for", "read this webpage", "open github", "open website", "summarize this webpage", "cheapest option"]):
            return True
        return False

    def execute(self, intent: Intent) -> SkillResult:
        action = intent.action
        params = intent.parameters
        raw_input = intent.raw_input.lower()
        
        # Determine implicit actions if not neatly parsed
        if not action or action == "unknown":
            if "search" in raw_input:
                action = "search"
            elif "read" in raw_input or "summarize" in raw_input:
                action = "read_page"
            elif "open" in raw_input:
                action = "open_url"
            else:
                action = "search"

        try:
            if action == "search":
                query = params.get("query")
                if not query:
                    # Extract query from raw input loosely
                    query = intent.raw_input.replace("search for", "").replace("search", "").strip()
                if not query:
                    return SkillResult(success=False, message="Please specify what you want to search for.")
                    
                result = self.browser_manager.search_web(session_id="default", query=query)
                if not result["success"]:
                    return SkillResult(success=False, message=result.get("error", "Search failed."))
                    
                # Format snippet
                output_text = "I searched the web.\n"
                for i, r in enumerate(result.get("results", [])):
                    output_text += f"{i+1}. Source: {r['source']} - {r['title']}\n   {r['snippet']}\n"
                    
                return SkillResult(
                    success=True,
                    data=result,
                    message=f"Found {len(result.get('results', []))} results.",
                    output_text=output_text
                )

            elif action == "read_page" or action == "open_url":
                url = params.get("url")
                if not url:
                    # Fallback naive extraction
                    parts = intent.raw_input.split()
                    for p in parts:
                        if p.startswith("http") or "." in p:
                            url = p
                            break
                            
                if not url:
                    return SkillResult(success=False, message="No URL provided.")

                result = self.browser_manager.read_page(session_id="default", url=url)
                if not result["success"]:
                    return SkillResult(success=False, message=result.get("error", "Page read failed."))

                message = "I opened the website." if action == "open_url" else "I read the webpage."
                
                return SkillResult(
                    success=True,
                    data=result,
                    message=message,
                    output_text=f"{message}\nContent extracted securely."
                )

            elif action == "interact":
                interaction_type = params.get("type", "submit_form")
                target = params.get("target", "unknown")
                data = params.get("data", "")
                
                # We map this to security proxy explicitly
                perm_action = f"browser_{interaction_type}"
                
                # Check via security proxy to force confirmation
                details = f"Browser interaction '{interaction_type}' on target '{target}'."
                proxy_result = self.security_proxy.execute(perm_action, details, self.browser_manager.interact, "default", interaction_type, target, data)
                
                if isinstance(proxy_result, dict) and proxy_result.get("status") in ["denied", "blocked"]:
                    return SkillResult(
                        success=False,
                        message=proxy_result.get("message", "Action blocked."),
                        output_text=proxy_result.get("message", "Action blocked.")
                    )
                    
                return SkillResult(
                    success=True,
                    data=proxy_result,
                    message=f"I {interaction_type}ed the {target}.",
                    output_text=f"Action '{interaction_type}' succeeded."
                )
                
            else:
                return SkillResult(success=False, message=f"Unsupported browser action: {action}")
                
        except Exception as e:
            logger.error(f"Browser skill failed: {e}")
            self.browser_manager._emit("BROWSER: ERROR")
            self.browser_manager._emit("BROWSER: IDLE")
            return SkillResult(success=False, message=str(e))
