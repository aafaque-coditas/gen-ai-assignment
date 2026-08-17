"""
Test questions for test_runner.py, grounded in docs/DS- Technical Case
Study.pdf. Each `checks` entry is a list of acceptable phrasings (OR) --
the answer must contain at least one phrase from EVERY entry (AND across
entries) to pass. `expect_refusal=True` questions are deliberately outside
the document's scope, to verify the context-only guard actually makes the
model say "I don't know" instead of guessing.
"""

REFUSAL_PHRASES = [
    "cannot find", "can't find", "do not know", "don't know", "no information",
    "not mentioned", "not contain", "does not contain", "doesn't contain",
    "not covered", "no mention", "unable to find", "not provided", "not available",
]

TEST_QUESTIONS = [
    {
        "question": "How long did the design system project take to deliver, and what was the originally planned timeline?",
        "checks": [["6 month"], ["12-month", "12 month"]],
    },
    {
        "question": "What frontend technology stack is the design system built on?",
        "checks": [["angular"], ["angular material"]],
    },
    {
        "question": "How is the design system documented, and how is it distributed to product teams?",
        "checks": [["storybook"], ["npm"]],
    },
    {
        "question": "What happens when a design token, like the primary color, is updated?",
        "checks": [["component styles"], ["storybook"]],
    },
    {
        "question": "What is the company's refund policy for returned products?",
        "checks": [],
        "expect_refusal": True,
    },
]
