"""
Session 5 Assignment - Domain tools for the OTA cancellation workflow
=========================================================================
The workflow chosen for the design doc (README.md) is the exact scenario
Session 5's canonical example for Pattern 1 (ReAct): a travel app's "can I cancel
this booking" flow. Two new domain tools simulate the backend a real OTA
would have -- no network calls, just local dicts, the same "simulated but
structurally real" approach as session-4's send_email/outbox.log:

  get_booking    - booking lookup by PNR (route, fare type, timing facts)
  search_policy  - keyword search over a small cancellation-policy KB
  calculator     - NOT reimplemented -- imported straight from session-4's
                   tools.py, per the general "same code as Session 3" reuse
                   rule, now one session later.

compute_refund() is deliberately NOT a tool the model calls -- it is the
plain-code business rule the Sequential Pipeline (pipeline.py) runs as its
"Format JSON (code)" stage. This is the whole point of that pattern: a
money calculation should be exact, testable code, not something an LLM
free-forms from policy prose (the ReAct baseline in react_agent.py leaves
this to the model on purpose, so the two patterns can be compared honestly).
"""

import importlib.util
import json
from pathlib import Path

SESSION_DIR = Path(__file__).resolve().parent
SESSION_4_DIR = SESSION_DIR.parent / "session-4"

# Loaded by explicit file path (not sys.path + `import tools`) because this
# module is ALSO named tools.py -- a plain sys.path.insert + `import tools`
# would resolve to itself mid-initialization instead of session-4's file.
_spec = importlib.util.spec_from_file_location("session4_tools", SESSION_4_DIR / "tools.py")
_session4_tools = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_session4_tools)
calculator = _session4_tools.calculator  # reused verbatim from session-4

# ---------------------------------------------------------------------------
# Simulated booking DB. Timings are relative ("booked_hours_ago",
# "departs_in_hours") so the eligibility rule in compute_refund() has
# something real to branch on, matching the "booked 6h ago,
# non-refundable fare" framing.
# ---------------------------------------------------------------------------
BOOKINGS = {
    "MMT7842": {
        "pnr": "MMT7842", "route": "DEL-GOA", "fare_type": "non-refundable",
        "booked_hours_ago": 6, "departs_in_hours": 40, "amount_inr": 4500,
    },
    "MMT9911": {
        "pnr": "MMT9911", "route": "BLR-DEL", "fare_type": "refundable",
        "booked_hours_ago": 30, "departs_in_hours": 50, "amount_inr": 6200,
    },
    "MMT1200": {
        "pnr": "MMT1200", "route": "DEL-BOM", "fare_type": "refundable",
        "booked_hours_ago": 0.5, "departs_in_hours": 5, "amount_inr": 3000,
    },
    "MMT5555": {
        "pnr": "MMT5555", "route": "HYD-CHN", "fare_type": "refundable",
        "booked_hours_ago": 10, "departs_in_hours": 10, "amount_inr": 2800,
    },
}

# ---------------------------------------------------------------------------
# Tiny local "policy KB" -- keyword-matched, not embedded. A real system
# would use session-3's vector_store.py the way session-4's search_docs
# does; 4 short clauses don't need a vector index, so this stays a plain
# substring match rather than pulling in an embedding call this domain
# doesn't need (ground rule: no new installs today).
# ---------------------------------------------------------------------------
POLICY_CLAUSES = [
    {
        "id": "free-window",
        "keywords": ["free", "1 hour", "one hour", "grace", "window"],
        "text": "Cancellations made within 1 hour of booking are fully refundable (100%), regardless of fare type.",
    },
    {
        "id": "non-refundable",
        "keywords": ["non-refundable", "saver", "no refund"],
        "text": "Outside the free-cancellation window, ECONOMY SAVER (non-refundable) fares are not eligible for any refund.",
    },
    {
        # "more than 24" (not the ambiguous "24 hour", which is a substring
        # of BOTH "more than 24 hours" and "within 24 hours" and made this
        # clause tie with refundable-late on every query) keeps this clause
        # from being retrieved for a within-24h cancellation.
        "id": "refundable-early",
        "keywords": ["refundable", "flex", "more than 24", "before departure", "early"],
        "text": (
            "Outside the free-cancellation window, ECONOMY FLEX (refundable) fares cancelled more than "
            "24 hours before departure receive a 90% refund; a 10% cancellation fee applies."
        ),
    },
    {
        "id": "refundable-late",
        "keywords": ["refundable", "flex", "within 24", "late", "close to departure"],
        "text": "ECONOMY FLEX (refundable) fares cancelled within 24 hours of departure receive a 50% refund.",
    },
]


