# Session 6 Assignment — MCP: Model Context Protocol

```
session-6/
  sandbox/                        <- scoped project folder for the filesystem server demo
    app.py                          (2 TODO comments, for the classic "find all TODOs" example)
    notes.md
  mcp.json                        <- ready-to-paste host config (Cursor / Claude Desktop), least-privilege scoped
  inspect_filesystem_server.py    <- Must do: connects to the real official filesystem server, documents 3 tools
  oncall_data.py                  <- Challenge: simulated internal rotation "API"
  oncall_server.py                <- Challenge: the ~10-line MCP server (the standard minimal example)
  mcp_agent.py                    <- ReAct agent whose tools come from list_tools(), not a hard-coded schema
  router_demo.py                  <- Challenge: session-5's router, extended with an MCP-backed branch
```

## Setup

```bash
cd session-6
pip install -r requirements.txt   # adds mcp[cli] to the usual openai + python-dotenv
```

Also needs Node/npx on PATH (verified: v22.17.1 / npx 11.16.0) — the official
filesystem server ships as an npm package, launched via `npx -y` the same
way the standard `mcp.json` snippet does. Reuses session-4's `llm_client.py`
and session-5's `pipeline.py`/`react_agent.py` directly (imported, not
copied) — see [../session-4/README.md](../session-4/README.md) and
[../session-5/README.md](../session-5/README.md).

## A scoping note before the deliverables

Two of the four "must do" items — **connect it to Cursor or Claude
Desktop's GUI**, and **screenshot it working** — are genuinely outside what
this environment can do: I run in a terminal/IDE-extension context, not
inside Cursor or Claude Desktop, and I won't silently edit *your* personal
app config files without you asking. What I *can* do, and did: install the
real official server, connect to it for real, and produce verified
terminal transcripts of the actual protocol traffic — arguably more
evidence than a screenshot shows, since a screenshot can't prove the
access-scoping actually held (see the "bonus" check below, which a GUI
wouldn't surface at all). [mcp.json](mcp.json) is ready to paste into
Cursor's `Settings > MCP` or `%APPDATA%\Claude\claude_desktop_config.json`
— that GUI click-through and its screenshot are the one step left for you.

## Must do: install + document an official MCP server

**Installed:** `@modelcontextprotocol/server-filesystem` (the official
package, launched via the exact `npx -y ...` form shown in `mcp.json`), scoped to
[sandbox/](sandbox/) only — the "one project folder, not your home
directory" least-privilege principle — not this repo, not the user's home directory.

```bash
python inspect_filesystem_server.py
```

Real, verified output:

```
Connected to the official filesystem MCP server. It offers 14 tools total:
  - read_file, read_text_file, read_media_file, read_multiple_files, write_file,
    edit_file, create_directory, list_directory, list_directory_with_sizes,
    directory_tree, move_file, search_files, get_file_info, list_allowed_directories

[1] list_allowed_directories()  -- verifying least-privilege scoping
    Allowed directories:
    C:\Users\Coditas-Admin\work\gen-ai\session-6\sandbox

[2] list_directory(path='...\sandbox')
    [FILE] app.py
    [FILE] notes.md

[3] read_text_file(path='...\sandbox\app.py') -- then grepping the result for TODOs
    # TODO: validate currency against the supported-currency list before charging
    # TODO: add idempotency key so a retried refund can't double-refund
    (3 TODO comment(s) found in app.py)

[+] read_text_file(path='...\inspect_filesystem_server.py') -- outside the sandbox, should be denied
    is_error=True: Access denied - path outside allowed directories: ...inspect_filesystem_server.py not in ...\sandbox
```

### 3 tools: name, purpose, one real use

| Tool | Purpose | Real use in this run |
|---|---|---|
| `list_allowed_directories` | Reports which folder(s) the server is actually confined to | A security check *before* trusting the server — confirmed the sandbox scoping in `mcp.json` actually held, rather than taking the config's word for it |
| `list_directory` | Lists a folder's contents | "What's in this project" — the same first move a human would make on a new checkout |
| `read_text_file` | Reads one file's full text | Reading `app.py` to find TODO comments (the classic "find all TODO comments in src" example) |

**A real gap worth noting:** the classic "find all TODOs" example implies one call finds every
TODO in a project. This server version's `search_files` only matches
**filenames** against a glob pattern (its schema takes `path` + `pattern`,
no content option) — there's no full-text/content-search tool at all in
this 14-tool set. Finding TODOs actually took `read_text_file` plus doing
the `"TODO" in line` grep in Python myself, one file at a time. A
one-liner description and a specific server version's actual tool list aren't always
the same thing — worth checking `list_tools()` before assuming a
capability exists.

**Bonus verification, not just documentation:** the last call above asked
`read_text_file` for a file one level *above* the sandbox (this very
script) and got `is_error=True` with an explicit "Access denied" message.
The least-privilege scoping isn't just a claim in `mcp.json` — it's
enforced by the server itself, confirmed by trying to break it.

## Challenge: build a server (`get_team_oncall`), then decide who consumes it

### The server ([oncall_server.py](oncall_server.py))

The standard snippet, essentially unchanged:

```python
from mcp.server.mcpserver import MCPServer as FastMCP  # see note below

mcp = FastMCP("oncall")

@mcp.tool()
def get_team_oncall(service: str) -> str:
    """Return the current on-call engineer for a service."""
    return fetch_oncall_from_api(service)

mcp.run()  # stdio by default
```

**One real finding, not hypothetical:** the `mcp` SDK version that installs
today (v2.0.0) renamed the `FastMCP` helper class the original snippet uses
to `MCPServer` — same constructor, same `@tool()` decorator, same
`.run()` defaulting to stdio, just a different import path
(`mcp.server.mcpserver` instead of `mcp.server.fastmcp`). Aliased it back
to `FastMCP` so the code matches the original example exactly. If you followed the
original `from mcp.server.fastmcp import FastMCP` import literally against this
SDK version, it fails with `ModuleNotFoundError` — pin your SDK version if
a snippet needs to survive unchanged.

### Consuming it without a hard-coded tool list ([mcp_agent.py](mcp_agent.py))

```bash
python mcp_agent.py "Who is on-call for payments right now? What's their number?"
```

```
[MCP] Connected. Server offers 1 tool(s): get_team_oncall

[TOOL] step 1  get_team_oncall({"service":"payments"})
[OBS]  (0.17s) Priya Sharma is on-call for payments (since 2026-08-08). Page at +91-98xxx-11223.

Assistant: Priya Sharma is currently on-call for payments. You can page her at +91-98xxx-11223.
```

This is session-5's `react_agent.py` ReAct loop, structurally unchanged,
with the one difference that actually matters:
`TOOL_SCHEMAS` is never written by hand here. It comes from
`await session.list_tools()`, live, over the wire — `mcp_agent.py` never
imports anything named `get_team_oncall`; if the server offered 5 tools
tomorrow, this script's tool list would grow to 5 with no code change.
Verified an unknown-service case too — `get_team_oncall("billing")`
correctly returned "No on-call rotation found... Known services: auth,
checkout, payments" and the model relayed that instead of guessing.

### Which Session 5 pattern should consume it?

**Router into a specialist — not a bigger ReAct agent's tool list.**
`get_team_oncall` is a single, narrow, company-wide lookup — exactly the
"company-wide tool (on-call, deploys) -> build an MCP server" guidance.
The mistake would be bolting it onto one big ops ReAct agent that also has
deploy tools, runbook search, and log queries: the standard warning applies
directly — *"too many connected servers bloats the model's tool list;
connect what the task needs."* A router that classifies intent first and
only then connects the on-call specialist to the on-call MCP server keeps
every agent's tool list narrow and each server's blast radius small if
something goes wrong.

[router_demo.py](router_demo.py) is that answer, written as code —
extends session-5's existing 2-way router (`cancellation` → pipeline,
`general` → ReAct) with a third branch that pulls its tools from an MCP
server, **without modifying a single line of session-5's `router.py`,
`pipeline.py`, or `react_agent.py`**:

