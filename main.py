import json
import sys
from openai import OpenAI
from config import require_key, MODEL
from html.parser import HTMLParser
from urllib.request import urlopen, Request
from urllib.parse import quote_plus
import re

# ----- configs -----
client = OpenAI(
    api_key=require_key("openrouter"),
    base_url=require_key("open_router_url"),
)

# ---- Messages ------ #
SYSTEM_PROMT = """
    You are Atlas, a reserach assistant
    You answer questions by searching the web and reading pages.
    For each step, think carefully about what information you need next.

    RULES:
    1. Always search before answering- don't reply on your trainining data alone.
    2. Read at leats one source to verify the answer
    3. Use at most 5 tool calls.
    4. If you can't find a reliable answer, say so honestly.
    5. Provide your final answer in a clear, structured format.
    6. Cite your sources with URLs.
"""
messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMT,
    },
    {
        "role": "user",
        "content": "What's the weather in Tokyo?",
    }
]


# ------- Tools definitions ------ #
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


def search_web(query: str) -> str:
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


def read_url(url: str) -> str:
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


TOOLS = {
    "search_web": search_web,
    "read_url": read_url,
}

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web using DuckDuckGo. Returns top 5 results with titles and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Read the text content of a web page. Returns up to 3000 characters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to read"
                    }
                },
                "required": ["url"]
            }
        }
    },
]

# ----- ReAct Loop ------- #
def run_chad(str: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMT},
        {"role": "user", "content": question},
    ]

    for i in range(6):
        print(f"itr {i}\n")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            print(f"✅ Final answer received.")
            return msg.content

        for tool_call in msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)

            print(f"🔧 Calling: {fn_name}({fn_args})")

            if fn_name in TOOLS:
                result = TOOLS[fn_name](**fn_args)
            else:
                result = f"Error: Unknown tool '{fn_name}"

            preview = result[:200] + "..." if len(result) > 200 else result
            print(f"📋 Result: {preview}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
    
    return "Agent Reached Max Iterations"




if __name__ == "__main__":
    question = " ".join(sys.argv[1:])
    print(f"asking questions: {question}\n")

    answer = run_chad(question)
    print(f"FINAL ANSWER:\n{'='*60}")
    print(answer)