"""
Tiny sample "project" for the filesystem MCP server demo (see
../inspect_filesystem_server.py and ../README.md). Deliberately has a
couple of TODO comments so the classic "Find all TODO
comments in src" example has something real to find.
"""


def charge_card(amount_cents: int, currency: str = "INR") -> dict:
    # TODO: validate currency against the supported-currency list before charging
    return {"status": "charged", "amount_cents": amount_cents, "currency": currency}


def refund(payment_id: str, amount_cents: int) -> dict:
    # TODO: add idempotency key so a retried refund can't double-refund
    return {"status": "refunded", "payment_id": payment_id, "amount_cents": amount_cents}
