"""
Session 5 Assignment - Pattern 1 (ReAct) baseline for the OTA cancellation workflow
=======================================================================================
This is deliberately the *same shape* as session-4/agent.py's ReAct loop --
copied and trimmed to this domain's 3 tools -- because the design doc's
whole point is comparing two real, run-able implementations of the same
task, not two paragraphs of theory. See pipeline.py for the recommended
Sequential Pipeline alternative and README.md for the comparison.

Scenario: "Can I cancel this? My PNR is MMT7842." The model does
not know the fare's refund eligibility upfront -- it has to call
get_booking, then search_policy, then (usually) calculator, discovering the
path step by step. Nothing here tells it which tool to call first.

Usage:
    python react_agent.py "Can I cancel my booking MMT7842? What refund would I get?"
    python react_agent.py                                  # interactive
"""

import argparse
import time

import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # model replies sometimes use "₹"; Windows' cp1252 console can't print it otherwise
sys.path.append(str(Path(__file__).resolve().parent.parent / "session-4"))  # append, not insert(0): keep this dir's own tools.py resolving first
from llm_client import get_client, call_model, DEFAULT_MODEL  # noqa: E402 -- reused, not re-implemented

from tools import TOOL_SCHEMAS, dispatch

SYSTEM_PROMPT = (
    "You are an airline customer support assistant. You have tools to look "
    "up a booking by PNR, search the cancellation policy, and do arithmetic. "
    "When a user asks about cancelling or the refund for a booking, look up "
    "the booking first, then find the policy rule that applies to its fare "
    "type and timing, then compute the exact refund amount with the "
    "calculator -- never guess a refund percentage or amount. Once you have "
    "everything you need, answer in plain text with no further tool calls."
)

DEFAULT_MAX_ITERATIONS = 6
MAX_CONTENT_LOG = 300


def _truncate(text: str, limit: int = MAX_CONTENT_LOG) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit] + f"... [{len(text) - limit} more chars]"


def run_react(
    client,
    task: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = 400,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    verbose: bool = True,
) -> dict:
    """Runs the ReAct while-loop. Returns {"answer", "llm_calls", "tool_calls",
    "hit_cap", "latency_s", "trace"} -- the same shape compare_runner.py
    reads from pipeline.run_pipeline() so both patterns score identically."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    trace = []
    llm_calls = 0
    start = time.perf_counter()

    for iteration in range(1, max_iterations + 1):
        step_start = time.perf_counter()
        msg = call_model(client, messages, model, temperature, max_tokens, tools=TOOL_SCHEMAS)
        llm_calls += 1
        step_elapsed = time.perf_counter() - step_start
        messages.append(msg)  # assistant turn before any tool results (session-4's "bug everyone hits")

        if not msg.tool_calls:
            if verbose:
                print(f"\nAssistant: {msg.content}")
            return {
                "answer": msg.content, "llm_calls": llm_calls, "tool_calls": len(trace),
                "hit_cap": False, "latency_s": time.perf_counter() - start, "trace": trace,
            }

        for tc in msg.tool_calls:
            if verbose:
                print(f"[TOOL] step {iteration} ({step_elapsed:.2f}s)  {tc.function.name}({tc.function.arguments})")
            result = dispatch(tc.function.name, tc.function.arguments)
            if verbose:
                print(f"[OBS]  {_truncate(result)}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            trace.append({"iteration": iteration, "tool": tc.function.name, "result": result})

    if verbose:
        print(f"\n>>> Stopped: hit MAX_ITERATIONS ({max_iterations}) without a final answer.")
    return {
        "answer": None, "llm_calls": llm_calls, "tool_calls": len(trace),
        "hit_cap": True, "latency_s": time.perf_counter() - start, "trace": trace,
    }


def run_interactive(client, args):
    print("ReAct OTA Assistant -- type 'quit' or 'exit' to leave\n")
    while True:
        try:
            task = input("Task: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if not task:
            continue
        if task.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break
        run_react(client, task, args.model, args.temperature, args.max_tokens, args.max_iterations)
        print()


def parse_args():
    parser = argparse.ArgumentParser(description="Pattern 1 (ReAct) baseline: OTA cancellation Q&A")
    parser.add_argument("task", nargs="?", help="Task/question to run (omit for interactive mode)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=400)
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    return parser.parse_args()


def main():
    args = parse_args()
    client = get_client()
    if args.task is None:
        run_interactive(client, args)
        return
    run_react(client, args.task, args.model, args.temperature, args.max_tokens, args.max_iterations)


if __name__ == "__main__":
    main()
