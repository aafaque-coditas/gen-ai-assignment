"""
Session 4 Assignment - Stretch: Small Eval (5 tasks, pass rate, avg iterations)
====================================================================================
Runs every task in eval_tasks.py through agent.run_agent(), checks the answer
against expected phrases (and, for one task, that the agent didn't reach for
a tool it didn't need), then reports PASS/FAIL plus the two summary numbers
that matter for a small eval: pass rate and average iterations.

Usage:
    python eval_runner.py
    python eval_runner.py --verbose   # also print each task's [TOOL]/[OBS] trace
"""

import argparse

from agent import run_agent, DEFAULT_MAX_ITERATIONS
from eval_tasks import EVAL_TASKS
from llm_client import get_client, DEFAULT_MODEL


def check_result(result: dict, spec: dict) -> bool:
    if result["answer"] is None:
        return False  # hit MAX_ITERATIONS -- never produced an answer
    lowered = result["answer"].lower()
    phrases_ok = all(any(phrase in lowered for phrase in group) for group in spec["checks"])
    if spec.get("expect_no_tools") and result["trace"]:
        return False
    return phrases_ok


def main():
    parser = argparse.ArgumentParser(description="Run the 5 eval tasks and report pass rate + avg iterations")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    parser.add_argument("--verbose", action="store_true", help="Also print each task's [TOOL]/[OBS] trace")
    args = parser.parse_args()

    client = get_client()

    passed = 0
    total_iterations = 0
    for i, spec in enumerate(EVAL_TASKS, start=1):
        result = run_agent(
            client,
            spec["task"],
            model=args.model,
            max_iterations=args.max_iterations,
            auto_approve=True,  # no human at the keyboard during an eval run
            verbose=args.verbose,
        )
        ok = check_result(result, spec)
        passed += ok
        total_iterations += result["iterations"]

        mark = "PASS" if ok else "FAIL"
        tool_names = [t["tool"] for t in result["trace"]]
        print(f"[{mark}] Task {i}: {spec['task']}")
        print(f"  Tools called: {tool_names or 'none'}  |  Iterations: {result['iterations']}  |  Hit cap: {result['hit_cap']}")
        print(f"  Answer: {result['answer']}\n")

    accuracy = passed / len(EVAL_TASKS)
    avg_iterations = total_iterations / len(EVAL_TASKS)
    print(f"--- Summary: {passed}/{len(EVAL_TASKS)} passed ({accuracy:.0%})  |  avg iterations: {avg_iterations:.1f} ---")


if __name__ == "__main__":
    main()
