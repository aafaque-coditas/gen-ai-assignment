"""
Shared LLM API-access plumbing for Session 7's voice pipeline (voice_summary.py,
eval_runner.py): the OpenAI client (same OpenRouter/OpenAI auto-detection as
every other session -- see ../session-1/README.md), a one-shot chat helper,
and a Whisper transcription helper.

Verified live before building on it: OpenRouter proxies the whisper-1
transcription endpoint (client.audio.transcriptions.create) the same way it
already proxies chat completions (session-1) and embeddings (session-3) --
confirmed against a real synthesized audio file before relying on it here.
It does NOT proxy tts-1 (client.audio.speech.create raises "Model tts-1 does
not exist"), unlike the transcription endpoint -- see audio_gen.py and the
README's "A real gap" note for why this session's sample audio is
synthesized locally instead of via the OpenRouter/OpenAI TTS endpoint.
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
# whisper-1 works unprefixed through OpenRouter too (verified live, the same
# way text-embedding-3-small did in session-3) -- no "openai/" prefix needed.
DEFAULT_STT_MODEL = "whisper-1"


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
    """One-shot chat completion. Returns the reply text."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content


def transcribe_audio(client: OpenAI, audio_path, model: str = DEFAULT_STT_MODEL) -> str:
    """Batch STT ('upload a file, wait, get the result'): send the
    whole audio file in one call, return the full transcript."""
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(model=model, file=f)
    return response.text
