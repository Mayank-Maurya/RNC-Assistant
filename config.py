import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BASE_URL_OPEN_ROUTER = os.getenv("BASE_URL_OPEN_ROUTER", "")
MODEL = "openai/gpt-oss-120b:free"
# "google/gemma-4-26b-a4b-it:free"
def require_key(provider: str) -> str:
    keys = {
        "openrouter": OPENROUTER_API_KEY,
        "open_router_url": BASE_URL_OPEN_ROUTER
    }
    key = keys.get(provider.lower(), "")
    if not key:
        raise EnvironmentError(
            f"Missing {provider.upper()}_API_KEY."
        )
    return key
