# Final Assignment — Doc-to-Podcast Pipeline (Option 3)

Turns a real technical document into a narrated, fact-checked podcast
episode: RAG-grounded plan-and-execute scripting, a critic/reflection pass
that catches unsupported claims, text-to-speech, and an MCP tool call (via a
real ReAct tool-calling loop) that saves the audio and transcript side by
side. Built to force touching all seven sessions — see
[Map back to the sessions](#map-back-to-the-sessions) below.

```
final-assignment/
  llm_client.py       <- shared: get_client(), call_model() (+tokens), call_with_tools()
  rag.py               <- retrieval, reused directly from session-3's index.json (no re-ingestion)
  planner.py            <- Stage 1: plan-and-execute (outline -> per-section retrieval + expansion)
  critic.py              <- Stage 2: critic/reflection (flag unsupported claims, revise, MAX_REVISIONS=3)
  tts.py                   <- Stage 3: text-to-speech (pyttsx3, local)
  podcast_server.py         <- the MCP server: one tool, save_podcast_output
  save_agent.py               <- Stage 4: ReAct tool-calling loop that consumes podcast_server.py over MCP
  pipeline.py                  <- orchestrates all 4 stages, logs timing + token counts, CLI entry point
  eval_set.py                    <- 10 eval cases (content questions + structure checks + critic checks)
  eval_runner.py                   <- runs eval_set.py for real, reports pass/fail
  output/                            <- saved episodes (transcript .txt + audio .wav, side by side)
```

## Chosen document, and why

**[../session-3/docs/DS- Technical Case Study.pdf](../session-3/docs/DS-%20Technical%20Case%20Study.pdf)**
— a real 6-page technical case study about building a centralized Angular
design system, already RAG-indexed by Session 3
(`../session-3/index.json`). This pipeline queries that index directly
rather than re-ingesting the same PDF a third time (session-4's
`search_docs` tool already set this precedent one session earlier, wiring
straight into Session 3's index instead of duplicating it). Reusing a real,
already-indexed document lets this capstone spend its effort on the
plan-execute/critic/TTS/MCP pipeline itself — the actual point of this
assignment — instead of re-solving RAG ingestion a fourth time.

## Setup

```bash
cd final-assignment
pip install -r requirements.txt
```

Needs `../session-3/index.json` to exist (it's already in this repo; if
missing, `cd ../session-3 && python ingest.py` rebuilds it). Uses the same
`OPENAI_API_KEY` (an OpenRouter key) from the root `.env` as every other
session — see [../session-1/README.md](../session-1/README.md). Text-to-speech
uses `pyttsx3`'s Windows SAPI5 backend (same as Session 7) — Windows only, no
API key, fully offline.

## Run it

```bash
python pipeline.py                                   # full run, verbose stage-by-stage log
python pipeline.py --episode-name my-episode --k 5   # custom episode name / retrieval width
python pipeline.py --quiet                           # suppress the stage log
python eval_runner.py                                # runs the pipeline once + the 10-case eval set
```

Output lands in `output/<episode-name>.txt` and `output/<episode-name>.wav`,
saved side by side by the MCP tool call.

### When the input is wrong

Every way I could get this wrong on a fresh clone fails with a sentence that
says what to do about it, not a stack trace. All four messages below are
copied from actually triggering them:

| What's wrong | What you get |
|---|---|
| No `OPENAI_API_KEY` in the root `.env` | `ERROR: OPENAI_API_KEY not found. Add it to C:\...\gen-ai\.env as: OPENAI_API_KEY=sk-...` then exit 1 — no traceback (`llm_client.py`) |
| Session 3's index missing | `No Session 3 index at ...\index.json. Run 'python ingest.py' in session-3/ first.` (`rag.py`) |
| A file the save tool is pointed at doesn't exist | The tool returns `{"error": "transcript_source_path does not exist: nope.txt"}` — a normal observation the agent reads, not a crash (`podcast_server.py`) |
| An episode name that tries to escape the folder | `--episode-name ../../evil` is sanitized to `evil` and lands in `output/evil.txt`; a destination that still resolved outside `output/` would be refused (`podcast_server.py`) |

The model's own bad output is handled the same way: a non-JSON outline or
critic verdict falls back to a safe default (`{"title": "Untitled Episode",
"sections": []}` / `supported: true`) instead of raising, and both agent
loops are capped (`MAX_REVISIONS=3`, `MAX_ITERATIONS=3`) so a model that
keeps flagging or keeps calling tools stops rather than spins.

## The 4-stage pipeline

```
User's document
     |
     v
[RAG]                Session 3's real vector_store.py + index.json, reused
     |                directly -- no re-ingestion (see rag.py)
     v
[Plan-and-execute]    Session 5 pattern #1 (planner.py)
     |  1. plan_outline()   -- ONE call, whole-doc text in, JSON outline out
     |  2. expand_section()  -- PER SECTION: its own top-k retrieval + its
     |                          own LLM call, grounded in what THAT
     |                          retrieval returned
     v
[Critic / reflection] Session 5 pattern #2 (critic.py)
     |  check_section()  -- flags claims the source doc doesn't support
     |  revise_section()  -- rewrites, grounded in the source, if flagged
     |  looped up to MAX_REVISIONS=3 times per section
     v
[Text-to-speech]      Session 7 (tts.py) -- pyttsx3, local, since
     |                 OpenRouter doesn't proxy TTS (verified in session-7)
     v
[MCP save]            Session 4 + 6 (save_agent.py + podcast_server.py)
                       A ReAct tool-calling loop (Thought/Action/Observation,
                       correct tool_call_id handling, MAX_ITERATIONS=3)
                       whose only tool is discovered live from an MCP
                       server's list_tools() -- never hard-coded -- and
                       calls save_podcast_output to persist the transcript
                       and audio, side by side, in output/.
```

## Why this architecture, and what I rejected

The named pattern is **plan-and-execute** (`planner.py`) with a
**critic/reflection** loop on top (`critic.py`) — two of Session 5's listed
patterns, chosen for one reason: *the shape of this work is known before it
starts.* A podcast script is an outline, then N sections, then a check. That
shape doesn't depend on anything discovered at runtime.

The alternative I actually considered was a **single ReAct loop** — one
agent with a `search_docs` tool, told to "write a podcast script," free to
retrieve as it goes. I rejected it on three grounds:

- **Grounding gets worse.** In plan-and-execute, section 4's prose comes
  from an LLM call whose *only* input is section 4's own retrieval. In a
  ReAct loop, by section 4 the context window holds three earlier sections
  the model wrote itself, and the cheapest next token is one that continues
  its own prose rather than the retrieved text. That's exactly the drift
  this assignment's critic step exists to catch — better not to manufacture
  it upstream.
- **You can't inspect a loop the same way.** Fixed stages mean
  `section["sources"]` is a real answer to "where did this sentence come
  from." A ReAct trace can tell you what it searched, not which retrieval
  each sentence leaned on.
- **Cost is unbounded and untunable.** Plan-and-execute costs exactly
  `1 + N` calls for the draft. The measured run below is 26.4k tokens for a
  6-section episode; a loop's spend depends on how many times it decides to
  search.

This is the same argument session-5's README used to pick Sequential
Pipeline over ReAct for a compliance-sensitive number, applied to a
different known-shape task. Where ReAct *does* earn its place here is the
one genuinely open-ended step — the save, where the tool schema isn't known
until an MCP server reports it — which is exactly where `save_agent.py`
uses it.

The critic is a separate pass rather than "just a better section prompt"
because a model checking its own sentence in the same call as it writes it
isn't checking anything; the second call sees the finished section and the
*whole* source document, not the retrieval slice that produced it.

## Retrieval: k, citations, and the "I don't know" path

**k is 4** (`--k` to change it). Session 3 shipped `k=3` on this index; this
pipeline raised it to 4 because the unit of generation is different. Session 3
answered one narrow question per call, where a 4th chunk is mostly noise; here
each call has to write 3–5 sentences of continuous narration on a *section
heading*, which is broader than a question, and a section that comes up one
passage short reads as vague rather than wrong. The index holds 6 chunks
total, so k=4 gives each section two-thirds of the document ranked by its
own query, and still drops the two least relevant chunks rather than
degenerating into "hand it everything."

**Every chunk is cited.** `format_context()` renders each passage with its
source, page, chunk index and cosine score, and `expand_section()` keeps a
`section["sources"]` list (source/page/score) on every section it writes, so
any sentence in the transcript traces back to the passages that produced it.

**On a threshold for "I don't know."** Measured cosine scores on this index,
k=6 (i.e. everything):

| Query | Scores |
|---|---|
| "Storybook documentation for the design system" | 0.649, 0.619, 0.617, 0.615, 0.600, 0.564 |
| "npm package distribution strategy" | 0.421, 0.373, 0.365, 0.362, 0.334, 0.266 |
| "What is the capital of France?" | 0.037, 0.012, 0.003, −0.000, −0.009, −0.022 |

On-topic and off-topic are an order of magnitude apart, so a cutoff would
sit around **0.2** — but note the second row: a perfectly answerable
question about this document tops out at 0.42, well under the 0.649 of the
first. A cutoff tuned any tighter than 0.2 would start refusing real
questions, and this pipeline never issues the third kind of query anyway —
section queries are written by the outline call *from this document's own
text*, so an off-topic query can't arise in the flow.

So the abstain path is enforced where it can actually fire, at generation
time rather than at retrieval time: `SECTION_SYSTEM_PROMPT` ends with *"if
the retrieved context doesn't actually support this section's heading, say
so plainly in the narration instead of filling in from general knowledge,"*
and the critic pass then flags anything that filled in anyway. A score
cutoff is the right guard for a Q&A front door taking arbitrary user
questions; it's the wrong guard for a closed pipeline whose queries it
generates itself.

## Grounded generation, checked two ways

1. **The planner is grounded by construction** — every section's prose comes
   from an LLM call whose only input is that section's own retrieved
   passages.
2. **The critic is grounded independently, as a second pass** — a separate
   LLM call at `temperature=0.0` re-checks each finished section against the
   *whole* source document, returns
   `{"supported": bool, "flagged_claims": [...]}`, and a revise call
   rewrites the section if anything is flagged, up to 3 times.

Group C of the eval set tests the critic on purpose, including the case most
likely to slip through — a section where every fact is right except one
number. It catches it (see [Evaluation](#evaluation-10-cases-run-for-real)).

## The agent and its tools

`save_agent.py` is a real Thought/Action/Observation loop, not a function
call with ceremony around it:

- **The tool schema is never hard-coded.** The agent connects to the MCP
  server, calls `list_tools()`, and converts whatever comes back into
  function-calling schemas (`_mcp_tools_to_openai_schema`). Add a second
  tool to `podcast_server.py` and the agent can use it without a line
  changing here.
- **Every call is logged** — `[TOOL]` with the arguments and `[OBS]` with
  the result *and its wall-clock time*, both truncated at 200 chars so a
  long observation can't drown the log.
- **`tool_call_id` is round-tripped correctly.** The assistant message
  carrying `tool_calls` is appended *before* any tool result, and each
  result goes back as `{"role": "tool", "tool_call_id": tc.id, ...}` — the
  pitfall Session 4 flagged.
- **Iteration cap.** `MAX_ITERATIONS=3`; hitting it returns
  `answer: None` with the partial trace instead of looping.
- **Tool errors come back as observations, not exceptions.** The server
  returns `{"error": "..."}` as a normal tool result, so a missing file or a
  refused path lands in the message history and the model gets its remaining
  iterations to react — the loop only ends on a final answer or the cap.

Parallel tool calls aren't used: there is exactly one tool, and the two
copies it performs are already a single atomic call. The loop appends
results per `tc` in `msg.tool_calls`, so a model that emitted two calls in
one turn would be handled correctly regardless.

## MCP: separation and permissions

`podcast_server.py` is a standalone MCP server, launched by
`save_agent.py` as a subprocess over stdio. The separation is real, not
cosmetic — the server never imports the pipeline, the pipeline never imports
the server's function, and `python podcast_server.py` serves on its own.
Everything crosses the protocol boundary.

Permissions are least-privilege and enforced in the server's own code, since
this is a custom server rather than the official filesystem one:

- The tool can only ever write into `final-assignment/output/`. The episode
  name is stripped to alphanumerics, `-` and `_`, and both destination paths
  are then re-checked to confirm they resolve inside `OUTPUT_DIR` — belt and
  suspenders. Verified by trying it: `../../evil` becomes `output/evil.txt`.
- It only ever *creates two files it names itself*. It cannot delete, cannot
  write outside `output/`, and cannot be pointed at a destination path by
  the model at all — the model supplies a name, not a target.
- It takes **paths, not payloads**. Its first version took the transcript
  text as a parameter, which is what caused the failure documented below.

## Multimodal: TTS latency, logged and discussed

`tts.py` returns `{"tts_ms", "audio_seconds", "path"}` on every call, and
`pipeline.py` folds `tts_ms` into the same per-stage timing block as every
other stage. From the verified run below:

| | Time | Share of run |
|---|---|---|
| Plan-and-execute (7 LLM calls) | 20,461 ms | 51% |
| Critic (6 LLM calls) | 9,539 ms | 24% |
| MCP save (agent + tool) | 6,309 ms | 16% |
| **TTS (254.9 s of audio)** | **2,760 ms** | **7%** |

The interesting number is that TTS synthesizes at roughly **92× real time**
and is the *cheapest* stage in the pipeline, at 7% of a 40-second run. That
is the direct payoff of it being local: `pyttsx3` drives the Windows SAPI5
engine in-process, so there's no upload of a 4,700-character script, no
queueing, and no download of an 11 MB wav. Session 7 established the
constraint that forced this choice — OpenRouter doesn't proxy the TTS
endpoint (`client.audio.speech.create(model="tts-1")` returns "Model tts-1
does not exist") — but on latency it's the better answer anyway; a hosted
call would have made the audio stage cost more than the entire critic pass,
for the same 4 minutes of speech.

What it costs is voice quality: SAPI5 sounds like a screen reader, not a
podcast host. If this went anywhere real, that's the trade I'd revisit —
and the swap is one function, since `synthesize_speech()` is the only place
in the pipeline that knows how audio gets made.

## Verified run

Real, live run against the real document, the real OpenRouter API, and the
real MCP server (`python pipeline.py`):

```
=== Stage: Plan-and-execute (RAG-grounded outline + sections) ===
[PLAN] 'Building a Centralized Design System: A Technical Case Study' -- 6 sections
[EXPAND 1/6] Project Overview and Business Challenges
[EXPAND 2/6] The Centralized Design System Solution
[EXPAND 3/6] Storybook as Documentation and Training Tool
[EXPAND 4/6] npm Packaging and Distribution Strategy
[EXPAND 5/6] Delivery Approach and Outcomes
[EXPAND 6/6] Scalability and Conclusion

=== Stage: Critic / reflection (grounded-claim check + revise) ===
[CRITIC pass 1] Project Overview and Business Challenges: OK
[CRITIC pass 1] The Centralized Design System Solution: OK
[CRITIC pass 1] Storybook as Documentation and Training Tool: OK
[CRITIC pass 1] npm Packaging and Distribution Strategy: OK
[CRITIC pass 1] Delivery Approach and Outcomes: OK
[CRITIC pass 1] Scalability and Conclusion: OK

=== Stage: Text-to-speech ===
[TTS] 254.9s of audio in 2760ms

=== Stage: MCP save (ReAct agent, tool sourced live from MCP) ===
[MCP] Connected. Server offers 1 tool(s): save_podcast_output
[TOOL] step 1  save_podcast_output({"episode_name":"ds-case-study-ep1", "transcript_source_path":"...\\transcript_tmp.txt", "audio_source_path":"...\\audio_tmp.wav"})
[OBS]  (0.26s) {"transcript_path": "...\\output\\ds-case-study-ep1.txt", "audio_path": "...\\output\\ds-case-study-ep1.wav"}

Assistant: The episode has been successfully saved.

--- Summary: 'Building a Centralized Design System: A Technical Case Study' | total_ms=40288 | total_tokens=26450 ---
  plan_execute_ms: 20461ms
  critic_ms: 9539ms
  tts_ms: 2760ms
  mcp_save_ms: 6309ms
  total_ms: 40288ms
```

`output/ds-case-study-ep1.txt` and `output/ds-case-study-ep1.wav` in this
repo are that exact run's real, unedited output — a 6-section, ~4-minute
narrated script and its synthesized audio.

## Evaluation: 10 cases, run for real

`python eval_runner.py` runs the whole pipeline once, then checks the
episode it just produced. Nothing is mocked; the numbers below are one run's
console output.

**Latest run: 10/10 passed.** `'Building a Centralized Design System: A
Technical Case Study'` — 243.2 s of audio, 26,352 tokens, 44,159 ms total.

| Group | Case | What it proves | Result |
|---|---|---|---|
| A. Content | `q-framework` | Names Angular **and** Angular Material, not just the framework | PASS |
| A. Content | `q-timeline` | Says six months **and** the twelve-month plan — the comparison, not half of it | PASS |
| A. Content | `q-documentation` | Storybook **and** npm; mentioning one leaves half the answer out | PASS |
| A. Content | `q-no-invented-frameworks` | Names no framework the document never mentions (negative case) | PASS |
| B. Structure | `outline-size` | The planner produced 3–7 sections | PASS |
| B. Structure | `audio-matches-script` | ≥1 s of audio per 5 words — catches audio that stopped early | PASS |
| B. Structure | `saved-files-match` | Both files on disk, non-empty, and the saved transcript is byte-identical to the generated one | PASS |
| C. Critic | `critic-catches-invented-facts` | Flagged both the invented timeline and "React and Vue... Svelte" | PASS |
| C. Critic | `critic-catches-near-miss-number` | Flagged "seven months" where the document says six — everything else in the sentence is true | PASS |
| C. Critic | `critic-accepts-true-paraphrase` | Did **not** flag "about half the year originally set aside" — same fact, different words | PASS |

Group A's checks require *both* halves of each answer on purpose. An earlier
version of this file checked single keywords against generous thresholds
("angular" appears somewhere, audio longer than 5 seconds); those could not
fail on any run that completed at all, so passing them proved very little.

### Two failures worth writing down

**1. The eval was wrong, not the pipeline.** The run before the one above
scored **9/10**. The failure was `q-no-invented-frameworks` — the check that
exists to catch hallucinated frameworks. It fired on this sentence:

> "...allowing new team **members** to grasp the design language quickly..."

`"ember" in narration` is true, because `members` contains `ember`. A
substring test is not a mention test. The episode was clean; the check that
was supposed to catch fabrication had fabricated one itself, and it would
have failed on any run whose script used a perfectly ordinary word. Fixed in
`eval_set.py` with a `mentions()` helper that matches on word boundaries
(`\bember\b`), which is what "mentions Ember" meant all along. Rerun: 10/10.
The lesson I'd carry: a check that can only ever fire on a *string* needs
testing as hard as the thing it's checking, because when it's wrong it lies
in the more expensive direction — it tells you your model hallucinated when
it didn't.

**2. The tool call that couldn't fit.** `save_podcast_output` originally
took the transcript **text** as a parameter, so the agent had to copy the
whole multi-KB script verbatim into its tool-call arguments. At
`max_tokens=300` that JSON got cut off mid-string — `JSONDecodeError:
Unterminated string`, every run, not flakily. Raising `max_tokens` only
moves the cliff to the next longer episode. The real fix was to change the
tool's contract: take a `transcript_source_path` instead, the way
`audio_source_path` already worked, so the model only ever echoes two short
paths and a name and the argument size stops scaling with the script at all.
This is why `pipeline.py` writes `transcript_tmp.txt` to disk before the
save stage. Generalized: if a tool's arguments grow with your data, the tool
signature is wrong — pass a reference, not a payload.

## Safety on actions

The only write in this pipeline — saving the episode — goes through a real
MCP tool call inside a ReAct loop capped at `MAX_ITERATIONS=3`
(`save_agent.py`), not a direct file write. `podcast_server.py`'s tool is
scoped to write only inside its own `output/` folder (checked in code, the
same least-privilege principle as Session 6's filesystem-server sandbox).
This action isn't destructive or irreversible — it only ever creates two new
files, never deletes or overwrites unrelated state — so no human-in-the-loop
gate was added on top of the iteration cap; that gate exists elsewhere in
this repo (session-4's `send_email`) for actions that actually warrant one.
If the tool could delete, overwrite arbitrary paths, or publish the episode
anywhere, the cap alone wouldn't be enough and a confirmation step would go
in front of the call.

## Map back to the sessions

- [x] **Session 1.** `OPENAI_API_KEY` from the root `.env`, never
  hard-coded (`llm_client.py`). A `messages` array built and resent by hand
  at every LLM call site. Temperatures chosen on purpose and documented per
  call: `0.0` for the critic (deterministic fact-checking), `0.3` for the
  outline, `0.4` for section drafting (a little room for natural narration
  phrasing without drifting from the retrieved facts). Token counts logged
  per call and totalled per run.
- [x] **Session 2.** Structured JSON output at three points — the outline
  (`{"title", "sections"}`), the critic verdict
  (`{"supported", "flagged_claims"}`), and the MCP tool's return value —
  each with a fallback for when the model returns something unparseable.
- [x] **Session 3.** Chunking/embeddings/vector store/top-k retrieval, all
  reused directly from Session 3's real index; every section's prose is
  generated from, and attributable to, its own retrieved passages
  (`section["sources"]` in `planner.py`).
- [x] **Session 4.** `save_agent.py`'s Thought/Action/Observation loop:
  correct `tool_call_id` round-tripping, every `[TOOL]`/`[OBS]` logged with
  timing, tool errors handled as observations, `MAX_ITERATIONS=3`.
- [x] **Session 5.** Two named, deliberately chosen patterns —
  plan-and-execute (`planner.py`) and critic/reflection (`critic.py`) —
  argued against the ReAct alternative in
  [Why this architecture](#why-this-architecture-and-what-i-rejected).
- [x] **Session 6.** `podcast_server.py` is a real MCP server run as its own
  process; its tool schema is discovered live via `list_tools()` in
  `save_agent.py`, never hard-coded — the same pattern as session-6's
  `mcp_agent.py` — and it's sandboxed to its own `output/` folder.
- [x] **Session 7.** Text-to-speech (`tts.py`) wired into the flow, with
  `tts_ms` (and every other stage's `*_ms`) logged per run and discussed in
  [Multimodal](#multimodal-tts-latency-logged-and-discussed).
