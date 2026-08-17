# Session 5 Assignment — Agentic AI Architectures (Design Doc)

Session 4 built one architecture (ReAct: [../session-4/agent.py](../session-4/agent.py)).
Session 5's ground rule is "no new installs, this is concepts and design" —
so the core deliverable below is the **design doc**: one real workflow,
mapped to two patterns, compared, and a recommendation justified in a
paragraph, per the assignment. The stretch goals then implement
both patterns for real on top of the same `llm_client.py`/tool-calling
plumbing session-4 already has, so the comparison table isn't guesswork —
every number in it came from an actual run.

```
session-5/
  tools.py            <- domain tools: get_booking, search_policy, compute_refund (+ calculator, reused from session-4)
  react_agent.py       <- Pattern 1 (ReAct) baseline, same task
  pipeline.py          <- Pattern 4 (Sequential Pipeline), the recommended architecture
  router.py            <- stretch: Router into a Pipeline for one category (combining patterns)
  compare_runner.py    <- runs both patterns on 4 cases, produces the numbers below
```

## Setup

```bash
cd session-5
pip install -r requirements.txt   # same 2 deps as every session: openai, python-dotenv
```

Uses the same `OPENAI_API_KEY` (OpenRouter key) from the root `.env` as
every other session, and reuses session-4's `llm_client.py` and `calculator`
tool directly (imported, not copied) — see [../session-4/README.md](../session-4/README.md).

## Core requirement: the workflow

**Chosen workflow: airline booking cancellation & refund quote** — the
exact scenario used for Pattern 1 ("Can I cancel this? My PNR is
MMT7842."). A user gives a PNR; the system has to look up the booking, find
the cancellation-policy rule that applies to its fare type and timing, and
tell the user the refund percentage and amount. This workflow was picked
over the other suggested options (payments dispute, seller onboarding)
because it's small enough to implement both patterns for real inside this
assignment while still having a genuine "the answer must be exact" risk
profile — a refund percentage is real money, not prose.

### Mapped to Pattern 1: ReAct ([react_agent.py](react_agent.py))

```
User: "Can I cancel my booking MMT7842? What refund would I get?"
        |
        v
  [ Thought -> Action -> Observation, repeated ]
        |
   get_booking("MMT7842") ---------> {fare_type, booked_hours_ago, departs_in_hours, amount}
        |
   search_policy("...")  -----------> matching policy clause(s)
        |
   calculator("amount * pct/100") --> exact refund amount   (model decides IF it needs this)
        |
        v
   Final answer (free text): refund %, amount, reason
```

The model discovers this exact 2-3 step path itself — nothing in the code
tells it to look up the booking before the policy, or to compute the
refund amount at all. It re-derives the policy rule from retrieved prose
and does the arithmetic (or skips it) each time.

### Mapped to Pattern 4: Sequential Pipeline ([pipeline.py](pipeline.py))

```
User message
     |
     v
[1. extract_pnr]      code, regex        -- pull the PNR out of the message
     |
     v
[2. get_booking]      code, direct call  -- fare_type, timing, amount
     |
     v
[3. search_policy]    code, direct call  -- query built FROM the booking facts, not guessed
     |
     v
[4. compute_refund]   code, pure rule    -- the ONE deterministic branch: free-window -> non-refundable
     |                                      -> >24h -> <24h, in that fixed priority order, every time
     v
[5. draft_reply]      1 LLM call          -- turn already-correct facts into a friendly sentence
     |
     v
[6. format_response]  code                -- {pnr, refund_pct, refund_amount_inr, reason, reply}
```

Every request walks all 6 stages in the same order. The model's only job is
stage 5 — restating numbers it is never allowed to compute itself. If the
message has no PNR, the pipeline fails fast at stage 1 with a clear error
instead of the model improvising (see "Avoid when" below).

## Comparison: measured, not estimated

[compare_runner.py](compare_runner.py) runs the same 4 requests — one per
branch of `compute_refund()`'s eligibility rule (free-window, non-refundable,
refundable >24h, refundable <24h) — through both patterns and checks each
answer against the objectively correct refund percentage:

```bash
python compare_runner.py
```

| Metric | ReAct | Sequential Pipeline |
|---|---|---|
| Correct refund % (4 cases) | **2/4 (50%)** | **4/4 (100%)** |
| Avg LLM calls per request | 3.8 | **1.0** |
| Avg tool calls per request | 2.8 | 2.0 |
| Avg wall latency | 4.64s | **1.82s** |
| Debug difficulty | Medium — have to read the model's tool-call trace to see *why* it picked a number | Very high — `compute_refund()` is a pure function, unit-testable with no model in the loop |
| Risk if wrong | High and silent — a wrong refund % looks exactly as confident as a right one | Low — the number can only be wrong if the code rule itself is wrong, which is testable |

