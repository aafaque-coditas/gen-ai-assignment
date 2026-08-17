"""
Session 3 Assignment - Deliverable: 3+ test questions with pass/fail
=======================================================================

Runs every question in test_questions.py through the same retrieve ->
generate pipeline as rag.py (default k=3, no rerank/json/stream), checks
the answer against expected phrases (or the refusal guard), and prints a
PASS/FAIL summary.

Usage:
    python test_runner.py
"""

import argparse

from llm_client import get_client, call_model, DEFAULT_MODEL
from rag import build_messages, format_source, load_store, retrieve
from test_questions import REFUSAL_PHRASES, TEST_QUESTIONS


def check_answer(answer: str, spec: dict) -> bool:
    lowered = answer.lower()
    if spec.get("expect_refusal"):
        return any(phrase in lowered for phrase in REFUSAL_PHRASES)
    return all(any(phrase in lowered for phrase in group) for group in spec["checks"])


def main():
    parser = argparse.ArgumentParser(description="Run the 3+ required test questions and report pass/fail")
    parser.add_argument("--k", type=int, default=3, help="Chunks to retrieve per question (default: 3)")
    args = parser.parse_args()

    client = get_client()
    store = load_store()

    passed = 0
    for i, spec in enumerate(TEST_QUESTIONS, start=1):
        question = spec["question"]
        results = retrieve(client, store, question, args.k, use_rerank=False)
        messages = build_messages(question, results, json_mode=False)
        answer = call_model(client, messages, DEFAULT_MODEL, temperature=0.0, max_tokens=400)

        ok = check_answer(answer, spec)
        passed += ok
        mark = "PASS" if ok else "FAIL"

        print(f"[{mark}] Q{i}: {question}")
        print(f"  Retrieved: {', '.join(format_source(r) for r in results)}")
        print(f"  Answer: {answer}\n")

    print(f"--- Summary: {passed}/{len(TEST_QUESTIONS)} passed ---")


if __name__ == "__main__":
    main()
