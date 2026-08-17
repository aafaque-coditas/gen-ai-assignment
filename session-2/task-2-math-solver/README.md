# Task 2 — Math Problem Solver (Chain of Thought)

A CLI tool that solves math word problems using chain-of-thought
prompting: every prompt ends with *"Let's think step by step"* plus an
instruction to close with a structured `Final Answer: <number>` line (the
"reliable ask" pattern), so the code can reliably extract just the number
via regex instead of parsing free-form prose.

Uses [../llm_client.py](../llm_client.py) (shared with Task 1) for API
access — see [../../session-1/README.md](../../session-1/README.md) for
the note on the OpenRouter-key auto-detection.

## Run it

```bash
cd task-2-math-solver
pip install -r ../requirements.txt
python math_solver.py                    # interactive
python math_solver.py --test             # run the 10 built-in problems
python math_solver.py --test --verbose   # + print each problem's full reasoning
```

## Result

**Test mode — 10/10 correct (100%)**, verified live against
[math_problems.py](math_problems.py)'s 10 word problems:

```
Testing 10 problems (model=openai/gpt-4o-mini)...

[OK  ] Problem 1: Roger has 5 tennis balls...            Expected: 11 | Got: 11
[OK  ] Problem 2: A bakery sells cupcakes...              Expected: 8  | Got: 8
[OK  ] Problem 3: There are 24 students...                Expected: 15 | Got: 15
[OK  ] Problem 4: A train travels at 60 mph...             Expected: 150 | Got: 150
[OK  ] Problem 5: Sarah has $45...                         Expected: 25 | Got: 25
[OK  ] Problem 6: A rectangular garden...                  Expected: 40 | Got: 40
[OK  ] Problem 7: A recipe calls for 2 cups...              Expected: 5  | Got: 5
[OK  ] Problem 8: Tom is saving for a $150 bike...          Expected: 7  | Got: 7
[OK  ] Problem 9: A store had 100 items...                  Expected: 52 | Got: 52
[OK  ] Problem 10: Three friends split a $90 bill...         Expected: 33 | Got: 33

--- Summary: 10/10 correct (100%) ---
```

**Interactive mode** — verified with a brand-new problem not in the test
set, a two-step discount + tax calculation:

```
Problem: If a shirt costs $25 and is discounted by 20%, then 8% sales
tax is added, what is the final price in dollars?

1. Discount: 25 * 0.20 = 5
2. Price after discount: 25 - 5 = 20
3. Sales tax: 20 * 0.08 = 1.6
4. Final price: 20 + 1.6 = 21.6

Final Answer: 21.6

>>> Final Answer: 21.6
```

No surprise compared to Task 1's finding, since these are ordinary
arithmetic word problems, not famous real-world entities the model has
memorized opinions about. Chain-of-thought gives it room to actually work
through the arithmetic instead of guessing, and the structured
`Final Answer:` line makes extraction 100% reliable across all 10 runs.
