"""
Shared LLM API-access plumbing for Session 3's RAG app (ingest.py, rag.py,
test_runner.py): the OpenAI client, a chat-completion helper (blocking,
streaming, and JSON-mode variants), and a batch embeddings helper.

The API key is read from OPENAI_API_KEY in the root .env file (never
hard-coded, never committed) -- see ../session-1/README.md for why it's
actually an OpenRouter key and how the base_url/model auto-detection below
handles that. OpenRouter proxies /embeddings too, so the same key and
base_url work for both chat and embedding calls (verified directly against
the live API before building this).
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
# live), unlike chat models which need the "openai/" provider prefix there.
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


def call_model(client: OpenAI, messages: list, model: str, temperature: float, max_tokens: int, json_mode: bool = False) -> str:
    """Blocking chat completion. Returns the full reply text."""
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
    return response.choices[0].message.content


def stream_model(client: OpenAI, messages: list, model: str, temperature: float, max_tokens: int):
    """Streaming chat completion. Yields text deltas as they arrive."""
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for event in stream:
        delta = event.choices[0].delta.content
        if delta:
            yield delta


def embed_texts(client: OpenAI, texts: list, model: str = DEFAULT_EMBED_MODEL, batch_size: int = 100) -> list:
    """Embed a list of strings, batched, preserving input order."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = client.embeddings.create(model=model, input=batch)
        vectors.extend(item.embedding for item in response.data)
    return vectors