The two ReAct misses are real, reproducible failures, not checker noise:
for the booking cancelled inside the 1-hour free window, the model reasoned
from a retrieved "within 24 hours -> 50%" clause and **missed the
free-cancellation-window rule entirely**, answering 50% instead of the
correct 100%. For the booking cancelled 10 hours before departure, it
**inverted the threshold** and answered 90% (the ">24h" rate) instead of 50%.
Both are the same failure shape: the model re-derives a money calculation
from retrieved prose every single call, and a plausible-sounding wrong
answer is indistinguishable from a right one without checking it by hand.
The pipeline cannot make either mistake — `compute_refund()` always
evaluates the same 4 branches in the same priority order, so the number is
right by construction; the LLM never touches it, it only writes the sentence
around it.

## Recommendation: ship the Sequential Pipeline first

**Ship the pipeline.** This workflow is exactly the "same 4 stages
run every time" signal to avoid ReAct, and matches the decision-matrix row
("every ticket takes the same stages -> Sequential pipeline") to the letter:
every cancellation request needs the same booking lookup, the same policy
check, and the same refund arithmetic, in the same order, and the arithmetic
is money — exactly where the "avoid it when mistakes are expensive"
warning applies hardest. The measured numbers back this up on every axis
that matters for a support flow: 4x fewer LLM calls, ~2.5x lower latency,
and — the one that actually matters for a refund quote — 100% vs 50% correct
in this test, because the one place a wrong number could appear
(`compute_refund`) isn't inside the model's control at all. ReAct remains
the better choice for the *next* feature this same system will eventually
need — "why was my refund only 90%, can you explain the fee" — an open-ended
question with no fixed number of steps, which is exactly what Pattern 1 is
for and what Pattern 4 explicitly cannot flex into.

## Stretch: hybrid — Router into a Pipeline for one category ([router.py](router.py))

Per the "Combine patterns: Router into a ReAct specialist... Production
systems are hybrids" guidance, adapted the other direction — **router into a
pipeline**:

```
User message
     |
     v
[classify]  1 cheap LLM call -> "cancellation" | "general"
     |
     +--- "cancellation" --> pipeline.run_pipeline()   (Pattern 4, fixed & cheap)
     |
     +--- "general"      --> react_agent.run_react()   (Pattern 1, flexible)
```

```bash
python router.py "Can I cancel my booking MMT9911? What refund would I get?"
# [ROUTER] classified as: cancellation  -> pipeline runs, 1 LLM call total (+1 for the route)

python router.py "Is booking MMT9911 a refundable fare?"
# [ROUTER] classified as: general       -> ReAct agent runs instead
```

Verified: the first message routes into the pipeline and returns the exact
90%/₹5580 answer in 2 LLM calls total (classify + draft); the second has no
cancellation intent, routes to the ReAct agent instead, and it correctly
calls only `get_booking` (no `search_policy`, no `calculator` — there's no
refund question to answer). The router keeps the cheap, always-correct path
for the high-volume "cancel and quote" case and reserves the expensive,
flexible path for everything that doesn't fit the pipeline's fixed shape.

## Debrief

**Which pattern surprised you as the best fit for a problem you know?** —
The Sequential Pipeline surprised me by how much it improved *correctness*,
not just cost. Going in, I expected the trade-off to be "pipeline is
cheaper and faster, ReAct is smarter" — the kind of trade-off the
decision-matrix table implies (pipeline: "very high" debug ease but nothing about accuracy).
In practice, on a task with one genuinely risky number, the ReAct agent's
flexibility was actively a liability: it re-derived the refund rule from
prose every time and got it wrong twice out of four tries. The pipeline's
rigidity is exactly what made it reliable.

**When is a pipeline better than an agent?** — When the same fixed sequence
of steps really does apply to every request (predictability), when a step
in that sequence has one objectively correct output that code can compute
exactly instead of a model estimating it (this case's refund %), and when
each stage needs to be unit-testable in isolation before it ships
(`compute_refund()` here can be tested with 4 plain assertions and no API
key at all — try doing that for a ReAct trace).

**What would you combine from Session 3 (RAG) and today?** — `search_policy`
here is a toy keyword matcher standing in for what should be session-3's
real `vector_store.py`, the same way session-4's `search_docs` was wired
directly to session-3's index instead of reimplementing retrieval. The
natural combination: pipeline Stage 3 becomes a real RAG call over an actual
policy document, while Stage 4's refund math stays plain code regardless —
RAG is right for "what does the policy document say," never for "what number
does the policy imply," which is exactly the split this assignment's
`search_policy` vs `compute_refund` already models.

## Next session

MCP (Model Context Protocol) — the standard way to plug tools and data into
any of these seven patterns without writing custom glue (like this
session's `sys.path` + `importlib` reach-across into session-4's `tools.py`)
per integration.
