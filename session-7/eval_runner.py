"""
Session 7 Assignment - Homework item 3: run the 5-case golden set, report pass/fail
==========================================================================================
Runs every case in golden_set.py through the same run_voice_pipeline() as
voice_summary.py, checks the resulting 3-bullet summary against each case's
expected phrases, and prints a PASS/FAIL summary plus average per-stage
timings -- same "list of OR-groups, ANDed" checker as session-3's
test_runner.py and session-4's eval_runner.py.

Usage:
    python eval_runner.py
    python eval_runner.py --verbose   # also print each case's transcript + summary
"""

import argparse

from golden_set import GOLDEN_CASES
from llm_client import get_client, DEFAULT_MODEL
from voice_summary import AUDIO_DIR, run_voice_pipeline


def check_summary(summary: str, checks: list) -> bool:
    lowered = summary.lower()
    return all(any(phrase in lowered for phrase in group) for group in checks)


def main():
    parser = argparse.ArgumentParser(description="Run the 5-case golden set and report pass/fail")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--verbose", action="store_true", help="Also print each case's transcript + summary")
    args = parser.parse_args()

    client = get_client()

    passed = 0
    total_stt = total_llm = total_ms = 0.0
    for case in GOLDEN_CASES:
        audio_path = AUDIO_DIR / case["audio_file"]
        if not audio_path.exists():
            raise SystemExit(f"Missing {audio_path}. Run `python audio_gen.py` first.")

        result = run_voice_pipeline(client, audio_path, args.model)
        ok = check_summary(result["summary"], case["checks"])
        passed += ok
        total_stt += result["stt_ms"]
        total_llm += result["llm_ms"]
        total_ms += result["total_ms"]

        mark = "PASS" if ok else "FAIL"
        print(
            f"[{mark}] {case['id']:<22} "
            f"(stt_ms={result['stt_ms']:.0f} llm_ms={result['llm_ms']:.0f} total_ms={result['total_ms']:.0f})"
        )
        if args.verbose:
            print(f"  Transcript: {result['transcript']}")
            print(f"  Summary:\n{result['summary']}\n")

    n = len(GOLDEN_CASES)
    print(f"\n--- Summary: {passed}/{n} passed ({passed / n:.0%}) ---")
    print(f"Avg stt_ms={total_stt / n:.0f}  avg llm_ms={total_llm / n:.0f}  avg total_ms={total_ms / n:.0f}")


if __name__ == "__main__":
    main()
