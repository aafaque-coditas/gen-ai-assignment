"""
Session 4 Assignment - Tool definitions + dispatch
======================================================

Three required tools plus one deliberately "dangerous" one for the
human-in-the-loop stretch goal. Per the principle that a tool's description
is the interface the model reasons from: one tool = one responsibility,
every description says "Use this when...", units/formats are spelled out,
and every tool returns structured text the model can reason about.

  calculator    - safe arithmetic, no external call. Real tool (not a toy
                  "add two numbers" stub): parses with `ast`, so it can't be
                  used to run arbitrary Python.
  get_movie_info - live OMDb lookup, same API + auto-detected demo token as
                  session-2/task-1-sentiment/sentiment.py.
  search_docs   - RAG-as-a-tool: wired directly to Session 3's
                  vector_store.py and index.json, no duplicated data.
  send_email    - DANGEROUS_TOOLS member. Never actually sends anything --
                  simulated by appending to outbox.log -- but it stands in
                  for any real destructive/side-effecting action, so the
                  human-in-the-loop gate in agent.py has something to guard.
"""

import ast
import json
import operator
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SESSION_DIR = Path(__file__).resolve().parent
SESSION_3_DIR = SESSION_DIR.parent / "session-3"
OUTBOX_PATH = SESSION_DIR / "outbox.log"

# search_docs needs Session 3's VectorStore class and index -- imported
# directly rather than copied, reusing the same code as Session 3.
sys.path.insert(0, str(SESSION_3_DIR))
from vector_store import VectorStore  # noqa: E402

# Tools whose side effects are irreversible / external. agent.py checks this
# set before dispatching and gates behind a human confirmation.
DANGEROUS_TOOLS = {"send_email"}

OMDB_URL = "https://www.omdbapi.com/demo.aspx/"
_SEARCH_INDEX_CACHE = {}  # index path -> VectorStore, loaded once per run


# ---------------------------------------------------------------------------
# Tool schemas -- sent to the API as `tools=[...]`. The description IS the
# prompt the model uses to decide whether/when to call this tool.
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Evaluate a basic arithmetic expression (+, -, *, /, **, "
                "parentheses, decimals). Use this whenever the user's "
                "question requires a numeric computation -- do not compute "
                "arithmetic yourself, call this tool instead, even for "
                "simple-looking sums, so the answer is exact rather than "
                "guessed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": 'The expression to evaluate, e.g. "197 * 43" or "(150 - 45) / 15".',
                    },
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_movie_info",
            "description": (
                "Look up a movie's metadata from the OMDb database by title. "
                "Use this when the user asks about a specific film's rating, "
                "plot, genre, or reception. A single call returns ALL "
                "available fields at once (year, genre, plot, IMDb rating, "
                "awards) -- never call this more than once for the same "
                "movie, even if the user asked about several of its fields. "
                "Do NOT use this for questions unrelated to movies. Returns "
                "'not found' if OMDb has no match."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": 'Movie title, e.g. "Inception".',
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": (
                "Search the internal technical case study document (the "
                "design system project write-up) for relevant passages. Use "
                "this when the user asks about the design system project, "
                "its timeline, tech stack, documentation, or distribution -- "
                "anything that would be in that internal doc. Do NOT use "
                "this for general knowledge questions. Returns the top-k "
                "passages with source page and similarity score."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question or topic to search for in the document.",
                    },
                    "k": {
                        "type": "integer",
                        "description": "How many passages to return (default 3, max 10).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": (
                "Send an email to a recipient. Use this ONLY when the user "
                "explicitly asks to send/email something to someone. This is "
                "a destructive, external-facing action -- it will prompt a "
                "human for confirmation before it actually runs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": 'Recipient address, e.g. "alice@acme.com".'},
                    "subject": {"type": "string", "description": "Email subject line."},
                    "body": {"type": "string", "description": "Email body text."},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# calculator -- ast-based safe evaluator. No eval()/exec(): only numbers and
# +-*/**% (plus unary +/-) are accepted, so a malicious/garbled expression
# can't execute arbitrary Python -- validate before dispatch.
# ---------------------------------------------------------------------------
_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.FloorDiv: operator.floordiv,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(node):
    if isinstance(node, ast.Expression):
        return _safe_eval(node.body)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"Unsupported constant: {node.value!r}")
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_safe_eval(node.left), _safe_eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_safe_eval(node.operand))
    raise ValueError(f"Disallowed expression element: {type(node).__name__}")


