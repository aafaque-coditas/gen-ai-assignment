"""
Session 6 Assignment - Challenge: which Session 5 pattern should consume
the new MCP tool?
===========================================================================
The challenge asks: build get_team_oncall as a server (done: oncall_server.py,
mcp_agent.py), then decide which Session 5 pattern would consume it -- a
router specialist, or a ReAct agent?

Answer argued in README.md: **Router into a specialist**, not a bigger
ReAct agent's tool list. This script is that answer, written as code, and
it's also made real: "Each specialist agent or
pipeline stage from Session 5 can now get its tools from an MCP server
instead of hard-coding them." -- extends session-5/router.py's existing
2-way split (cancellation -> pipeline, general -> ReAct) with a 3rd branch
that routes to an MCP-backed specialist instead of a hard-coded tool list:

    classify (1 cheap LLM call)
        -> "oncall"       -> mcp_agent.run_mcp_agent()   (tools from the oncall MCP server, Session 6)
        -> "cancellation" -> session-5 pipeline.run_pipeline()   (Session 5, unchanged)
        -> "general"      -> session-5 react_agent.run_react()   (Session 5, unchanged)

Nothing in session-5/router.py, pipeline.py, or react_agent.py was
modified to add this -- new capability, zero changes to the existing
patterns, exactly the plumbing/architecture split MCP promises.

Usage:
    python router_demo.py "Who is on-call for payments right now?"
    python router_demo.py "Can I cancel my booking MMT9911? What refund would I get?"
    python router_demo.py "What's the capital of France?"
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path

# Order matters: session-4 AND session-5 each have their own tools.py (same
# filename, different content -- session-5's has BOOKINGS/compute_refund,
# session-4's has calculator/get_movie_info). session-5 must resolve first,
# or pipeline.py's own `from tools import ...` would silently pick up
# session-4's tools.py instead and crash on a missing BOOKINGS symbol --
# the same shadowing bug worked around inside session-5/tools.py itself.
sys.path.append(str(Path(__file__).resolve().parent.parent / "session-5"))
sys.path.append(str(Path(__file__).resolve().parent.parent / "session-4"))
from llm_client import get_client, call_model, DEFAULT_MODEL  # noqa: E402
from pipeline import run_pipeline  # noqa: E402 -- session-5, untouched
from react_agent import run_react  # noqa: E402 -- session-5, untouched

from mcp_agent import run_mcp_agent  # session-6

CLASSIFY_SYSTEM_PROMPT = (
    "Classify the user's message as exactly one word:\n"
    "- 'oncall' if they're asking who is on-call, who owns an incident, or who to page for a service\n"
    "- 'cancellation' if they're asking to cancel a booking or what refund they'd get\n"
    "- 'general' for anything else\n"
    "Reply with only that one word, nothing else."
)


def classify(client, task: str, model: str) -> str:
    msg = call_model(
        client,
        [{"role": "system", "content": CLASSIFY_SYSTEM_PROMPT}, {"role": "user", "content": task}],
        model, temperature=0.0, max_tokens=5,
    )
    label = (msg.content or "").strip().lower()
    if "oncall" in label or "on-call" in label or "on_call" in label:
        return "oncall"
    if "cancel" in label:
        return "cancellation"
    return "general"


async def run_router(client, task: str, model: str = DEFAULT_MODEL, verbose: bool = True) -> dict:
    start = time.perf_counter()
    route = classify(client, task, model)
    if verbose:
        print(f"[ROUTER] classified as: {route}")

    if route == "oncall":
        result = await run_mcp_agent(client, sys.executable, ["oncall_server.py"], task, model=model, verbose=verbose)
    elif route == "cancellation":
        result = run_pipeline(client, task, model=model, verbose=verbose)
    else:
        result = run_react(client, task, model=model, verbose=verbose)

    result = dict(result)
    result["route"] = route
    result["latency_s"] = time.perf_counter() - start
    return result


def parse_args():
    parser = argparse.ArgumentParser(description="3-way router: oncall (MCP) | cancellation (pipeline) | general (ReAct)")
    parser.add_argument("task", help="The user's message")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    return parser.parse_args()


def main():
    args = parse_args()
    client = get_client()
    asyncio.run(run_router(client, args.task, model=args.model))


if __name__ == "__main__":
    main()
