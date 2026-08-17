"""
Shared LLM API-access plumbing for Session 2's scripts (sentiment.py,
math_solver.py). Not a deliverable by itself -- neither Session 2 task
needs an interactive chat loop or a temperature experiment, so this is
trimmed down to just what those scripts actually import: the client and
a one-shot `call_model` helper.

The API key is read from OPENAI_API_KEY in the root .env file (never
hard-coded, never committed) -- see ../session-1/README.md for why it's
actually an OpenRouter key and how the base_url/model auto-detection
below handles that.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ROOT_ENV_PATH)

API_KEY = os.getenv("OPENAI_API_KEY")

# The key in this repo's .env is an OpenRouter key (prefix "sk-or-"), which
# only works against OpenRouter's endpoint, not api.openai.com directly.
# Auto-detect so this script works whether OPENAI_API_KEY holds a real
# OpenAI key (sk-...) or an OpenRouter key (sk-or-...).
IS_OPENROUTER_KEY = bool(API_KEY) and API_KEY.startswith("sk-or-")
BASE_URL = "https://openrouter.ai/api/v1" if IS_OPENROUTER_KEY else None
DEFAULT_MODEL = "openai/gpt-4o-mini" if IS_OPENROUTER_KEY else "gpt-4o-mini"


def get_client() -> OpenAI:
    if not API_KEY:
        print(
            f"ERROR: OPENAI_API_KEY not found. Add it to {ROOT_ENV_PATH} as:\n"
            f"  OPENAI_API_KEY=sk-...",
            file=sys.stderr,
        )
        sys.exit(1)
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def call_model(client: OpenAI, messages: list, model: str, temperature: float, max_tokens: int) -> str:
    """Send a one-shot message list to the API and return the assistant's reply text."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content
