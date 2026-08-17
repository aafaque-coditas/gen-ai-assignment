"""
Session 6 Assignment - Must do: install + document an official MCP server
==============================================================================
"Install one official MCP server, connect it, document 3 tools (name,
purpose, one real use), screenshot it working."

This script IS that connection, just made from a small Python client
instead of Cursor/Claude Desktop's GUI -- the actual protocol traffic a
screenshot can only show a rendering of. It launches the real, official
`@modelcontextprotocol/server-filesystem` package (the exact npx command
from the standard mcp.json snippet -- see mcp.json in this folder) via stdio,
scoped ONLY to ./sandbox (the "one project folder, not your home
directory" least-privilege principle), lists every tool it actually offers, and calls three of them
for real against the sandbox files committed alongside this script.

See README.md for the "3 tools: name, purpose, one real use" write-up this
run's output feeds, and for why a terminal transcript stands in for a
screenshot here.

Usage:
    python inspect_filesystem_server.py
"""

import asyncio
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SANDBOX = str(Path(__file__).resolve().parent / "sandbox")
SERVER_COMMAND = "npx"
SERVER_ARGS = ["-y", "@modelcontextprotocol/server-filesystem", SANDBOX]


def _text(result) -> str:
    return "\n".join(b.text for b in result.content if getattr(b, "type", None) == "text")


async def main():
    params = StdioServerParameters(command=SERVER_COMMAND, args=SERVER_ARGS)
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = (await session.list_tools()).tools
            print(f"Connected to the official filesystem MCP server. It offers {len(tools)} tools total:")
            for t in tools:
                print(f"  - {t.name}")

            # --- Tool 1: list_allowed_directories -----------------------
            # Purpose: report the sandbox this server is actually confined
            # to. Real use: a security check BEFORE trusting a server --
            # confirms the "one project folder, not your home
            # directory" least-privilege principle actually held, rather than taking the mcp.json
            # config's word for it.
            print("\n[1] list_allowed_directories()  -- verifying least-privilege scoping")
            result = await session.call_tool("list_allowed_directories", {})
            print(f"    {_text(result)}")

            # --- Tool 2: list_directory -----------------------------------
            # Purpose: list a folder's contents. Real use: "what's in this
            # project" -- the same first move a human would make.
            print(f"\n[2] list_directory(path={SANDBOX!r})")
            result = await session.call_tool("list_directory", {"path": SANDBOX})
            print(f"    {_text(result)}")

            # --- Tool 3: read_text_file ------------------------------------
            # Purpose: read one file's contents. Real use: the classic "find
            # all TODO comments in src" example -- except this server version has
            # no content-search tool (search_files only matches FILENAMES,
            # not file contents, confirmed by its schema), so finding TODOs
            # actually takes read_text_file + doing the grep yourself, one
            # file at a time. A real gap between a one-liner description and
            # what a specific server version actually ships.
            app_path = str(Path(SANDBOX) / "app.py")
            print(f"\n[3] read_text_file(path={app_path!r}) -- then grepping the result for TODOs")
            result = await session.call_tool("read_text_file", {"path": app_path})
            content = _text(result)
            todos = [line.strip() for line in content.splitlines() if "TODO" in line]
            for line in todos:
                print(f"    {line}")
            print(f"    ({len(todos)} TODO comment(s) found in app.py)")

            # --- Bonus: prove the scoping in [1] is actually enforced, not
            # just reported. Ask for a file one level ABOVE the sandbox
            # (this very script) and confirm the server refuses.
            outside_path = str(Path(__file__).resolve())
            print(f"\n[+] read_text_file(path={outside_path!r}) -- outside the sandbox, should be denied")
            result = await session.call_tool("read_text_file", {"path": outside_path})
            print(f"    is_error={result.is_error}: {_text(result)}")


if __name__ == "__main__":
    asyncio.run(main())
