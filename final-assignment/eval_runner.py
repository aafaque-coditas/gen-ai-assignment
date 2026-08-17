"""
Final Assignment - Eval runner
===================================
Runs the whole pipeline once, asks the four content questions of the episode
it produced, runs the three structure checks against the same run, then calls
critic.check_section() directly with the three hand-written critic cases, and
reports PASS/FAIL for all ten -- same style as every earlier session's eval
runner (session-3/test_runner.py, session-4/eval_runner.py,
session-7/eval_runner.py).

Usage:
    python eval_runner.py
"""

import argparse

from critic import check_section
from eval_set import CONTENT_QUESTIONS, CRITIC_CHECKS, STRUCTURE_CHECKS
from llm_client import DEFAULT_MODEL, get_client
from pipeline import run_pipeline
from rag import all_chunks_context


def run_content_questions(result: dict) -> int:
    passed = 0
    for spec in CONTENT_QUESTIONS:
        ok = spec["check"](result)
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {spec['id']}")
        print(f"        Q: {spec['question']}")
        print(f"        Expected: {spec['expected']}")
    return passed


def run_structure_checks(result: dict) -> int:
    passed = 0
    for spec in STRUCTURE_CHECKS:
        ok = spec["check"](result)
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {spec['id']}: {spec['description']}")
        print(f"        Expected: {spec['expected']}")
    return passed


def run_critic_checks(client, model: str) -> int:
    doc_text = all_chunks_context()
    passed = 0
    for spec in CRITIC_CHECKS:
        section = {"heading": spec["heading"], "text": spec["text"]}
        verdict, _ = check_section(client, section, doc_text, model=model)
        flagged = verdict.get("flagged_claims", [])
        ok = spec["expect_flag"] == bool(flagged)
        passed += ok
        print(f"[{'PASS' if ok else 'FAIL'}] {spec['id']}: {spec['description']}")
        print(f"        Expected: {spec['expected']}")
        print(f"        flagged_claims={flagged}")
    return passed


def main():
    parser = argparse.ArgumentParser(description="Run the 10-case eval set and report pass/fail")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--episode-name", default="eval-run")
    args = parser.parse_args()

    print("=== Running the pipeline once, to test what it produces ===\n")
    result = run_pipeline(episode_name=args.episode_name, model=args.model, verbose=False)
    print(
        f"Generated: '{result['title']}' ({result['audio_seconds']:.1f}s audio, "
        f"{result['tokens']['total']} tokens, {result['timings_ms']['total_ms']:.0f}ms total)\n"
    )

    print("=== Group A: questions about the finished episode ===")
    n1 = run_content_questions(result)

    print("\n=== Group B: structure checks on the same run ===")
    n2 = run_structure_checks(result)

    print("\n=== Group C: the checking step, tested on purpose ===")
    client = get_client()
    n3 = run_critic_checks(client, args.model)

    total_passed = n1 + n2 + n3
    total_checks = len(CONTENT_QUESTIONS) + len(STRUCTURE_CHECKS) + len(CRITIC_CHECKS)
    print(f"\n--- Summary: {total_passed}/{total_checks} passed ({total_passed / total_checks:.0%}) ---")


if __name__ == "__main__":
    main()
