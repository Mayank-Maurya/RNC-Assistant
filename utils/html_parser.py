from html.parser import HTMLParser

class _HTMLTextExtractor(HTMLParser):
    """Simple HTML-to-text converter."""
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data.strip())

    def get_text(self) -> str:
        return "\n".join(line for line in self._text if line)