```
classify (1 cheap LLM call)
    -> "oncall"       -> mcp_agent.run_mcp_agent()    tools from the oncall MCP server (Session 6)
    -> "cancellation" -> pipeline.run_pipeline()       Session 5, untouched
    -> "general"      -> react_agent.run_react()       Session 5, untouched
```

All three routes verified in one afternoon, no cross-session file edited:

```bash
python router_demo.py "Who is on-call for payments right now?"
# [ROUTER] classified as: oncall
# ... get_team_oncall({"service":"payments"}) -> Priya Sharma, +91-98xxx-11223

python router_demo.py "Can I cancel my booking MMT9911? What refund would I get?"
# [ROUTER] classified as: cancellation
# ... session-5's 5-stage pipeline runs unchanged -> 90% / INR 5580.00

python router_demo.py "What's the capital of France?"
# [ROUTER] classified as: general
# Assistant: The capital of France is Paris.
```

This is made real: *"Each specialist agent or
pipeline stage from Session 5 can now get its tools from an MCP server
instead of hard-coding them. Architecture and plumbing, cleanly
separated."* Session 5 decided the shape (router → specialist); Session 6
only changed where one specialist's tools come from.

## Debrief

**When does MCP beat just writing a Python function?** — Exactly the
second time the same tool gets copied into a new project.
`get_team_oncall` here is a good example either way it's argued — as a
plain function it would need to be re-imported (or re-copied) into every
agent that wants it, each carrying its own copy of the rotation-lookup
logic to keep in sync; as an MCP server, `mcp_agent.py`, `router_demo.py`,
and (per `mcp.json`) Cursor or Claude Desktop can all connect to the exact
same running definition. The `calculator`/`compute_refund` functions
reused via plain Python imports across sessions 4-6 in this repo are the
counterexample: single-process, single-team, no credential to protect —
exactly the "keep it a plain function" guidance, and correctly left that
way rather than wrapped in a server for no reason.

**If you could give your team one MCP server tomorrow, what would it
connect to?** — Given this repo's own running example, the honest answer
is the OTA booking system from Session 5: `get_booking` and `search_policy`
are already real tools multiple things want (the ReAct agent, the pipeline,
a colleague's Slack bot for the same airline). Session 5 has both hard-coded
as local functions imported via `sys.path` tricks between folders — useful
for this assignment, but exactly the "everyone builds their own connector"
problem that MCP exists to solve, if two different real teams needed the same
booking lookup.

**Where did you draw the line on access, and why?** — The filesystem
server got exactly one folder ([sandbox/](sandbox/), not the repo root, not
the home directory) and it was verified, not assumed — the "outside the
sandbox" call at the end of `inspect_filesystem_server.py` came back denied.
The on-call server got read-only-by-construction: `get_team_oncall` has no
write path at all (no `set_oncall`, no way to page anyone from a tool call),
so there was no approval gate to design in the first place — the safest
version of "least privilege" is a tool that structurally cannot do the
dangerous thing, not a tool that can and is merely asked nicely not to
(compare to session-4's `send_email`, which *can* act externally and is
gated behind a human-in-the-loop confirmation for exactly that reason).

## Next session

The finale: giving the app ears and eyes (speech and vision via Whisper),
and proving it works with evaluation.
