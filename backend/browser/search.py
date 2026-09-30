import urllib.request
import urllib.parse
import json
import logging
from typing import List, Dict, Any

logger = logging.getLogger("JARVIS.BrowserSearch")

class BrowserSearch:
    """
    Search engine integration. Uses a mock or lightweight public API for search 
    results to ensure source tracking and verifiable results.
    """

    @classmethod
    def search_web(cls, query: str, limit: int = 3) -> Dict[str, Any]:
        """Performs a web search for the given query."""
        try:
            # We mock the actual live DuckDuckGo or Google search since we 
            # might not have an API key. 
            # In a real environment, this would hit Serper / DuckDuckGo Lite.
            # We will use Wikipedia API as a safe proxy for search to avoid CAPTCHAs.
            
            safe_query = urllib.parse.quote(query)
            url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={safe_query}&utf8=&format=json"
            
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0) JARVIS-X'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            results = []
            for item in data.get("query", {}).get("search", [])[:limit]:
                # Extract snippet without HTML tags
                import re
                snippet = re.sub(r'<[^>]+>', '', item.get("snippet", ""))
                title = item.get("title", "")
                page_url = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title)}"
                
                results.append({
                    "title": title,
                    "url": page_url,
                    "snippet": snippet,
                    "source": "Wikipedia"
                })
                
            if not results:
                return {"success": True, "results": [], "query": query}
                
            return {"success": True, "results": results, "query": query}
            
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return {"success": False, "error": str(e), "query": query}
