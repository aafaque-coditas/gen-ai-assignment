"""
Session 5 Assignment - Pattern 4 (Sequential Pipeline), the recommended architecture
========================================================================================
Same task as react_agent.py -- "can I cancel booking X, what's my refund" --
but wired as a fixed chain your code controls, per the general principle
that the model never decides whether to skip a stage or which tool to call
next. Every request
walks the same 5 stages in the same order:

    extract_pnr (code) -> get_booking (code) -> search_policy (code)
        -> compute_refund (code)      <- the money math is a rule, not a guess
        -> draft_reply (1 LLM call)   <- only step that needs a model at all
        -> format_response (code)

This is the design doc's recommendation over react_agent.py's ReAct pattern:
the refund percentage is a compliance-sensitive number (real money, real
policy), so it comes from compute_refund()'s pure business rule every single
time, not from a model reading policy prose and doing arithmetic itself. The
LLM's only job is turning already-correct facts into a friendly sentence --
it cannot get the number wrong because it never computes it.

Usage:
    python pipeline.py "Can I cancel my booking MMT7842? What refund would I get?"
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")  # model replies sometimes use "₹"; Windows' cp1252 console can't print it otherwise
sys.path.append(str(Path(__file__).resolve().parent.parent / "session-4"))  # append, not insert(0): keep this dir's own tools.py resolving first
from llm_client import get_client, call_model, DEFAULT_MODEL  # noqa: E402

from tools import BOOKINGS, get_booking, search_policy, compute_refund  # noqa: E402

PNR_PATTERN = re.compile(r"\b[A-Z]{2,4}\d{3,5}\b")

DRAFT_SYSTEM_PROMPT = (
    "You write short, friendly airline customer-support replies. You are given "
    "already-verified facts (booking details and the exact refund decision) -- "
    "restate them clearly and warmly. Never invent or adjust any number given "
    "to you; use the refund percentage and amount exactly as provided."
)


def _stage_log(verbose, label, detail):
    if verbose:
        print(f"[STAGE] {label}: {detail}")


def run_pipeline(
    client,
    task: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.2,
    max_tokens: int = 250,
    verbose: bool = True,
) -> dict:
    """Runs the fixed 5-stage chain. Returns the same result shape as
    react_agent.run_react() -- {"answer", "llm_calls", "tool_calls",
    "hit_cap", "latency_s", "trace"} -- so compare_runner.py can score both
    patterns identically. hit_cap is repurposed here as "pipeline could not
    proceed" (no MAX_ITERATIONS concept exists in a fixed chain)."""
    start = time.perf_counter()
    trace = []

    # Stage 1: extract_pnr -- code, not a model call. A pipeline's whole
    # premise is that it doesn't need an LLM to find something this
    # mechanical; this is also exactly where the pattern's rigidity shows --
    # if the user's message has no PNR-shaped token, this pipeline cannot
    # proceed at all (see README's "Avoid when" row).
    match = PNR_PATTERN.search(task.upper())
    _stage_log(verbose, "1/5 extract_pnr", match.group(0) if match else "no PNR found")
    if not match:
        return {
            "answer": None, "llm_calls": 0, "tool_calls": 0, "hit_cap": True,
            "latency_s": time.perf_counter() - start, "trace": trace,
            "error": "No PNR found in the message -- this pipeline only handles cancellation requests with a PNR.",
        }
    pnr = match.group(0)

    # Stage 2: get_booking -- code.
    booking_json = get_booking(pnr)
    booking = json.loads(booking_json)
    trace.append({"stage": "get_booking", "result": booking})
    _stage_log(verbose, "2/5 get_booking", booking_json)
    if "error" in booking:
        return {
            "answer": None, "llm_calls": 0, "tool_calls": 1, "hit_cap": True,
            "latency_s": time.perf_counter() - start, "trace": trace, "error": booking["error"],
        }

    # Stage 3: search_policy -- code. The pipeline already knows the fare
    # type and timing from stage 2, so it can build a precise query itself
    # instead of asking a model to guess what to search for. Timing only
    # matters for refundable fares -- appending it unconditionally would
    # make a non-refundable query match on "before departure"/"24 hour" and
    # retrieve the wrong clause, since "refundable" is a substring of
    # "non-refundable" for this toy keyword scorer.
    if booking["booked_hours_ago"] <= 1:
        topic = "free cancellation within 1 hour of booking, grace window"
    elif booking["fare_type"] == "non-refundable":
        topic = "non-refundable fare cancellation, no refund"
    elif booking["departs_in_hours"] <= 24:
        topic = "refundable fare cancelled within 24 hours of departure"
    else:
        topic = "refundable fare cancelled more than 24 hours before departure, early"
    policy_json = search_policy(topic, k=1)
    policy = json.loads(policy_json)
    trace.append({"stage": "search_policy", "result": policy})
    _stage_log(verbose, "3/5 search_policy", policy_json)

    # Stage 4: compute_refund -- code. The one number that must be exact.
    refund = compute_refund(booking)
    trace.append({"stage": "compute_refund", "result": refund})
    _stage_log(verbose, "4/5 compute_refund", json.dumps(refund))

    # Stage 5: draft_reply -- the pipeline's ONLY LLM call.
    prompt = (
        f"Booking {booking['pnr']} ({booking['route']}, a {booking['fare_type']} fare, "
        f"{booking['booked_hours_ago']}h ago). Refund decision: {refund['refund_pct']}% "
        f"= INR {refund['refund_amount_inr']}, because {refund['reason']}. "
        f"Write a 2-3 sentence reply to the customer."
    )
    step_start = time.perf_counter()
    msg = call_model(
        client,
        [{"role": "system", "content": DRAFT_SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        model, temperature, max_tokens,
    )
    step_elapsed = time.perf_counter() - step_start
    _stage_log(verbose, "5/5 draft_reply", f"({step_elapsed:.2f}s) {msg.content}")

    # Stage 6: format_response -- code.
    response = {"pnr": booking["pnr"], **{k: v for k, v in refund.items() if k != "pnr"}, "reply": msg.content}
    if verbose:
        print(f"\nAssistant: {msg.content}")

    return {
        "answer": msg.content, "llm_calls": 1, "tool_calls": 2, "hit_cap": False,
        "latency_s": time.perf_counter() - start, "trace": trace, "structured": response,
    }


def parse_args():
    parser = argparse.ArgumentParser(description="Pattern 4 (Sequential Pipeline): OTA cancellation, fixed chain")
    parser.add_argument("task", help="The user's cancellation request (must contain a PNR, e.g. MMT7842)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    return parser.parse_args()


def main():
    args = parse_args()
    client = get_client()
    result = run_pipeline(client, args.task, model=args.model)
    if result.get("error"):
        print(f"\n>>> Pipeline could not proceed: {result['error']}")
    else:
        print(f"\nStructured response: {json.dumps(result['structured'], indent=2)}")


if __name__ == "__main__":
    main()
