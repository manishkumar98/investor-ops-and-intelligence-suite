"""Adapted from M3 phase1/src/booking/booking_code_generator.py + slot_resolver.py"""
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pytz

IST = pytz.timezone("Asia/Kolkata")

# Excludes visually ambiguous chars: 0, O, 1, I  (from M3 booking_code_generator.py)
_SAFE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

_DAY_MAP = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}

_TIME_BAND_MAP = {
    "morning": (9, 12), "afternoon": (12, 17),
    "evening": (17, 20), "night": (18, 21),
    "noon": (12, 14), "midday": (11, 14),
    "am": (9, 12), "pm": (12, 17),
}


def generate_booking_code(existing: set | None = None) -> str:
    """NL-XXXX — 4 safe alphanumeric chars (no 0/O/1/I ambiguity). From M3."""
    existing = existing or set()
    for _ in range(1000):
        suffix = "".join(random.choices(_SAFE_CHARS, k=4))
        code = f"NL-{suffix}"
        if code not in existing:
            return code
    raise RuntimeError("Could not generate unique booking code after 1000 attempts.")


def generate_waitlist_code(existing: set | None = None) -> str:
    """NL-WXXX — W prefix + 3 safe chars. From M3."""
    existing = existing or set()
    for _ in range(1000):
        suffix = "".join(random.choices(_SAFE_CHARS, k=3))
        code = f"NL-W{suffix}"
        if code not in existing:
            return code
    raise RuntimeError("Could not generate unique waitlist code after 1000 attempts.")


def is_valid_booking_code(code: str) -> bool:
    if not isinstance(code, str) or not code.startswith("NL-"):
        return False
    suffix = code[3:]
    return len(suffix) == 4 and not suffix.startswith("W") and all(c in _SAFE_CHARS for c in suffix)


def load_calendar(calendar_path: str) -> list[dict]:
    return json.loads(Path(calendar_path).read_text())


def match_slots(calendar: list[dict], day_pref: str | None, period: str | None) -> list[dict]:
    """Return up to 2 available slots matching day and time-of-day preference.
    Adapted from M3 slot_resolver._resolve_slots_mock.
    """
    available = [s for s in calendar if s.get("available", True) or s.get("status") == "AVAILABLE"]
    if not available:
        return []

    # Day filter
    if day_pref:
        day_lower = day_pref.lower()
        target_weekday = next((v for k, v in _DAY_MAP.items() if k in day_lower), None)
        if target_weekday is not None:
            today = datetime.now(IST)
            days_ahead = (target_weekday - today.weekday()) % 7 or 7
            target_day_name = (today + timedelta(days=days_ahead)).strftime("%A").lower()
            available = [s for s in available if target_day_name in s.get("day", "").lower()]
        else:
            available = [s for s in available if day_lower in s.get("day", "").lower()]

    # Period / time band filter
    if period and available:
        period_lower = period.lower()
        period_band = _TIME_BAND_MAP.get(period_lower)
        time_matched = []
        for s in available:
            slot_period = s.get("period", "").lower()
            if period_lower in slot_period:
                time_matched.append(s)
                continue
            if period_band and "time" in s:
                try:
                    slot_hour = int(s["time"].split(":")[0])
                    if period_band[0] <= slot_hour < period_band[1]:
                        time_matched.append(s)
                except (ValueError, IndexError):
                    pass
        if time_matched:
            available = time_matched

    return available[:2]


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
