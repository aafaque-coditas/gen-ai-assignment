"""
Final Assignment - Text-to-Speech
======================================
Session 7 verified live that OpenRouter does not proxy the TTS endpoint:
client.audio.speech.create(model="tts-1") raises "Model tts-1 does not
exist", unlike the whisper-1 transcription endpoint it does proxy (see
../session-7/llm_client.py's docstring). Same fix as session-7's
audio_gen.py: pyttsx3, the local SAPI5 engine bundled with Windows, fully
offline, no API key needed -- real synthesized speech, not a placeholder
tone.
"""

import time
import wave
from pathlib import Path

import pyttsx3

DEFAULT_RATE = 175  # session-7's tuned rate for natural spoken pacing


def synthesize_speech(text: str, out_path: Path, rate: int = DEFAULT_RATE) -> dict:
    """Synthesizes `text` to a .wav file at out_path.
    Returns {"tts_ms", "audio_seconds", "path"}."""
    start = time.perf_counter()
    engine = pyttsx3.init()
    engine.setProperty("rate", rate)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    engine.save_to_file(text, str(out_path))
    engine.runAndWait()
    tts_ms = (time.perf_counter() - start) * 1000

    with wave.open(str(out_path), "rb") as f:
        audio_seconds = f.getnframes() / float(f.getframerate())

    return {"tts_ms": tts_ms, "audio_seconds": audio_seconds, "path": str(out_path)}
