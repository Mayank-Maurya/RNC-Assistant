import json
import sys
from openai import OpenAI
from config import require_key, MODEL
from html.parser import HTMLParser
from urllib.request import urlopen, Request
from urllib.parse import quote_plus
import re
from dataclasses import dataclass, field
import time

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

# ------- Promt Variants -------- #
VARIANT_CONCISE = {
    "name": "Concise Analyst",
    "prompt": """You are RNC-Assistant, a concise research analyst.
You give brief, factual answers. No fluff. Bullet points preferred.
Maximum 3 sentences per point. Cite sources inline.

Available tools: search_web(query), read_url(url).
Use at most 3 tool calls. Be efficient."""
}

VARIANT_THOROUGH = {
    "name": "Thorough Researcher",
    "prompt": """You are RNC-Assistant, a thorough senior researcher.
You provide comprehensive analysis with multiple perspectives.
Compare sources, note contradictions, and qualify uncertainties.
Your answers should read like a well-researched briefing document.

Available tools: search_web(query), read_url(url).
Use as many tool calls as needed (up to 5) to ensure accuracy. """
}

VARIANT_STRUCTURED = {
    "name": "Structured Reporter",
    "prompt": """You are RNC-Assistant, a structured report generator.
Every answer MUST follow this exact format:

## Summary
(2-3 sentences)

## Key Findings
(numbered list)

## Sources
(URLs used)

## Confidence
(high/medium/low with justification)

Available tools: search_web(query), read_url(url).
Use 2-4 tool calls for a balanced approach."""
}

VARIANTS = [VARIANT_CONCISE, VARIANT_THOROUGH, VARIANT_STRUCTURED]


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

# -------- Evaluation Cases -------- #
EVAL_CASES = [
    {
        "question": "What is the population of Tokyo?",
        "expected_keywords": ["million"],
        "max_tool_calls": 3,
        "category": "factual",
    },
    {
        "question": "Compare React and Vue.js for a new web project.",
        "expected_keywords": ["react", "vue"],
        "max_tool_calls": 4,
        "category": "comparison",
    },
    {
        "question": "What is the Model Context Protocol (MCP)?",
        "expected_keywords": ["protocol", "tool"],
        "max_tool_calls": 3,
        "category": "technical",
    },
    {
        "question": "Explain the difference between RAG and fine-tuning.",
        "expected_keywords": ["retrieval", "training"],
        "max_tool_calls": 3,
        "category": "technical",
    },
    {
        "question": "What are the top 3 programming languages in 2025?",
        "expected_keywords": ["python"],
        "max_tool_calls": 3,
        "category": "factual",
    },
    {
        "question": "Write me a poem about cats.",
        "expected_refusal": True,
        "category": "out_of_scope",
    },
    {
        "question": "Should I invest in Bitcoin?",
        "expected_refusal": True,
        "category": "out_of_scope",
    },
    {
        "question": "What is LangGraph and how does it work?",
        "expected_keywords": ["graph", "state"],
        "max_tool_calls": 4,
        "category": "technical",
    },
    {
        "question": "What are the pros and cons of microservices?",
        "expected_keywords": ["service"],
        "max_tool_calls": 3,
        "category": "comparison",
    },
    {
        "question": "How does vector search work?",
        "expected_keywords": ["embedding", "vector"],
        "max_tool_calls": 3,
        "category": "technical",
    },
]

# --------- Evaluation Login -------- #
@dataclass
class EvalResult:
    question: str
    variant: str
    answer: str
    tool_calls_count: int
    has_expected_keywords: bool
    expected_refusal: bool = False
    correctly_refused: bool = False
    latency_ms: int = 0

def run_single_eval(variant: dict, case: dict) -> EvalResult:
    """Run a single eval case with a single prompt variant (no actual tool execution)."""
    messages = [
        {"role": "system", "content": variant["prompt"]},
        {"role": "user", "content": case["question"]},
    ]

    start = time.time()

    # Single LLM call — we're testing prompt quality, not tool execution
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS_SCHEMA,
    )

    latency = int((time.time() - start) * 1000)
    msg = response.choices[0].message
    answer = msg.content or ""
    tool_calls_count = len(msg.tool_calls) if msg.tool_calls else 0

    # Check expected keywords
    has_keywords = True
    if "expected_keywords" in case:
        answer_lower = answer.lower()
        has_keywords = all(kw.lower() in answer_lower for kw in case["expected_keywords"])

    # Check refusal behavior
    expected_refusal = case.get("expected_refusal", False)
    refusal_phrases = ["can't help", "not able to", "outside my scope",
                       "don't provide", "cannot", "not appropriate",
                       "i'm a research", "apologize"]
    correctly_refused = any(p in answer.lower() for p in refusal_phrases) if expected_refusal else False

    return EvalResult(
        question=case["question"],
        variant=variant["name"],
        answer=answer,
        tool_calls_count=tool_calls_count,
        has_expected_keywords=has_keywords,
        expected_refusal=expected_refusal,
        correctly_refused=correctly_refused,
        latency_ms=latency,
    )

def run_eval_suite():
    """Run all eval cases across all prompt variants."""
    results: dict[str, list[EvalResult]] = {}

    for variant in VARIANTS:
        print(f"\n{'='*60}")
        print(f"Testing: {variant['name']}")
        print(f"{'='*60}")

        variant_results = []
        for i, case in enumerate(EVAL_CASES):
            print(f"  [{i+1}/{len(EVAL_CASES)}] {case['question'][:50]}...", end=" ")
            try:
                result = run_single_eval(variant, case)
                status = "✅" if result.has_expected_keywords or result.correctly_refused else "❌"
                print(f"{status} ({result.latency_ms}ms, {result.tool_calls_count} tools)")
                variant_results.append(result)
            except Exception as e:
                print(f"💥 Error: {e}")

        results[variant["name"]] = variant_results

    return results

def print_summary(results: dict[str, list[EvalResult]]):
    """Print a comparison table of all variants."""
    print(f"\n\n{'='*70}")
    print("PROMPT A/B TEST RESULTS")
    print(f"{'='*70}\n")

    header = f"{'Variant':<22} | {'Quality':>8} | {'Avg Tools':>10} | {'Avg Latency':>12} | {'Refusal':>8}"
    print(header)
    print("─" * len(header))

    for name, evals in results.items():
        if not evals:
            continue

        # Quality: % of cases where expected keywords were found
        non_refusal = [e for e in evals if not e.expected_refusal]
        refusal = [e for e in evals if e.expected_refusal]

        quality = sum(1 for e in non_refusal if e.has_expected_keywords) / max(len(non_refusal), 1) * 100
        avg_tools = sum(e.tool_calls_count for e in evals) / max(len(evals), 1)
        avg_latency = sum(e.latency_ms for e in evals) / max(len(evals), 1)
        refusal_accuracy = sum(1 for e in refusal if e.correctly_refused) / max(len(refusal), 1) * 100

        print(f"{name:<22} | {quality:>7.0f}% | {avg_tools:>10.1f} | {avg_latency:>10.0f}ms | {refusal_accuracy:>7.0f}%")

    print()

# ------ Main Fn ------- #
if __name__ == "__main__":
    question = " ".join(sys.argv[1:])
    print(f"asking questions: {question}\n")

    # answer = run_chad(question)
    # print(f"FINAL ANSWER:\n{'='*60}")
    # print(answer)

    results = run_eval_suite()
    print_summary(results)