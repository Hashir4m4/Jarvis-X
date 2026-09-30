import re

with open('backend/browser/reader.py', 'r', encoding='utf-8') as f:
    code = f.read()

new_parser_code = '''class CleanHTMLParser(HTMLParser):
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
            self.text_content.append('\\n')
        elif tag == 'a':
            href = next((v for k, v in attrs if k == 'href'), None)
            if href:
                self.links.append({"href": href, "text": ""})
        elif tag in ('button', 'input', 'select', 'textarea'):
            el_type = next((v for k, v in attrs if k == 'type'), tag)
            self.elements.append({"type": el_type if tag == 'input' else tag, "text": "", "selector": tag, "visible": True})
        elif tag in ('p', 'br', 'div', 'li'):
            self.text_content.append('\\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'meta', 'head', 'link'):
            self.in_script_or_style = False
        elif tag == 'title':
            self.in_title = False
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.in_heading = False
            if self.current_heading.strip():
                self.headings.append(self.current_heading.strip())
            self.text_content.append('\\n')
        elif tag in ('p', 'div', 'li'):
            self.text_content.append('\\n')

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
        lines = [line.strip() for line in raw_text.split('\\n') if line.strip()]
        return "\\n".join(lines)'''

# Using regex to replace the class content
code = re.sub(r'class CleanHTMLParser\(HTMLParser\):.*?def get_clean_text\(self\) -> str:.*?return "\\n"\.join\(lines\)', new_parser_code, code, flags=re.DOTALL)

with open('backend/browser/reader.py', 'w', encoding='utf-8') as f:
    f.write(code)

