# Session 7 Assignment — Audio, Video & Evaluation (Homework)

Session 7's homework, done for real against this repo's audio:

```
session-7/
  llm_client.py     <- shared: get_client(), call_model(), transcribe_audio()
  audio_gen.py       <- synthesizes real ~30s speech locally (no mic in this environment)
  golden_set.py        <- the 5 golden-set cases (script + expected summary phrases)
  voice_summary.py       <- Homework items 1-2: audio -> transcript -> 3-bullet summary, timed
  eval_runner.py            <- Homework item 3: runs all 5 cases, reports pass/fail
  audio/                      <- generated .wav files, one per golden-set case
```

## Setup

```bash
cd session-7
pip install -r requirements.txt   # adds pyttsx3 (+ pywin32 on Windows) to the usual openai + python-dotenv
python audio_gen.py                # generates audio/*.wav (only needed once, or after editing golden_set.py)
```

Uses the same `OPENAI_API_KEY` (an OpenRouter key) from the root `.env` as
every other session — see [../session-1/README.md](../session-1/README.md).

## A real gap, checked before building on it (same discipline as every earlier session)

The TTS discussion and this session's homework both assume you can get from
text to speech and from speech to text through the same provider. Verified
live, both directions, before writing anything else:

- `client.audio.transcriptions.create(model="whisper-1", ...)` — **works**
  through OpenRouter, the same way chat completions (session-1) and
  embeddings (session-3) already do.
- `client.audio.speech.create(model="tts-1", ...)` — **fails**:
  `Error code: 400 - {'error': {'message': 'Model tts-1 does not exist', 'code': 400}}`.

So OpenRouter proxies STT but not TTS. Combined with there being no
microphone in this environment, the homework's required "~30s audio" input
had two options: fabricate a dummy tone (not real speech, useless for
proving a summarizer works), or synthesize genuine speech another way.
Chose the latter: [audio_gen.py](audio_gen.py) uses `pyttsx3`, the local
SAPI5 engine that ships with Windows — fully offline, no API key, real
spoken audio, not a placeholder.

```bash
python audio_gen.py
```
```
design-system-status    28.7s -> audio\case-1-design-system.wav
oncall-handoff           28.0s -> audio\case-2-oncall-handoff.wav
ota-cancellation           29.5s -> audio\case-3-ota-cancellation.wav
sprint-planning              28.3s -> audio\case-4-sprint-planning.wav
payment-support                27.1s -> audio\case-5-payment-support.wav
```

All 5 land within a couple seconds of the homework's "~30s" target.

## Homework 1 & 2 — audio → transcript → 3-bullet summary, timed

[voice_summary.py](voice_summary.py) is the pipeline: batch STT (fine here
since nothing is waiting live on a phone call) into one LLM call
that condenses the transcript to exactly 3 bullets, timing both stages
separately.

```bash
python voice_summary.py --verbose
```

Verified, live run against `audio/case-1-design-system.wav`:

```
Transcript:
Quick status update on the design system project. We shipped the button and input
components last week, and the color token migration is now complete across all
three product teams. The main blocker right now is a legacy CSS override in the
checkout flow, which is still overriding our new spacing tokens. I have filed a
ticket for that. Next week we are planning to start the typography rollout, and
QA sign-off is expected by Friday. Overall we are on track to hit the mid-month
deadline.

Summary:
- The button and input components were shipped last week, and the color token
  migration is complete across all three product teams.
- A legacy CSS override in the checkout flow is blocking progress, and a ticket
  has been filed to address it.
- Next week, the typography rollout is planned, with QA sign-off expected by
  Friday, keeping the project on track for the mid-month deadline.

stt_ms=4859  llm_ms=1935  total_ms=6794
```

The transcript is a verbatim match of the synthesized script — Whisper had
no trouble with `pyttsx3`'s voice — and the summary correctly compresses it
to 3 bullets without inventing anything.

## Homework 3 — the 5-case golden set

