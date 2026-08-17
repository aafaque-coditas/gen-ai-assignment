"""
Session 5 Assignment - Stretch: hybrid, Router into a Pipeline for one category
====================================================================================
The "Combine patterns" guidance, made concrete: "Router into a ReAct
specialist... Production systems are hybrids." Here it's a router in front
of the two patterns already built:

    classify (1 cheap LLM call)
        -> "cancellation"  -> pipeline.run_pipeline()   (Pattern 4, fixed chain)
        -> "general"       -> react_agent.run_react()   (Pattern 1, flexible)

Rationale: the Sequential Pipeline is fast and cheap but rigid -- it only
handles "cancel booking X" requests with a PNR in them (see pipeline.py's
Stage 1). Anything else ("what's the baggage allowance", "is MMT9911
refundable" with no cancellation intent) needs the ReAct agent's ability to
improvise. The router keeps the cheap, auditable path for the high-volume
case and reserves the expensive, flexible path for everything else --
exactly the "right pattern for the job" argument, applied twice in
one system.

Usage:
    python router.py "Can I cancel my booking MMT7842? What refund would I get?"
    python router.py "Is booking MMT9911 a refundable fare?"
"""

import argparse
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # model replies sometimes use "₹"; Windows' cp1252 console can't print it otherwise
sys.path.append(str(Path(__file__).resolve().parent.parent / "session-4"))  # append, not insert(0): keep this dir's own tools.py resolving first
from llm_client import get_client, call_model, DEFAULT_MODEL  # noqa: E402

from pipeline import run_pipeline
from react_agent import run_react

CLASSIFY_SYSTEM_PROMPT = (
    "Classify the user's message as exactly one word: 'cancellation' if they "
    "are asking to cancel a specific booking or asking what refund they'd "
    "get for cancelling it, otherwise 'general'. Reply with only that one "
    "word, nothing else."
)


def classify(client, task: str, model: str) -> str:
    msg = call_model(
        client,
        [{"role": "system", "content": CLASSIFY_SYSTEM_PROMPT}, {"role": "user", "content": task}],
        model, temperature=0.0, max_tokens=5,
    )
    label = (msg.content or "").strip().lower()
    return "cancellation" if "cancel" in label else "general"


def run_hybrid(client, task: str, model: str = DEFAULT_MODEL, verbose: bool = True) -> dict:
    start = time.perf_counter()
    route = classify(client, task, model)
    if verbose:
        print(f"[ROUTER] classified as: {route}")

    if route == "cancellation":
        result = run_pipeline(client, task, model=model, verbose=verbose)
    else:
        result = run_react(client, task, model=model, verbose=verbose)

    result = dict(result)
    result["route"] = route
    result["llm_calls"] = result.get("llm_calls", 0) + 1  # +1 for the classify call itself
    result["latency_s"] = time.perf_counter() - start
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Hybrid: router into pipeline for cancellations, ReAct otherwise")
    parser.add_argument("task", help="The user's message")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    return parser.parse_args()


def main():
    args = parse_args()
    client = get_client()
    run_hybrid(client, args.task, model=args.model)


if __name__ == "__main__":
    main()
