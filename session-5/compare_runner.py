"""
Session 5 Assignment - Comparison harness: ReAct vs Sequential Pipeline
============================================================================
Runs the same 4 cancellation requests -- one per refund-eligibility branch
in tools.compute_refund() -- through both react_agent.run_react() and
pipeline.run_pipeline(), and reports the numbers the design doc's
comparison table (README.md) is built from: LLM calls, tool calls, wall
latency, and whether each pattern landed on the objectively correct refund
percentage. Same spirit as session-4/eval_runner.py's pass-rate table, but
comparing two *architectures* on one task instead of scoring one agent
against 5 tasks.

Usage:
    python compare_runner.py
"""

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # model replies sometimes use "₹"; Windows' cp1252 console can't print it otherwise
sys.path.append(str(Path(__file__).resolve().parent.parent / "session-4"))  # append, not insert(0): keep this dir's own tools.py resolving first
from llm_client import get_client, DEFAULT_MODEL  # noqa: E402

from pipeline import run_pipeline
from react_agent import run_react
from tools import BOOKINGS, compute_refund

CASES = [
    "Can I cancel my booking MMT7842? What refund would I get?",       # non-refundable -> 0%
    "I need to cancel MMT9911, what's my refund?",                     # refundable, >24h out -> 90%
    "Please cancel MMT1200 immediately, how much do I get back?",      # inside 1h free window -> 100%
    "What refund will I get if I cancel MMT5555?",                     # refundable, <24h out -> 50%
]


def expected_pct(task: str) -> int:
    pnr = re.search(r"\b[A-Z]{2,4}\d{3,5}\b", task.upper()).group(0)
    return compute_refund(BOOKINGS[pnr])["refund_pct"]


def correct(answer: str, pct: int) -> bool:
    """Loose phrase check -- accepts the exact percentage OR the natural-
    language equivalent a draft might use instead ("full refund" for 100%,
    "not eligible"/"no refund" for 0%), so a drafting LLM's wording choice
    doesn't get scored as a wrong *number*."""
    if answer is None:
        return False
    lowered = answer.lower()
    if f"{pct}%" in answer or f"{pct} %" in answer:
        return True
    if pct == 0:
        return any(p in lowered for p in ["no refund", "not eligible for any refund", "not eligible for a refund"])
    if pct == 100:
        return "full refund" in lowered
    return False


def run_pattern(name, fn, client):
    rows = []
    for task in CASES:
        result = fn(client, task, model=DEFAULT_MODEL, verbose=False)
        pct = expected_pct(task)
        ok = correct(result["answer"], pct)
        rows.append({
            "task": task, "llm_calls": result["llm_calls"], "tool_calls": result["tool_calls"],
            "latency_s": result["latency_s"], "correct": ok, "expected_pct": pct,
        })
        print(f"[{name}] {'OK ' if ok else 'MISS'}  llm_calls={result['llm_calls']}  "
              f"tool_calls={result['tool_calls']}  latency={result['latency_s']:.2f}s  "
              f"expected={pct}%  -> {task}")
        print(f"        answer: {result['answer']}")
    return rows


def summarize(name, rows):
    n = len(rows)
    avg_llm = sum(r["llm_calls"] for r in rows) / n
    avg_tool = sum(r["tool_calls"] for r in rows) / n
    avg_latency = sum(r["latency_s"] for r in rows) / n
    correct_n = sum(r["correct"] for r in rows)
    print(f"\n--- {name}: {correct_n}/{n} correct refund % | "
          f"avg LLM calls: {avg_llm:.1f} | avg tool calls: {avg_tool:.1f} | avg latency: {avg_latency:.2f}s ---\n")


def main():
    client = get_client()
    print("=== Pattern 1: ReAct ===")
    react_rows = run_pattern("REACT", run_react, client)
    summarize("ReAct", react_rows)

    print("=== Pattern 4: Sequential Pipeline ===")
    pipeline_rows = run_pattern("PIPE ", run_pipeline, client)
    summarize("Pipeline", pipeline_rows)


if __name__ == "__main__":
    main()
