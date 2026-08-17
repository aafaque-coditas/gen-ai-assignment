"""
Session 4 Assignment - Stretch: Two Agents (Planner delegates to Specialist)
=================================================================================
The smallest version of the orchestrator/specialist pattern:

  Planner    - reasons about the overall goal and breaks it into steps. Its
               only "tool" is delegate_to_specialist(step) -- it has no
               direct access to calculator/get_movie_info/search_docs/
               send_email. It "knows what, not how."
  Specialist - literally agent.run_agent() from the core assignment (same
               tools, same HITL gate, same MAX_ITERATIONS guard), run fresh
               on one delegated step at a time. It "knows how, not why" --
               it never sees the planner's other steps or the original goal.

Delegation is just another tool call from the planner's point of view: the
planner emits delegate_to_specialist(step=...), the code runs a whole
specialist ReAct loop on that step, and the specialist's final answer comes
back as the tool's role:"tool" observation.

Usage:
    python multi_agent.py "How many months did the design system project take, and what is that number times 4?"
"""

import argparse
import json

from agent import run_agent, DEFAULT_MAX_ITERATIONS
from llm_client import get_client, call_model, DEFAULT_MODEL

PLANNER_SYSTEM_PROMPT = (
    "You are a planning agent. You cannot look anything up or compute "
    "anything yourself -- you can only delegate one concrete step at a time "
    "to a specialist agent via the delegate_to_specialist tool, read back "
    "its result, and decide the next step. Break the user's goal into the "
    "smallest number of steps that need delegating, one fact per step. Once "
    "you have every fact you need, answer the user's original question in "
    "plain text with no further delegation."
)

DELEGATE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "delegate_to_specialist",
            "description": (
                "Hand one concrete, self-contained step to the specialist "
                "agent, which has real tools (calculator, movie lookup, "
                "document search, email). Use this for any step that needs "
                "a lookup or computation. Give it enough context to "
                "complete the step on its own -- it does not see the rest "
                "of this conversation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "step": {
                        "type": "string",
                        "description": "The single step to delegate, phrased as a self-contained instruction.",
                    },
                },
                "required": ["step"],
            },
        },
    }
]


def run_multi_agent(
    client,
    goal: str,
    model: str = DEFAULT_MODEL,
    max_planner_iterations: int = 4,
    specialist_max_iterations: int = DEFAULT_MAX_ITERATIONS,
    auto_approve: bool = True,
    verbose: bool = True,
) -> dict:
    """Run the planner loop; each delegate_to_specialist call spins up a full
    specialist ReAct agent on that one step. Returns {"answer",
    "planner_iterations", "delegations"} (each delegation carries the
    specialist's full run_agent() result, including its own trace)."""
    messages = [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {"role": "user", "content": goal},
    ]
    delegations = []

    for iteration in range(1, max_planner_iterations + 1):
        msg = call_model(client, messages, model, temperature=0.0, max_tokens=400, tools=DELEGATE_TOOL)
        messages.append(msg)

        if not msg.tool_calls:
            if verbose:
                print(f"\nPlanner final answer: {msg.content}")
            return {"answer": msg.content, "planner_iterations": iteration, "delegations": delegations}

        for tc in msg.tool_calls:
            step = json.loads(tc.function.arguments).get("step", "")
            if verbose:
                print(f"\n[PLANNER] step {iteration} delegates: {step}")

            result = run_agent(
                client,
                step,
                model=model,
                max_iterations=specialist_max_iterations,
                auto_approve=auto_approve,
                verbose=verbose,
            )
            observation = result["answer"] or "No answer -- specialist hit its own iteration cap."
            if verbose:
                print(f"[PLANNER] specialist returned: {observation}")

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": observation})
            delegations.append({"step": step, "specialist_result": result})

    if verbose:
        print(f"\n>>> Planner stopped: hit its own iteration cap ({max_planner_iterations}).")
    return {"answer": None, "planner_iterations": max_planner_iterations, "delegations": delegations}


def parse_args():
    parser = argparse.ArgumentParser(description="Planner delegates steps to a specialist ReAct agent")
    parser.add_argument("goal", help="The overall goal/question")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    return parser.parse_args()


def main():
    args = parse_args()
    client = get_client()
    run_multi_agent(client, args.goal, model=args.model)


if __name__ == "__main__":
    main()
