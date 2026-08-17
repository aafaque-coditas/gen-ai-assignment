"""
Session 6 Assignment - ReAct agent whose tools come from an MCP server
===========================================================================
This is session-4/session-5's ReAct loop, unchanged in shape, with exactly
one thing different: TOOL_SCHEMAS is never written by hand here. Compare
to session-5/react_agent.py's `from tools import TOOL_SCHEMAS` (a python
list baked into that file) -- here the schemas come from
`await session.list_tools()`, live, over the MCP protocol, from whatever
server was launched. This is the whole point of MCP made concrete:
"You do not hard-code them in your script. The server tells the AI what
it can do, automatically."

The host+client role usually described as "you do not write this" (a
real host like Cursor bundles it) is written out here on purpose, in
~20 lines, so the protocol isn't a black box: spawn the server as a
subprocess over stdio, `initialize()`, `list_tools()`, and `call_tool()`
whenever the model asks -- the same 5-step "who does what" sequence a
host/client implementation follows, just with this script playing host+client at once instead of
Cursor.

Usage:
    python mcp_agent.py "Who is on-call for payments right now?"
    python mcp_agent.py "Who do I page for the checkout service?"
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

sys.path.append(str(Path(__file__).resolve().parent.parent / "session-4"))
from llm_client import get_client, call_model, DEFAULT_MODEL  # noqa: E402

SYSTEM_PROMPT = (
    "You are an on-call assistant. You have access to whatever tools an "
    "MCP server has made available to you -- use them whenever a question "
    "needs a lookup you can't answer from general knowledge. Once you have "
    "everything you need, answer in plain text with no further tool calls."
)

DEFAULT_MAX_ITERATIONS = 4
MAX_CONTENT_LOG = 300


def _truncate(text: str, limit: int = MAX_CONTENT_LOG) -> str:
    text = str(text)
    return text if len(text) <= limit else text[: limit] + f"... [{len(text) - limit} more chars]"


def _mcp_tools_to_openai_schema(mcp_tools) -> list:
    """The one function this pattern needs that session-4/5's inline tools
    never did: turn whatever the server just told us it can do into the
    function-calling schema the chat API expects. No tool here is known
    ahead of time -- this list is only as long as whatever the connected
    server happens to expose today."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.input_schema,
            },
        }
        for t in mcp_tools
    ]


def _extract_text(call_tool_result) -> str:
    """MCP tool results come back as a list of content blocks (text, image,
    etc.) -- join the text ones, same idea as session-4's dispatch()
    returning a plain string the model can read as its observation."""
    parts = [block.text for block in call_tool_result.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts) if parts else json.dumps(call_tool_result.structured_content)


async def run_mcp_agent(
    client,
    server_command: str,
    server_args: list,
    task: str,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    max_tokens: int = 300,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    verbose: bool = True,
) -> dict:
    params = StdioServerParameters(command=server_command, args=server_args)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            discovered = (await session.list_tools()).tools
            tool_schemas = _mcp_tools_to_openai_schema(discovered)
            if verbose:
                names = ", ".join(t.name for t in discovered)
                print(f"[MCP] Connected. Server offers {len(discovered)} tool(s): {names}\n")

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task},
            ]
            trace = []

            for iteration in range(1, max_iterations + 1):
                # llm_client.call_model is a plain blocking call (session-4's
                # sync OpenAI client) -- run it inline rather than reaching
                # for run_in_executor; it's the only thing on the event loop.
                msg = call_model(client, messages, model, temperature, max_tokens, tools=tool_schemas)
                messages.append(msg)

                if not msg.tool_calls:
                    if verbose:
                        print(f"\nAssistant: {msg.content}")
                    return {"answer": msg.content, "iterations": iteration, "trace": trace}

                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    if verbose:
                        print(f"[TOOL] step {iteration}  {tc.function.name}({tc.function.arguments})")
                    start = time.perf_counter()
                    result = await session.call_tool(tc.function.name, args)
                    elapsed = time.perf_counter() - start
                    text = _extract_text(result)
                    if verbose:
                        print(f"[OBS]  ({elapsed:.2f}s) {_truncate(text)}")
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
                    trace.append({"iteration": iteration, "tool": tc.function.name, "result": text})

            if verbose:
                print(f"\n>>> Stopped: hit MAX_ITERATIONS ({max_iterations}) without a final answer.")
            return {"answer": None, "iterations": max_iterations, "trace": trace}


def parse_args():
    parser = argparse.ArgumentParser(description="ReAct agent that sources its tools from an MCP server")
    parser.add_argument("task", help="The question to ask")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Model name (default: {DEFAULT_MODEL})")
    parser.add_argument(
        "--server", nargs="+", default=[sys.executable, "oncall_server.py"],
        help="Command to launch the MCP server, e.g. --server python oncall_server.py",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    client = get_client()
    asyncio.run(run_mcp_agent(client, args.server[0], args.server[1:], args.task, model=args.model))


if __name__ == "__main__":
    main()
