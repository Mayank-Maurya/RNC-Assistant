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
from skills.webskill import WebSkill
from skills.fileskill import FileSkill
from skills.codeskill import CodeSkill
from skills.skillRegistry import SkillRegistry

# ----- configs -----
client = OpenAI(
    api_key=require_key("openrouter"),
    base_url=require_key("open_router_url"),
)

# ---- configure registry -------

registry = SkillRegistry()
registry.register(WebSkill())
# registry.register(FileSkill(base_dir="./workspace"))
# registry.register(CodeSkill())

all_tools = registry.get_all_tools()

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


# ----- ReAct Loop ------- #
def run_chad(question: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMT},
        {"role": "user", "content": question},
    ]

    for i in range(6):
        print(f"itr {i}\n")
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=all_tools
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

            result = registry.execute_tool(fn_name, fn_args)

            preview = result[:200] + "..." if len(result) > 200 else result
            print(f"📋 Result: {preview}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result,
            })
    
    return "Agent Reached Max Iterations"


# ------ Main Fn ------- #
if __name__ == "__main__":
    question = " ".join(sys.argv[1:])
    print(f"asking questions: {question}\n")

    answer = run_chad(question)
    print(f"FINAL ANSWER:\n{'='*60}")
    print(answer)