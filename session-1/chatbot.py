"""
Session 1 Assignment — Terminal API Chat
=========================================

  Task 1 (API access) - reads the API key from the root .env file
                         (never hard-coded, never committed).
  Task 2 (CLI chat)    - a terminal chatbot that keeps conversation history
                         in a `messages` list, tagged by role
                         ("user"/"assistant" only), and resends it every
                         call since the API itself is stateless.

Usage:
    python chatbot.py
    python chatbot.py --model gpt-4o-mini --temperature 0.2 --stream

Type 'quit' or 'exit' to leave the chat.
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIError, APIConnectionError, AuthenticationError

# ---------------------------------------------------------------------------
# Task 1 — API access: load the key from the .env file at the repo root.
# ---------------------------------------------------------------------------
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


def call_model(client: OpenAI, messages: list, model: str, temperature: float, max_tokens: int, stream: bool = False) -> str:
    """Send the full message history to the API and return the assistant's reply text."""
    if not stream:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content

    # Streamed variant: print tokens as they arrive, then return the joined text.
    print("Assistant: ", end="", flush=True)
    chunks = []
    stream_resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    for event in stream_resp:
        delta = event.choices[0].delta.content or ""
        chunks.append(delta)
        print(delta, end="", flush=True)
    print()  # newline after the streamed reply
    return "".join(chunks)


# ---------------------------------------------------------------------------
# Task 2 — CLI chat with a persistent, role-tagged `messages` list.
# Only two roles are used: "user" and "assistant".
# ---------------------------------------------------------------------------
def run_chat(args):
    client = get_client()

    # The messages list IS the conversation history. We append user/assistant
    # turns as the chat progresses and resend all of it each call, because
    # the API has no memory of its own.
    messages = []

    print("GenAI Terminal Chat -- type 'quit' or 'exit' to leave")
    print(f"(model={args.model}, temperature={args.temperature})\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break

        # Distinguish the user turn from the assistant turn via `role`.
        messages.append({"role": "user", "content": user_input})

        try:
            reply = call_model(
                client,
                messages,
                model=args.model,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                stream=args.stream,
            )
        except AuthenticationError:
            print("ERROR: Invalid API key. Check your .env file.", file=sys.stderr)
            break
        except APIConnectionError:
            print("ERROR: Could not reach the API. Check your network.", file=sys.stderr)
            continue
        except APIError as e:
            print(f"ERROR: API call failed: {e}", file=sys.stderr)
            continue

        if not args.stream:
            print(f"Assistant: {reply}")

        # Append the assistant's reply so the NEXT request includes it --
        # this is what gives the chat "memory" across turns.
        messages.append({"role": "assistant", "content": reply})


def parse_args():
    parser = argparse.ArgumentParser(description="Session 1 assignment: terminal API chat")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--temperature", type=float, default=0.7, help="0 = deterministic, higher = more varied")
    parser.add_argument("--max-tokens", type=int, default=500, help="Max tokens in the reply")
    parser.add_argument("--stream", action="store_true", help="Stream the reply token-by-token")
    return parser.parse_args()


def main():
    args = parse_args()
    run_chat(args)


if __name__ == "__main__":
    main()
