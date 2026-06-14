import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from .skill import Skill
from utils.html_parser import _HTMLTextExtractor

class WebSkill(Skill):
    """Web research skill - search and read web pages."""

    @property
    def name(self) -> str:
        return "WebSkill"

    @property
    def description(self) -> str:
        return "Searches the web and read web pages"
    
    def get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web using DuckDuckGo. Returns top 5 results with titles and snippets.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"}
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "web_read_page",
                    "description": "Read and extract the text content of a web page. Returns up to 4000 characters.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to read"}
                        },
                        "required": ["url"]
                    }
                }
            },
        ]

    def execute(self, tool_name: str, args: dict) -> str:
        print("execute tool name:", tool_name, "args:", args)
        if tool_name == "web_search":
            return self._search(args["query"])
        elif tool_name == "web_read_page":
            return self._read_page(args["url"])
        raise ValueError(f"Unknown tool: {tool_name}")
    
    def _search(self, query: str) -> str:
        print("came to search")
        """Search DuckDuckGo and return top results as text."""
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Atlas Agent)"})
            with urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            # Extract result snippets
            results = []
            for match in re.finditer(
                r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'<a class="result__snippet"[^>]*>(.*?)</a>',
                html, re.DOTALL
            ):
                href, title, snippet = match.groups()
                title = re.sub(r"<[^>]+>", "", title).strip()
                snippet = re.sub(r"<[^>]+>", "", snippet).strip()
                if title:
                    results.append(f"- [{title}]({href})\n  {snippet}")
                if len(results) >= 5:
                    break

            if not results:
                return "No results found."
            return f"Search results for '{query}':\n\n" + "\n\n".join(results)
        except Exception as e:
            return f"Search failed: {e}"
    
    def _read_page(self, url: str) -> str:
        """Read a web page and return its text content (truncated to 3000 chars)."""
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Atlas Agent)"})
            with urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            extractor = _HTMLTextExtractor()
            extractor.feed(html)
            text = extractor.get_text()

            # Truncate to avoid context window overflow
            if len(text) > 3000:
                text = text[:3000] + "\n\n[...truncated]"
            return text if text else "Could not extract text from this page."
        except Exception as e:
            return f"Failed to read URL: {e}"

