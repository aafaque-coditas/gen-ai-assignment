"""
Session 4 Assignment - ReAct Agent Loop (built from scratch)
================================================================
No framework -- a plain `for` loop against the raw chat.completions API,
the way session-1/chatbot.py's CLI loop is now a ReAct loop
instead of a chat loop.

Core requirement:
  - 3+ real tools with real descriptions -- see tools.py: calculator,
    get_movie_info, search_docs (send_email is a 4th, deliberately
    dangerous tool that exists for the HITL stretch goal below)
  - The ReAct while-loop: Thought (implicit in the model's reasoning) ->
    Action (tool_calls) -> Observation (role:"tool") -> repeat or stop
  - Every tool call and its observation is logged ([TOOL]/[OBS])
  - MAX_ITERATIONS is a hard cap -- verified to actually stop the loop
    (see README's "Verified: MAX_ITERATIONS actually stops the loop")

Stretch goals also live here:
  - search_docs is wired straight to Session 3's real index
  - send_email is gated behind a human-in-the-loop confirmation

Usage:
    python agent.py "What is 197 * 43?"
    python agent.py "How many months did the design system project take, and what is that number times 4?"
    python agent.py "Email a summary of the design system doc to alice@acme.com"
    python agent.py "..." --max-iterations 1     # force-hit the cap
    python agent.py "..." --yes                  # auto-approve HITL gates (scripts/eval)
    python agent.py                               # interactive
"""

import argparse
import json
import time

from llm_client import get_client, call_model, embed_texts, DEFAULT_MODEL
from tools import TOOL_SCHEMAS, DANGEROUS_TOOLS, dispatch

SYSTEM_PROMPT = (
    "You are a helpful assistant with access to tools: a calculator, a movie "
    "info lookup, a search over an internal technical case study document, "
    "and an email sender. Use a tool whenever the question needs one -- "
    "never guess a computation, a movie fact, or a document detail you can "
    "look up instead. If a question needs more than one fact, call tools "
    "one at a time and use each result before deciding the next step. Once "
    "you have everything you need, answer in plain text with no further "
    "tool calls."
)

DEFAULT_MAX_ITERATIONS = 6
MAX_CONTENT_LOG = 300


def _truncate(text: str, limit: int = MAX_CONTENT_LOG) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit] + f"... [{len(text) - limit} more chars]"


def run_agent(
    client,
    task: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = 500,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    auto_approve: bool = False,
    embed_fn=embed_texts,
    verbose: bool = True,
) -> dict:
    """Run the ReAct loop to completion or until max_iterations is hit.

    Returns {"answer", "iterations", "hit_cap", "trace"} -- used by both the
    CLI below and eval_runner.py's pass-rate/avg-iterations scoring.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    trace = []

    for iteration in range(1, max_iterations + 1):
        start = time.perf_counter()
        msg = call_model(client, messages, model, temperature, max_tokens, tools=TOOL_SCHEMAS)
        elapsed = time.perf_counter() - start
        # The assistant turn (with its tool_calls) must be appended BEFORE
        # any tool results, or the model can't correlate them next turn --
        # a classic pitfall when building an agent loop from scratch.
        messages.append(msg)

        if not msg.tool_calls:
            if verbose:
                print(f"\nAssistant: {msg.content}")
            return {"answer": msg.content, "iterations": iteration, "hit_cap": False, "trace": trace}

        for tc in msg.tool_calls:
            if verbose:
                print(f"[TOOL] step {iteration} ({elapsed:.2f}s)  {tc.function.name}({tc.function.arguments})")

            if tc.function.name in DANGEROUS_TOOLS and not auto_approve:
                approved = (
                    input(f"  Agent wants to run {tc.function.name}({tc.function.arguments}). Allow? [y/n] ")
                    .strip()
                    .lower()
                    == "y"
                )
                if not approved:
                    result = json.dumps({"status": "cancelled", "reason": "denied by human-in-the-loop gate"})
                    if verbose:
                        print(f"[OBS]  {_truncate(result)}")
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                    trace.append(
                        {"iteration": iteration, "tool": tc.function.name,
                         "arguments": tc.function.arguments, "result": result, "approved": False}
                    )
                    continue

            result = dispatch(tc.function.name, tc.function.arguments, client, embed_fn)
            if verbose:
                print(f"[OBS]  {_truncate(result)}")
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            trace.append(
                {"iteration": iteration, "tool": tc.function.name,
                 "arguments": tc.function.arguments, "result": result, "approved": True}
            )

    if verbose:
        print(f"\n>>> Stopped: hit MAX_ITERATIONS ({max_iterations}) without a final answer.")
    return {"answer": None, "iterations": max_iterations, "hit_cap": True, "trace": trace}


def run_interactive(client, args):
    print("ReAct Agent -- type 'quit' or 'exit' to leave\n")
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
        run_agent(client, task, args.model, args.temperature, args.max_tokens, args.max_iterations, args.yes)
        print()


def parse_args():
    parser = argparse.ArgumentParser(description="Session 4 assignment: ReAct agent with tools")
    parser.add_argument("task", nargs="?", help="Task/question to run (omit for interactive mode)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--temperature", type=float, default=0.0, help="0 = deterministic, higher = more varied")
    parser.add_argument("--max-tokens", type=int, default=500, help="Max tokens per model reply")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Hard cap on ReAct loop steps (default: {DEFAULT_MAX_ITERATIONS})",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Auto-approve human-in-the-loop gates instead of prompting (for scripts/eval)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    client = get_client()
    if args.task is None:
        run_interactive(client, args)
        return
    run_agent(client, args.task, args.model, args.temperature, args.max_tokens, args.max_iterations, args.yes)


if __name__ == "__main__":
    main()
