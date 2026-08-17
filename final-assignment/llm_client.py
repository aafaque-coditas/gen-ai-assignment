"""
Final Assignment - Shared LLM API-access plumbing
======================================================
Same OpenRouter/OpenAI auto-detection every session in this repo uses (see
../session-1/README.md for why the root .env's OPENAI_API_KEY is actually
an OpenRouter key). Two things this file adds that no earlier session's
llm_client.py needed together:

  call_model()      - returns (text, tokens) instead of just text, so every
                       stage of this pipeline can log its own token count
                       (the assignment's "log token counts for your model
                       calls" requirement) without each caller having to dig
                       into response.usage itself.
  call_with_tools()  - copied from session-4/6's call_model(tools=...): returns
                       the raw assistant *message* (not just text), since
                       save_agent.py's tool-calling loop needs to inspect
                       message.tool_calls.
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
# text-embedding-3-small works unprefixed through OpenRouter too (verified
# live in session-3).
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


def _usage_dict(usage) -> dict:
    if not usage:
        return {"prompt": 0, "completion": 0, "total": 0}
    return {"prompt": usage.prompt_tokens, "completion": usage.completion_tokens, "total": usage.total_tokens}


def call_model(
    client: OpenAI,
    messages: list,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 800,
    json_mode: bool = False,
) -> tuple:
    """Blocking chat completion. Returns (reply_text, tokens_dict)."""
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs,
    )
    return response.choices[0].message.content, _usage_dict(response.usage)


def call_with_tools(
    client: OpenAI,
    messages: list,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = 300,
    tools: list = None,
) -> tuple:
    """One turn of a tool-calling loop -- same shape as session-4/6's
    call_model(tools=...). Returns (raw_assistant_message, tokens_dict); the
    caller needs both `.content` and `.tool_calls`."""
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
    return response.choices[0].message, _usage_dict(response.usage)


def embed_texts(client: OpenAI, texts: list, model: str = DEFAULT_EMBED_MODEL, batch_size: int = 100) -> list:
    """Embed a list of strings, batched, preserving input order."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        vectors.extend(item.embedding for item in response.data)
    return vectors
