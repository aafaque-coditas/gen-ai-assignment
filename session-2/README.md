# Session 2 Assignment — Prompt Engineering

Each task lives in its own folder with its own README (setup, usage, and
**results**); both import a shared API-access helper from the session
root.

```
session-2/
  llm_client.py            <- shared: get_client(), call_model()
  task-1-sentiment/
    sentiment.py
    movies.py
    README.md              <- Task 1 write-up + results
  task-2-math-solver/
    math_solver.py
    math_problems.py
    README.md              <- Task 2 write-up + results
```

- **[task-1-sentiment/](task-1-sentiment/README.md)** — sentiment analysis
  comparison (zero-shot vs. few-shot) on real movies via the OMDb API.
  Result: 65% both ways, plus a real finding about *why*.
- **[task-2-math-solver/](task-2-math-solver/README.md)** — chain-of-thought
  word-problem solver, CLI. Result: 10/10 (100%).
- **[llm_client.py](llm_client.py)** — the OpenAI client setup both tasks
  import (`get_client()`, `call_model()`). Neither task needs an
  interactive chat loop or a temperature demo, so this is just the
  API-access plumbing, not a chatbot. Each task script adds `session-2/`
  to its import path at startup (`sys.path.insert`) since it lives one
  level down, in its own task folder.

## Setup

```bash
cd session-2
pip install -r requirements.txt
```

Make sure the repo root `.env` (two levels up from a task folder) has
`OPENAI_API_KEY=sk-...`. See [../session-1/README.md](../session-1/README.md)
for the note on why that key is actually an OpenRouter key and how
`llm_client.py` auto-detects it.