def get_booking(pnr: str) -> str:
    booking = BOOKINGS.get(pnr.strip().upper())
    if not booking:
        return json.dumps({"error": f"No booking found for PNR '{pnr}'"})
    return json.dumps(booking)


def search_policy(topic: str, k: int = 2) -> str:
    """Keyword-scored 'retrieval' over POLICY_CLAUSES -- same passages+score
    shape as session-4's search_docs, so both patterns read tool output the
    same way."""
    topic_lower = topic.lower()
    scored = []
    for clause in POLICY_CLAUSES:
        score = sum(1 for kw in clause["keywords"] if kw in topic_lower)
        if score:
            scored.append((score, clause))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = scored[: max(1, k)] or [(0, c) for c in POLICY_CLAUSES]  # fall back to all clauses if nothing matched
    passages = [{"clause_id": c["id"], "score": s, "text": c["text"]} for s, c in top]
    return json.dumps({"passages": passages})


def compute_refund(booking: dict) -> dict:
    """The deterministic business rule -- plain code, no LLM. This is what
    the Sequential Pipeline runs as a fixed stage instead of asking a model
    to reason it out from policy prose each time."""
    if booking["booked_hours_ago"] <= 1:
        pct, reason, clause_id = 100, "cancelled within the 1-hour free window", "free-window"
    elif booking["fare_type"] == "non-refundable":
        pct, reason, clause_id = 0, "non-refundable fare, outside the free window", "non-refundable"
    elif booking["departs_in_hours"] > 24:
        pct, reason, clause_id = 90, "refundable fare, cancelled >24h before departure", "refundable-early"
    else:
        pct, reason, clause_id = 50, "refundable fare, cancelled within 24h of departure", "refundable-late"

    amount = round(booking["amount_inr"] * pct / 100, 2)
    return {
        "pnr": booking["pnr"], "refund_pct": pct, "refund_amount_inr": amount,
        "reason": reason, "policy_clause_id": clause_id,
    }


# ---------------------------------------------------------------------------
# Tool schemas -- get_booking + search_policy here, calculator's schema
# copied verbatim from session-4 (same tool, same interface). Used by
# react_agent.py's ReAct loop; the pipeline calls the plain functions above
# directly and never puts these in front of the model at all.
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_booking",
            "description": (
                "Look up a flight booking by its PNR (booking reference). Use this "
                "whenever a user asks about cancelling, refunding, or checking a "
                "specific booking and gives (or implies) a PNR. Returns the route, "
                "fare type (refundable/non-refundable), how long ago it was booked, "
                "how many hours until departure, and the amount paid. Returns an "
                "'error' field if the PNR doesn't exist."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pnr": {"type": "string", "description": 'Booking reference, e.g. "MMT7842".'},
                },
                "required": ["pnr"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": (
                "Search the airline cancellation policy for the rule that applies to "
                "a fare type or situation. Use this to find out what refund percentage "
                "a booking is eligible for -- do NOT guess the refund rule from memory, "
                "policies vary by fare type and timing. Returns the top matching "
                "policy clause(s)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": 'What to search for, e.g. "non-refundable fare cancellation" or "refund within 24 hours of departure".',
                    },
                    "k": {"type": "integer", "description": "How many clauses to return (default 2)."},
                },
                "required": ["topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": (
                "Evaluate a basic arithmetic expression (+, -, *, /, **, parentheses, "
                "decimals). Use this whenever you need to compute a refund amount from "
                "a percentage and a fare -- do not compute it yourself."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": 'The expression to evaluate, e.g. "4500 * 0.9".',
                    },
                },
                "required": ["expression"],
            },
        },
    },
]


def dispatch(name: str, arguments_json: str) -> str:
    """Same never-raises contract as session-4's dispatch: any failure comes
    back as an 'ERROR: ...' string for the model to read, instead of
    crashing the loop."""
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        return f"ERROR: malformed arguments JSON from model: {e}"

    try:
        if name == "get_booking":
            return get_booking(args.get("pnr", ""))
        if name == "search_policy":
            return search_policy(args.get("topic", ""), args.get("k", 2))
        if name == "calculator":
            return calculator(args.get("expression", ""))
        return f"ERROR: unknown tool '{name}'"
    except Exception as e:  # noqa: BLE001
        return f"ERROR: tool '{name}' raised {type(e).__name__}: {e}"
