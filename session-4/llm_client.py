"""
Shared LLM API-access plumbing for Session 4's agent (agent.py, multi_agent.py,
eval_runner.py). Same OpenRouter/OpenAI auto-detection as every other session
(see ../session-1/README.md) -- copied from session-1's chatbot.py and then
split out the way session-2/session-3 already did, plus one addition this
session actually needs: passing `tools` through to the API and handing back
the *raw* assistant message (not just its text), since the agent loop has to
inspect `message.tool_calls`, not only `message.content`.
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
# text-embedding-3-small works unprefixed through OpenRouter too (verified in
# session-3), needed here for the search_docs tool's query embedding.
DEFAULT_EMBED_MODEL = "text-embedding-3-small"


def get_client() -> OpenAI:
    if not API_KEY:
        print(
            f"ERROR: OPENAI_API_KEY not found. Add it to {ROOT_ENV_PATH} as:\n"
            f"  OPENAI_API_KEY=sk-...",
            file=sys.stderr,
        )
        sys.exit(1)
    return OpenAI(api_key=API_KEY, base_url=BASE_URL)


def call_model(client: OpenAI, messages: list, model: str, temperature: float, max_tokens: int, tools: list = None):
    """One turn of the agent loop. Returns the raw assistant *message* object
    (not just its text) -- the caller needs both `.content` and
    `.tool_calls`, needed to build the agent loop from scratch."""
    kwargs = {}
    if tools:
        kwargs["tools"] = tools
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return response.choices[0].message


def embed_texts(client: OpenAI, texts: list, model: str = DEFAULT_EMBED_MODEL, batch_size: int = 100) -> list:
    """Embed a list of strings, batched, preserving input order. Copied from
    session-3/llm_client.py -- the search_docs tool needs to embed the user's
    query the same way the Session 3 index was built."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        vectors.extend(item.embedding for item in response.data)
    return vectors