def calculator(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        result = _safe_eval(tree)
    except (SyntaxError, ValueError, ZeroDivisionError, TypeError) as e:
        return f"ERROR: could not evaluate '{expression}': {e}"
    return json.dumps({"expression": expression, "result": result})


# ---------------------------------------------------------------------------
# get_movie_info -- same OMDb demo endpoint as session-2/task-1-sentiment.
# ---------------------------------------------------------------------------
def get_movie_info(title: str) -> str:
    url = OMDB_URL + "?" + urllib.parse.urlencode({"t": title, "token": "demo"})
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return f"ERROR: could not reach OMDb for '{title}': {e}"
    if data.get("Response") != "True":
        return f"ERROR: OMDb has no data for '{title}': {data.get('Error')}"
    return json.dumps(
        {
            "title": data.get("Title"),
            "year": data.get("Year"),
            "genre": data.get("Genre"),
            "plot": data.get("Plot"),
            "imdb_rating": data.get("imdbRating"),
            "awards": data.get("Awards"),
        }
    )


# ---------------------------------------------------------------------------
# search_docs -- RAG as a tool, wired to Session 3's real index.
# ---------------------------------------------------------------------------
def _load_search_index(client) -> VectorStore:
    index_path = SESSION_3_DIR / "index.json"
    if index_path in _SEARCH_INDEX_CACHE:
        return _SEARCH_INDEX_CACHE[index_path]
    if not index_path.exists():
        raise FileNotFoundError(
            f"No Session 3 index at {index_path}. Run `python ingest.py` in session-3/ first."
        )
    store = VectorStore.load(index_path)
    _SEARCH_INDEX_CACHE[index_path] = store
    return store


def search_docs(client, embed_fn, query: str, k: int = 3) -> str:
    store = _load_search_index(client)
    k = max(1, min(int(k or 3), 10))
    query_vec = embed_fn(client, [query])[0]
    results = store.search(query_vec, k=k)
    passages = [
        {
            "source": r["metadata"]["source"],
            "page": r["metadata"]["page"],
            "score": round(r["score"], 3),
            "text": r["text"],
        }
        for r in results
    ]
    return json.dumps({"passages": passages})


# ---------------------------------------------------------------------------
# send_email -- DANGEROUS_TOOLS member. Simulated: never leaves the machine.
# ---------------------------------------------------------------------------
def send_email(to: str, subject: str, body: str) -> str:
    entry = f"TO: {to}\nSUBJECT: {subject}\nBODY: {body}\n{'-' * 40}\n"
    with open(OUTBOX_PATH, "a", encoding="utf-8") as f:
        f.write(entry)
    return json.dumps({"status": "sent", "to": to, "subject": subject})


# ---------------------------------------------------------------------------
# dispatch -- the agent loop's single entry point for running a tool call.
# Never raises: any failure becomes an ERROR: string, which the model reads
# back as its observation -- errors get returned to the model, not raised.
# ---------------------------------------------------------------------------
def dispatch(name: str, arguments_json: str, client, embed_fn) -> str:
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return f"ERROR: malformed arguments JSON from model: {e}"

    try:
        if name == "calculator":
            return calculator(args.get("expression", ""))
        if name == "get_movie_info":
            return get_movie_info(args.get("title", ""))
        if name == "search_docs":
            return search_docs(client, embed_fn, args.get("query", ""), args.get("k", 3))
        if name == "send_email":
            return send_email(args.get("to", ""), args.get("subject", ""), args.get("body", ""))
        return f"ERROR: unknown tool '{name}'"
    except Exception as e:  # noqa: BLE001 -- last-resort guard so one bad
        # tool call can't crash the whole agent loop; the model gets to see
        # the failure and decide whether to retry, use another tool, or give up.
        return f"ERROR: tool '{name}' raised {type(e).__name__}: {e}"
