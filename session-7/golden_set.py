"""
Session 7 Assignment - Homework item 3: a 5-case golden set
=================================================================
Each case is a ~30s spoken script -- synthesized to audio/ by audio_gen.py,
since there's no microphone in this environment (see audio_gen.py's
docstring) -- plus the phrases voice_summary.py's 3-bullet summary must
contain to pass. Same "list of OR-groups, ANDed together" style as every
earlier session's test/eval set (session-3/test_questions.py,
session-4/eval_tasks.py): the summary must contain at least one phrase from
EVERY group.

Domains are deliberately reused from earlier sessions where it fit (design
system project = session-3's doc, on-call rotation = session-6, OTA booking
= session-5) plus two matching this session's own running examples (a
failed-UPI-payment support call is the exact PhonePe scenario used as this
session's running example; a sprint-planning recap is a generic "meeting
recap" case).
"""

GOLDEN_CASES = [
    {
        "id": "design-system-status",
        "audio_file": "case-1-design-system.wav",
        "script": (
            "Quick status update on the design system project. We shipped the "
            "button and input components last week, and the color token "
            "migration is now complete across all three product teams. The "
            "main blocker right now is a legacy CSS override in the checkout "
            "flow, which is still overriding our new spacing tokens. I have "
            "filed a ticket for that. Next week we are planning to start the "
            "typography rollout, and QA sign-off is expected by Friday. "
            "Overall we are on track to hit the mid-month deadline."
        ),
        "checks": [
            ["button", "input"],
            ["color token", "migration"],
            ["checkout", "css override"],
        ],
    },
    {
        "id": "oncall-handoff",
        "audio_file": "case-2-oncall-handoff.wav",
        "script": (
            "Handing off the on-call rotation for the payments service. In "
            "the last shift there were two paging incidents. One was a false "
            "alarm from a monitoring threshold set too low, and I have "
            "already adjusted it. The second was a real timeout in the "
            "settlement job around 2 A M, which I mitigated by restarting "
            "the worker, but the root cause is still open, so I have filed a "
            "ticket for the next on-call engineer. No other open incidents "
            "right now. Priya is picking up the rotation starting today."
        ),
        "checks": [
            ["payments"],
            ["false alarm", "monitoring threshold"],
            ["settlement job", "timeout"],
        ],
    },
    {
        "id": "ota-cancellation",
        "audio_file": "case-3-ota-cancellation.wav",
        "script": (
            "Recap of the support call about booking M M T 7 8 4 2. The "
            "customer wanted to cancel their Delhi to Goa flight and asked "
            "about a refund. I looked up the booking and found it is a "
            "non-refundable fare booked six hours ago, so per policy they "
            "are not eligible for any refund outside the one hour free "
            "cancellation window. The customer was not happy about that, so "
            "I offered a travel credit as a goodwill gesture instead, which "
            "they accepted. No refund was processed, but a travel credit was "
            "issued for the full amount."
        ),
        "checks": [
            ["mmt7842", "mmt 7842", "mmt-7842"],
            ["non-refundable", "no refund", "not eligible"],
            ["travel credit"],
        ],
    },
    {
        "id": "sprint-planning",
        "audio_file": "case-4-sprint-planning.wav",
        "script": (
            "Quick recap of today's sprint planning. We committed to eight "
            "stories for this sprint, mostly focused on the checkout "
            "redesign and the new notifications service. The biggest risk "
            "flagged was the notifications service depending on a third "
            "party vendor A P I that does not have a sandbox environment "
            "yet, so that story is now blocked until the vendor responds. We "
            "moved that story to the next sprint and pulled in a smaller bug "
            "fix instead to keep the sprint full. Standup times stay the "
            "same, nine thirty every morning."
        ),
        "checks": [
            ["eight stories", "checkout redesign", "notifications"],
            ["vendor", "sandbox", "blocked"],
            ["next sprint"],
        ],
    },
    {
        "id": "payment-support",
        "audio_file": "case-5-payment-support.wav",
        "script": (
            "Summary of the support call regarding a failed U P I payment. "
            "The customer said money was deducted from their bank account "
            "but the merchant never received it and the order was never "
            "confirmed. I checked the transaction and confirmed it failed at "
            "the bank's end after the debit, which means it qualifies for an "
            "automatic reversal. The refund will be credited back within two "
            "to three business days. I gave the customer the reference "
            "number for tracking and let them know to reach out again if the "
            "amount is not credited within that window."
        ),
        "checks": [
            ["upi", "deducted"],
            ["automatic reversal", "refund"],
            ["two to three business days", "2 to 3 business days", "2-3 business days"],
        ],
    },
]
