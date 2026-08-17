"""
Final Assignment - Save-episode ReAct agent (MCP tool via a real tool-calling loop)
========================================================================================
Two of the checklist's session requirements are the same piece of code here,
exactly like session-6's mcp_agent.py:

  Session 4 - "a tool-calling loop (Thought, Action, Observation), correct
  tool_call_id handling, every tool call logged, and an iteration cap."
  Session 6 - "at least one tool or resource... consumed over MCP, not just
  a hard-coded function call."

The model is handed whatever tool(s) podcast_server.py's list_tools()
actually reports -- never a hard-coded schema -- and decides for itself to
call save_podcast_output with the episode name, transcript, and audio path
it was given. MAX_ITERATIONS caps the loop the same way session-4/5/6's
ReAct loops do.
"""

import json
import sys
import time
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from llm_client import call_with_tools, DEFAULT_MODEL

SESSION_DIR = Path(__file__).resolve().parent
MCP_SERVER_PATH = SESSION_DIR / "podcast_server.py"

SYSTEM_PROMPT = (
    "You are a podcast-publishing assistant. You have access to whatever save tool "
    "an MCP server has made available to you. When asked to save a finished episode, "
    "call that tool with the exact episode name and the two file paths you were "
    "given -- never invent or alter any of those three values, and never ask for or "
    "restate the file contents yourself. Once the tool call succeeds, confirm in "
    "plain text with no further tool calls."
)

DEFAULT_MAX_ITERATIONS = 3
MAX_CONTENT_LOG = 200


def _truncate(text: str, limit: int = MAX_CONTENT_LOG) -> str:
    text = str(text)
    return text if len(text) <= limit else text[:limit] + f"... [{len(text) - limit} more chars]"


def _mcp_tools_to_openai_schema(mcp_tools) -> list:
    """Turn whatever the server just told us it can do into the
    function-calling schema the chat API expects. Nothing here is known
    ahead of time -- copied from session-6's mcp_agent.py."""
    return [
        {"type": "function", "function": {"name": t.name, "description": t.description or "", "parameters": t.input_schema}}
        for t in mcp_tools
    ]


def _extract_text(call_tool_result) -> str:
    parts = [b.text for b in call_tool_result.content if getattr(b, "type", None) == "text"]
    return "\n".join(parts) if parts else ""


async def run_save_agent(
    client,
    episode_name: str,
    transcript_path: str,
    audio_path: str,
    model: str = DEFAULT_MODEL,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    verbose: bool = True,
) -> dict:
    """Runs the ReAct while-loop against podcast_server.py over MCP.
    transcript_path/audio_path point at files already written to disk (the
    rendered transcript .txt and the TTS .wav) -- the model only ever
    handles short paths, never the file contents themselves (see
    podcast_server.py's docstring for the truncation bug this avoids).
    Returns {"answer", "iterations", "trace", "token_log"}."""
    params = StdioServerParameters(command=sys.executable, args=[str(MCP_SERVER_PATH)])
    token_log = []

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            discovered = (await session.list_tools()).tools
            tool_schemas = _mcp_tools_to_openai_schema(discovered)
            if verbose:
                names = ", ".join(t.name for t in discovered)
                print(f"[MCP] Connected. Server offers {len(discovered)} tool(s): {names}")

            task = (
                f"Save this finished episode. episode_name={episode_name!r}, "
                f"transcript_source_path={transcript_path!r}, audio_source_path={audio_path!r}."
            )
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task},
            ]
            trace = []

            for iteration in range(1, max_iterations + 1):
                msg, tokens = call_with_tools(client, messages, model=model, temperature=0.0, max_tokens=300, tools=tool_schemas)
                token_log.append({"stage": f"save_agent_iter{iteration}", **tokens})
                # The assistant turn (with its tool_calls) must be appended
                # BEFORE any tool results, or the model can't correlate them
                # next turn -- the classic pitfall session-4's README flags.
                messages.append(msg)

                if not msg.tool_calls:
                    if verbose:
                        print(f"\nAssistant: {msg.content}")
                    return {"answer": msg.content, "iterations": iteration, "trace": trace, "token_log": token_log}

                for tc in msg.tool_calls:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    if verbose:
                        print(f"[TOOL] step {iteration}  {tc.function.name}({_truncate(tc.function.arguments)})")
                    start = time.perf_counter()
                    result = await session.call_tool(tc.function.name, args)
                    elapsed = time.perf_counter() - start
                    text = _extract_text(result)
                    if verbose:
                        print(f"[OBS]  ({elapsed:.2f}s) {_truncate(text)}")
                    # tool_call_id correlates this observation to the exact
                    # tool_call the assistant just issued.
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})
                    trace.append({"iteration": iteration, "tool": tc.function.name, "result": text})

            if verbose:
                print(f"\n>>> Stopped: hit MAX_ITERATIONS ({max_iterations}) without a final answer.")
            return {"answer": None, "iterations": max_iterations, "trace": trace, "token_log": token_log}
