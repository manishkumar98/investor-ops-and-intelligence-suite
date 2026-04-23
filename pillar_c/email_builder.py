from datetime import date
from config import SECURE_BASE_URL

REQUIRED_KEYS = ["booking_detail", "booking_code", "weekly_pulse", "fee_bullets", "fee_sources"]


def build_email(session: dict) -> dict:
    """Assemble the advisor email from session state.

    Returns {"subject": str, "body": str}.
    Raises ValueError if any of the 5 required keys is missing.
    """
    for key in REQUIRED_KEYS:
        if not session.get(key):
            raise ValueError(f"build_email: missing required session key: '{key}'")

    detail      = session["booking_detail"]
    code        = session["booking_code"]
    pulse       = session["weekly_pulse"]
    fee_bullets = session["fee_bullets"]
    fee_sources = session["fee_sources"]

    topic = detail.get("topic", "General")
    slot  = detail.get("slot", "TBD")
    today = str(date.today())

    subject = f"Advisor Pre-Booking: {topic} — {today}"

    market_ctx    = " ".join(pulse.split()[:100])
    fee_section   = "\n".join(f"• {b}" for b in fee_bullets)
    sources_section = "\n".join(fee_sources)

    body = (
        f"Hi [Advisor Name],\n\n"
        f"{'─' * 50}\n"
        f"Booking Summary:\n"
        f"  Code:  {code}\n"
        f"  Topic: {topic}\n"
        f"  Slot:  {slot}\n"
        f"{'─' * 50}\n\n"
        f"📊 Market Context (first 100 words of this week's pulse):\n"
        f'"{market_ctx}"\n\n'
        f"{'─' * 50}\n"
        f"📋 Fee Context:\n"
        f"{fee_section}\n"
        f"Source: {sources_section}\n\n"
        f"{'─' * 50}\n"
        f"⚠ No investment advice implied.\n"
        f"Complete booking: {SECURE_BASE_URL}/complete/{code}"
    )

    return {"subject": subject, "body": body}
