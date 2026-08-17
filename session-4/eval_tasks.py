"""
5 tasks for eval_runner.py's small eval (a stretch goal), in the same
"list of OR-groups, ANDed together" style as session-3/test_questions.py.

Two of these are deliberately not tool-requiring or not what they look like:
  - Task 4 needs BOTH search_docs and calculator, in that order.
  - Task 5 is general knowledge with no internal tool that could help --
    `expect_no_tools=True` checks the agent doesn't waste a call anyway,
    the over-triggering RAG failure mode ("always retrieve
    5 chunks, even for 'what time is it?'").
"""

EVAL_TASKS = [
    {
        "task": "What is 84 * 17?",
        "checks": [["1428"]],
    },
    {
        "task": "What is the IMDb rating of the movie Inception?",
        "checks": [["8.8"]],
    },
    {
        "task": "What frontend technology stack is the design system built on?",
        "checks": [["angular"]],
    },
    {
        "task": "How many months did the design system project take to deliver, and what is that number times 4?",
        "checks": [["24"]],
    },
    {
        "task": "What is the capital of France?",
        "checks": [["paris"]],
        "expect_no_tools": True,
    },
]
