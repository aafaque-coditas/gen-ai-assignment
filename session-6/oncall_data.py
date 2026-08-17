"""
Session 6 Assignment - Challenge: simulated on-call rotation "internal API"
================================================================================
Stands in for a real internal rotation service (PagerDuty, Opsgenie, an
in-house tool) the way session-4's outbox.log stood in for a real email
provider -- structurally real (a lookup that can succeed or fail), never
actually calling anything external.
"""

ONCALL_ROTATION = {
    "payments": {"engineer": "Priya Sharma", "phone": "+91-98xxx-11223", "started": "2026-08-08"},
    "checkout": {"engineer": "Rahul Verma", "phone": "+91-98xxx-44556", "started": "2026-08-10"},
    "auth": {"engineer": "Ananya Iyer", "phone": "+91-98xxx-77889", "started": "2026-08-09"},
}


def fetch_oncall_from_api(service: str) -> str:
    entry = ONCALL_ROTATION.get(service.strip().lower())
    if not entry:
        known = ", ".join(sorted(ONCALL_ROTATION))
        return f"No on-call rotation found for service '{service}'. Known services: {known}."
    return (
        f"{entry['engineer']} is on-call for {service} (since {entry['started']}). "
        f"Page at {entry['phone']}."
    )
