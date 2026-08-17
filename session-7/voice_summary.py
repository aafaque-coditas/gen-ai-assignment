"""
Session 7 Assignment - Homework: ~30s audio -> transcribe -> LLM summary (3 bullets)
==========================================================================================
Core homework pipeline (this session's homework, items 1-2):
  1. Batch STT: send the whole audio file to Whisper, in one call,
     get the full transcript back -- fine here since the user can wait a
     few seconds (the batch pattern: "upload a file, wait, get the result").
  2. One LLM call: turn that transcript into exactly 3 bullet points.
  3. Log stt_ms, llm_ms, total_ms for the run (the "log time at every
     boundary" principle, trimmed to the two boundaries this 2-stage pipeline has).

Usage:
    python voice_summary.py                      # runs on the default demo audio
    python voice_summary.py --audio audio/case-3-ota-cancellation.wav
    python voice_summary.py --verbose             # also print the full transcript
"""

import argparse
import time
from pathlib import Path

from llm_client import get_client, call_model, transcribe_audio, DEFAULT_MODEL

AUDIO_DIR = Path(__file__).resolve().parent / "audio"
DEFAULT_AUDIO = AUDIO_DIR / "case-1-design-system.wav"

SUMMARY_SYSTEM_PROMPT = (
    "You summarize a spoken status update or support-call transcript into "
    "exactly 3 bullet points, one per line, each starting with '- '. Cover "
    "only what's actually in the transcript -- no invented facts, no intro "
    "sentence before the bullets, no closing remarks after them. Every named "
    "entity in the transcript -- people, teams, services/products, booking "
    "or ticket references -- must appear in at least one bullet; do not let "
    "naming one entity push another one out."
)


def run_voice_pipeline(client, audio_path: Path, model: str = DEFAULT_MODEL) -> dict:
    """Runs STT -> LLM summary, timing each stage separately.
    Returns {"transcript", "summary", "stt_ms", "llm_ms", "total_ms"}."""
    total_start = time.perf_counter()

    stt_start = time.perf_counter()
    transcript = transcribe_audio(client, audio_path)
    stt_ms = (time.perf_counter() - stt_start) * 1000

    llm_start = time.perf_counter()
    summary = call_model(
        client,
        [
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": transcript},
        ],
        model=model,
        temperature=0.0,
        max_tokens=200,
    )
    llm_ms = (time.perf_counter() - llm_start) * 1000

    total_ms = (time.perf_counter() - total_start) * 1000
    return {
        "transcript": transcript,
        "summary": summary,
        "stt_ms": stt_ms,
        "llm_ms": llm_ms,
        "total_ms": total_ms,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Session 7 homework: audio -> transcript -> 3-bullet LLM summary")
    parser.add_argument("--audio", default=str(DEFAULT_AUDIO), help=f"Path to the audio file (default: {DEFAULT_AUDIO.name})")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--verbose", action="store_true", help="Also print the full transcript")
    return parser.parse_args()


def main():
    args = parse_args()
    audio_path = Path(args.audio)
    if not audio_path.exists():
        raise SystemExit(
            f"No audio file at {audio_path}. Run `python audio_gen.py` first to synthesize this session's sample audio."
        )

    client = get_client()
    result = run_voice_pipeline(client, audio_path, args.model)

    if args.verbose:
        print(f"Transcript:\n{result['transcript']}\n")
    print(f"Summary:\n{result['summary']}\n")
    print(f"stt_ms={result['stt_ms']:.0f}  llm_ms={result['llm_ms']:.0f}  total_ms={result['total_ms']:.0f}")


if __name__ == "__main__":
    main()