[golden_set.py](golden_set.py) reuses domains from earlier sessions where it
fit — the design-system doc (session-3), the payments on-call rotation
(session-6), an OTA booking cancellation (session-5) — plus two matching
this session's own running examples (a failed-UPI-payment support call is
the exact PhonePe scenario used as this session's running example; a
sprint-planning recap is a generic meeting). Each case's
summary is checked against expected phrases the same way session-3's
`test_questions.py` and session-4's `eval_tasks.py` already do: OR-groups,
ANDed together.

**First run — 4/5, a real bug, not a checker artifact:**

```bash
python eval_runner.py
```
```
[PASS] design-system-status
[PASS] oncall-handoff
[FAIL] ota-cancellation
[PASS] sprint-planning
[PASS] payment-support

--- Summary: 4/5 passed (80%) ---
```

The failure was real: the summarizer's 3 bullets for the cancellation call
never mentioned the booking reference (`MMT7842`) at all — a support-call
summary that drops the one identifier someone would need to look the case
up later. Per the principle that "every real bug you hit becomes a permanent
new test case," this stays in the golden set rather than getting
special-cased away.

**Fix attempt 1 — fixed that case, broke a different one:**

Added "always carry forward identifying details — booking references,
ticket numbers, names" to the summarizer's system prompt. Re-ran the full
set (not just the fixed case):

```
[PASS] design-system-status
[FAIL] oncall-handoff        <- regressed: now never says "payments"
[PASS] ota-cancellation      <- fixed: now includes "MMT 7842"
[PASS] sprint-planning
[PASS] payment-support

--- Summary: 4/5 passed (80%) ---
```

Still 4/5 — just a different case failing. Fixing "keep identifiers" pulled
the model's attention away from naming which *service* (payments) the
on-call handoff was for. This is exactly why a golden set has to be re-run
in full on every change, not spot-checked on the one case you were fixing —
a prompt edit that looks like a strict improvement can silently regress
something else.

**Fix attempt 2 — generalized the instruction, 5/5:**

Reworded to "every named entity — people, teams, services, booking/ticket
references — must appear in at least one bullet; do not let naming one
entity push another one out," instead of listing "identifiers" as a special
case. Re-ran again:

```bash
python eval_runner.py
```
```
[PASS] design-system-status   (stt_ms=6150 llm_ms=1909 total_ms=8059)
[PASS] oncall-handoff         (stt_ms=3520 llm_ms=1757 total_ms=5277)
[PASS] ota-cancellation       (stt_ms=3756 llm_ms=2378 total_ms=6134)
[PASS] sprint-planning        (stt_ms=3739 llm_ms=1659 total_ms=5398)
[PASS] payment-support        (stt_ms=2799 llm_ms=2193 total_ms=4992)

--- Summary: 5/5 passed (100%) ---
Avg stt_ms=3993  avg llm_ms=1979  avg total_ms=5972
```

5/5, with the specific fix generalized rather than case-specific — the
prompt in [voice_summary.py](voice_summary.py) is left at this final version.

## Homework 4 — batch vs. live, and the first input to red-team

**Batch or live for this product?** A meeting/call-recap summarizer like
this one belongs squarely in **batch** (the "user can wait 30-60s" case for
choosing batch):
nobody needs a live transcript mid-call for a QA/status-recap use case, the
~5-7s total latency measured above is already fine for an async "call
ended, summary is ready" flow, and batch means one Whisper call instead of
a persistent streaming connection — cheaper and far simpler to debug, per
the general observation that a batch pipeline is "easier to debug, full
transcript in your logs." Live STT would only earn its complexity if this
became a real-time agent (e.g. the MakeMyTrip voice-assistant scenario used
elsewhere in this session), which this isn't.

**First input to red-team:** an audio clip with **no clear 3-bullet
structure at all** — a rambling, off-topic, or silent recording. The current
prompt assumes the transcript always has 3 summarizable facts; it's never
been tested against "the meeting got cancelled, everyone just said hi and
left" or a transcript that's mostly silence/noise. The golden set's own
lesson (above) says exactly what to do with whatever that test surfaces:
add it as a 6th permanent case, not a one-off fix.
