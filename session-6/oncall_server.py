"""
Session 6 Assignment - Challenge: build your own MCP server, ~10 lines
===========================================================================
This is a minimal example, typed almost verbatim -- one tool,
"who is on-call for payments right now?", backed by oncall_data.py's
simulated internal rotation API.

The only change from the original snippet: the `mcp` SDK installed here is
v2.0.0, which renamed the FastMCP helper class to MCPServer (same
constructor, same @tool() decorator, same .run() defaulting to stdio) --
aliased back to FastMCP below so the code matches the original example exactly. A
real finding, not a hypothetical one: pin your SDK version if a
snippet needs to survive unchanged.

Run standalone to serve over stdio (what a host like Cursor/Claude Desktop
launches automatically via mcp.json -- see ../mcp.json):
    python oncall_server.py

More usefully, run through mcp_agent.py, which launches this exact file as
a subprocess and talks MCP to it for real:
    python mcp_agent.py "Who is on-call for payments right now?"
"""

from mcp.server.mcpserver import MCPServer as FastMCP

from oncall_data import fetch_oncall_from_api

mcp = FastMCP("oncall")


@mcp.tool()
def get_team_oncall(service: str) -> str:
    """Return the current on-call engineer for a service (e.g. "payments",
    "checkout", "auth"), including their phone number for paging. Use this
    whenever asked who is on-call, who owns an incident, or who to page for
    a given service."""
    return fetch_oncall_from_api(service)


if __name__ == "__main__":
    mcp.run()  # stdio by default
