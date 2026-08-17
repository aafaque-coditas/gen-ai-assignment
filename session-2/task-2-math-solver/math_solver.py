"""
Session 2 Assignment - Task 2: Math Problem Solver (Chain of Thought)
=======================================================================

A CLI tool that solves math word problems using chain-of-thought
prompting ("Let's think step by step"), then extracts and displays just
the final numeric answer separately from the full reasoning, using a
structured output line the code can reliably parse (the "reliable ask"
pattern) instead of regexing free-form prose.

Usage:
    python math_solver.py                   # interactive: type your own problems
    python math_solver.py --test            # run the 10 built-in test problems
    python math_solver.py --test --verbose  # also print each problem's full reasoning
"""

import argparse
import re
import sys
from pathlib import Path

# llm_client.py is shared across both Session 2 tasks and lives one level
# up, at session-2/ -- add it to the import path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_client import get_client, call_model, DEFAULT_MODEL
from math_problems import MATH_PROBLEMS

FINAL_ANSWER_RE = re.compile(r"final answer\s*:\s*\$?(-?[\d,]+(?:\.\d+)?)", re.IGNORECASE)


def build_cot_prompt(problem: str) -> str:
    return (
        f"{problem}\n\n"
        "Let's think step by step. Show your reasoning, then on its own "
        "final line, output exactly:\n"
        "Final Answer: <number>"
    )


def solve(client, model: str, problem: str):
    """Return (full_reasoning_text, extracted_final_answer_or_None)."""
    messages = [{"role": "user", "content": build_cot_prompt(problem)}]
    reasoning = call_model(client, messages, model=model, temperature=0.0, max_tokens=500)

    match = FINAL_ANSWER_RE.search(reasoning)
    if not match:
        return reasoning, None

    number_str = match.group(1).replace(",", "")
    try:
        answer = float(number_str)
    except ValueError:
        return reasoning, None
    return reasoning, answer


def run_interactive(client, model: str):
    print("Math Problem Solver (chain-of-thought) -- type 'quit' or 'exit' to leave\n")
    while True:
        try:
            problem = input("Problem: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not problem:
            continue
        if problem.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break

        reasoning, answer = solve(client, model, problem)
        print(f"\n{reasoning}\n")
        if answer is not None:
            print(f">>> Final Answer: {answer:g}\n")
        else:
            print(">>> Could not extract a final numeric answer from the model's reply.\n")


def run_test(client, model: str, verbose: bool):
    print(f"Testing {len(MATH_PROBLEMS)} problems (model={model})...\n")
    correct_count = 0
    for i, (problem, expected) in enumerate(MATH_PROBLEMS, start=1):
        reasoning, answer = solve(client, model, problem)
        is_correct = answer is not None and abs(answer - expected) < 0.01
        correct_count += is_correct

        mark = "OK  " if is_correct else "MISS"
        print(f"[{mark}] Problem {i}: {problem}")
        if verbose:
            print(f"  Reasoning:\n{reasoning}\n")
        got = f"{answer:g}" if answer is not None else "unparseable"
        print(f"  Expected: {expected:g} | Got: {got}\n")

    accuracy = correct_count / len(MATH_PROBLEMS)
    print(f"--- Summary: {correct_count}/{len(MATH_PROBLEMS)} correct ({accuracy:.0%}) ---")


def main():
    parser = argparse.ArgumentParser(description="Math word-problem solver using chain-of-thought prompting")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--test", action="store_true", help="Run the 10 built-in test problems instead of interactive mode")
    parser.add_argument("--verbose", action="store_true", help="In --test mode, also print each problem's full reasoning")
    args = parser.parse_args()

    client = get_client()

    if args.test:
        run_test(client, args.model, args.verbose)
    else:
        run_interactive(client, args.model)


if __name__ == "__main__":
    main()
