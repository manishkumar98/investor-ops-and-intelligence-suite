"""Adapted from M3 phase1/src/booking/booking_code_generator.py + slot_resolver.py"""
import json
import random
from datetime import date
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


def _to_12h(time_str: str) -> str:
    """Convert 24h 'HH:MM' to 12h '2:00 PM' / '9:30 AM'."""
    try:
        h, m = (int(x) for x in time_str.split(":")[:2])
        am_pm = "AM" if h < 12 else "PM"
        h12 = h % 12 or 12
        return f"{h12}:{m:02d} {am_pm}"
    except Exception:
        return time_str


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
    data = json.loads(Path(calendar_path).read_text())
    if isinstance(data, dict):
        return data.get("available_slots", data.get("slots", list(data.values())[0] if data else []))
    return data


def _slot_start_dt(slot: dict):
    """Parse the slot's datetime from 'start' ISO string, 'date'+'time', or 'day'+'time'."""
    from datetime import datetime as _dt
    # Primary: ISO 'start' field (e.g. "2026-04-27T10:00:00")
    if "start" in slot:
        try:
            return _dt.fromisoformat(slot["start"])
        except Exception:
            pass
    # Legacy: separate 'date' and 'time' fields
    if "date" in slot and "time" in slot:
        try:
            return _dt.fromisoformat(f"{slot['date']}T{slot['time']}:00")
        except Exception:
            pass
    return None


def _slot_day_name(slot: dict) -> str:
    """Return weekday name from a slot, supporting 'start' ISO, 'date', or 'day' keys."""
    if "day" in slot:
        return slot["day"].lower()
    dt = _slot_start_dt(slot)
    if dt:
        return dt.strftime("%A").lower()
    return ""


def _slot_available(slot: dict) -> bool:
    """Return True if the slot is not booked / is available."""
    if slot.get("booked") is True:
        return False
    if slot.get("status") == "BOOKED":
        return False
    if slot.get("available") is False:
        return False
    return True


def match_slots(calendar: list[dict], day_pref: str | None, period: str | None) -> list[dict]:
    """Return up to 2 available slots matching day and time-of-day preference."""
    available = [s for s in calendar if _slot_available(s)]
    if not available:
        return []

    # Day filter
    if day_pref:
        day_lower = day_pref.lower()
        target_weekday = next((v for k, v in _DAY_MAP.items() if k in day_lower), None)
        if target_weekday is not None:
            matched = []
            for s in available:
                sday = _slot_day_name(s)
                if sday:
                    slot_wd = _DAY_MAP.get(sday[:3])
                    if slot_wd == target_weekday:
                        matched.append(s)
            # If user asked for a specific day and none match, return empty — triggers waitlist
            available = matched
        else:
            filtered = [s for s in available if day_lower in _slot_day_name(s)]
            if filtered:
                available = filtered

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
            # Support both legacy 'time' key and ISO 'start' datetime
            slot_hour = None
            if "time" in s:
                try:
                    slot_hour = int(s["time"].split(":")[0])
                except (ValueError, IndexError):
                    pass
            if slot_hour is None:
                dt = _slot_start_dt(s)
                if dt:
                    slot_hour = dt.hour
            if period_band and slot_hour is not None:
                if period_band[0] <= slot_hour < period_band[1]:
                    time_matched.append(s)
        if time_matched:
            available = time_matched

    return available[:2]


def book(slot: dict, topic: str, session: dict) -> dict:
    """Write booking details to session and return the detail dict."""
    code = generate_booking_code()

    # Extract day_name and time_str from 'start' ISO, or legacy 'day'/'date'/'time' keys
    day_name = slot.get("day", "")
    time_str = slot.get("time", "")
    slot_date = slot.get("date", str(date.today()))

    dt = _slot_start_dt(slot)
    if dt:
        if not day_name:
            day_name = dt.strftime("%A")
        if not time_str:
            time_str = dt.strftime("%H:%M")
        slot_date = dt.strftime("%Y-%m-%d")

    slot_str = f"{day_name.title()}, {slot_date} at {_to_12h(time_str)} IST".strip(", ")

    detail = {
        "date":         slot_date,
        "topic":        topic,
        "slot":         slot_str,
        "time":         time_str,
        "day":          day_name,
        "tz":           "IST",
        "booking_code": code,
    }

    session["booking_code"]   = code
    session["booking_detail"] = detail
    session["call_completed"] = True

    return detail
