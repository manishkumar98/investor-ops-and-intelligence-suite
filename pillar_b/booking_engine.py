import json
import random
import re
import string
from datetime import date, datetime
from pathlib import Path


def generate_booking_code(prefix: str = "NL") -> str:
    """Generate NL-[A-Z][0-9]{3} booking code."""
    letter = random.choice(string.ascii_uppercase)
    digits = "".join(random.choices(string.digits, k=3))
    code = f"{prefix}-{letter}{digits}"
    assert re.match(r"^(NL|WL)-[A-Z]\d{3}$", code), f"Invalid booking code: {code}"
    return code


def load_calendar(calendar_path: str) -> list[dict]:
    return json.loads(Path(calendar_path).read_text())


def match_slots(calendar: list[dict], day_pref: str | None, period: str | None) -> list[dict]:
    """Return up to 2 slots matching day and period preference."""
    if not calendar:
        return []

    matches = []
    for slot in calendar:
        slot_day    = slot.get("day", "").lower()
        slot_period = slot.get("period", "").lower()
        slot_avail  = slot.get("available", True)

        if not slot_avail:
            continue

        day_ok    = (day_pref is None) or (day_pref in slot_day)
        period_ok = (period is None)   or (period in slot_period)

        if day_ok and period_ok:
            matches.append(slot)
        if len(matches) >= 2:
            break

    return matches


def book(slot: dict, topic: str, session: dict) -> dict:
    """Write booking details to session and return the detail dict."""
    code = generate_booking_code()
    today = str(date.today())
    slot_str = f"{slot.get('day', '').title()} {slot.get('time', '')} IST"

    detail = {
        "date":         today,
        "topic":        topic,
        "slot":         slot_str,
        "time":         slot.get("time", ""),
        "day":          slot.get("day", ""),
        "tz":           "IST",
        "booking_code": code,
    }

    session["booking_code"]   = code
    session["booking_detail"] = detail
    session["call_completed"] = True

    return detail
