"""
Session 7 Assignment - Real sample audio, synthesized locally (no mic here)
=================================================================================
Homework item 1 needs "~30s audio" to run through the pipeline. This
environment has no microphone, and OpenRouter does NOT proxy the TTS
endpoint -- verified live: client.audio.speech.create(model="tts-1") raises
"Model tts-1 does not exist", unlike the whisper-1 transcription endpoint it
does proxy (see llm_client.py's docstring). So this uses pyttsx3, the local
SAPI5 text-to-speech engine that ships with Windows, entirely offline and
free, to synthesize genuine spoken audio from a script -- real speech, not a
placeholder tone -- for every case in golden_set.py.

Usage:
    python audio_gen.py              # (re)generate every audio file this session uses
"""

import wave
from pathlib import Path

import pyttsx3

from golden_set import GOLDEN_CASES

AUDIO_DIR = Path(__file__).resolve().parent / "audio"

# pyttsx3's default rate (200 wpm) rendered a ~76-word script in ~26s in
# testing; slowing to 175 wpm lands each of these ~75-90 word scripts closer
# to the "~30s" the homework asks for.
RATE = 175


def synthesize(text: str, out_path: Path) -> float:
    engine = pyttsx3.init()
    engine.setProperty("rate", RATE)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    engine.save_to_file(text, str(out_path))
    engine.runAndWait()
    with wave.open(str(out_path), "rb") as f:
        return f.getnframes() / float(f.getframerate())


def main():
    AUDIO_DIR.mkdir(exist_ok=True)
    for case in GOLDEN_CASES:
        out_path = AUDIO_DIR / case["audio_file"]
        duration = synthesize(case["script"], out_path)
        print(f"{case['id']:<22} {duration:5.1f}s -> {out_path.relative_to(AUDIO_DIR.parent)}")


if __name__ == "__main__":
    main()
