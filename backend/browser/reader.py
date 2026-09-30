import re
import urllib.request
import urllib.error
import logging
from html.parser import HTMLParser
from typing import Optional, Dict, Any

logger = logging.getLogger("JARVIS.BrowserReader")

class CleanHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text_content = []
        self.in_script_or_style = False
        self.title = ""
        self.in_title = False
        self.headings = []
        self.current_heading = ""
        self.in_heading = False
        self.links = []
        self.elements = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'meta', 'head', 'link'):
            self.in_script_or_style = True
        elif tag == 'title':
            self.in_title = True
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.in_heading = True
            self.current_heading = ""
            self.text_content.append('\n')
        elif tag == 'a':
            href = next((v for k, v in attrs if k == 'href'), None)
            if href:
                self.links.append({"href": href, "text": ""})
        elif tag in ('button', 'input', 'select', 'textarea'):
            el_type = next((v for k, v in attrs if k == 'type'), tag)
            self.elements.append({"type": el_type if tag == 'input' else tag, "text": "", "selector": tag, "visible": True})
        elif tag in ('p', 'br', 'div', 'li'):
            self.text_content.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'meta', 'head', 'link'):
            self.in_script_or_style = False
        elif tag == 'title':
            self.in_title = False
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.in_heading = False
            if self.current_heading.strip():
                self.headings.append(self.current_heading.strip())
            self.text_content.append('\n')
        elif tag in ('p', 'div', 'li'):
            self.text_content.append('\n')

    def handle_data(self, data):
        if not self.in_script_or_style:
            text = data.strip()
            if text:
                self.text_content.append(text + ' ')
        if self.in_title:
            self.title += data
        if self.in_heading:
            self.current_heading += data
        if self.links and getattr(self, 'lasttag', None) == 'a':
            self.links[-1]['text'] += data.strip()
        if self.elements and getattr(self, 'lasttag', None) in ('button', 'label'):
            self.elements[-1]['text'] += data.strip()

    def get_clean_text(self) -> str:
        raw_text = "".join(self.text_content)
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        return "\n".join(lines)


class BrowserReader:
    """
    Reads and extracts text from webpages cleanly without ads, 
    menus (where possible), or scripts.
    """

    @classmethod
    def read_page(cls, url: str) -> Dict[str, Any]:
        """Fetches URL and returns cleaned text and metadata."""
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 JARVIS-X-Browser'}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' not in content_type.lower() and 'text/plain' not in content_type.lower():
                    return {"success": False, "error": f"Unsupported content type: {content_type}"}

                html_bytes = response.read()
                # Basic decode
                try:
                    html_str = html_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    html_str = html_bytes.decode('latin-1')

                parser = CleanHTMLParser()
                parser.feed(html_str)
                clean_text = parser.get_clean_text()

                content_truncated = len(clean_text) > 20000

                return {
                    "success": True,
                    "url": url,
                    "title": parser.title.strip(),
                    "content": clean_text[:20000],
                    "content_truncated": content_truncated,
                    "headings": parser.headings[:20],
                    "links": parser.links[:50],
                    "elements": parser.elements[:50],
                    "source": url
                }
        except urllib.error.URLError as e:
            return {"success": False, "error": f"Failed to load page: {e.reason}"}
        except Exception as e:
            logger.error(f"Error reading page {url}: {e}")
            return {"success": False, "error": f"Extraction error: {str(e)}"}
