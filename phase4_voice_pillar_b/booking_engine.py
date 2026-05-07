"""Adapted from M3 phase1/src/booking/booking_code_generator.py + slot_resolver.py"""
import json
import re
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import pytz

IST = pytz.timezone("Asia/Kolkata")

# Excludes visually ambiguous chars: 0, O, 1, I
_SAFE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

_DAY_MAP = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}

_TIME_BAND_MAP = {
    "early morning": (8, 10), "late morning": (10, 12),
    "morning": (9, 12),
    "early afternoon": (12, 14), "late afternoon": (15, 18),
    "afternoon": (12, 17),
    "early evening": (17, 19), "evening": (17, 20), "night": (18, 21),
    "noon": (12, 14), "midday": (11, 14),
    "am": (9, 12), "pm": (12, 17),
}

_MONTH_MAP = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6,
    "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

# Band → implied am/pm and a sensible display hour
_BAND_AMPM = {
    "early morning": "am", "late morning": "am", "morning": "am",
    "noon": "pm", "midday": "pm",
    "early afternoon": "pm", "late afternoon": "pm", "afternoon": "pm",
    "early evening": "pm", "evening": "pm", "night": "pm",
}
_BAND_DEFAULT_HOUR = {
    "early morning": 8, "late morning": 11, "morning": 10,
    "noon": 12, "midday": 12,
    "early afternoon": 13, "late afternoon": 16, "afternoon": 14,
    "early evening": 17, "evening": 18, "night": 20,
}


def _today_ist() -> date:
    return datetime.now(IST).date()


# ── Day preference parser ────────────────────────────────────────────────────

def parse_day_preference(
    day_pref: str,
    reference_date: datetime | None = None,
) -> tuple[list[datetime], bool]:
    """
    Convert a day preference string to (candidate_dates, confident).

    confident=False → couldn't pin an exact date, fell back to a range.

    Handles:
        "today" / "tomorrow" / "day after tomorrow"
        "Monday" / "next Monday"
        "6th" / "6" → 6th of current or next month
        "6th April" / "April 6" / "6 April 2026"
        "this week" / "next week" → range fallback (confident=False)
    """
    if reference_date is None:
        reference_date = datetime.now(IST)

    pref = day_pref.lower().strip()
    today = reference_date.replace(hour=0, minute=0, second=0, microsecond=0)

    if "today" in pref:
        return [today], True
    if "day after tomorrow" in pref or "overmorrow" in pref:
        return [today + timedelta(days=2)], True
    if "tomorrow" in pref:
        return [today + timedelta(days=1)], True

    force_next_week = pref.startswith("next") and not any(m in pref for m in _MONTH_MAP)

    # Ordinal / numeric day-of-month: "6th", "6th April", "April 6", "6 April 2026"
    ordinal_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", pref)
    if ordinal_match:
        day_num = int(ordinal_match.group(1))
        if 1 <= day_num <= 31:
            target_month = reference_date.month
            target_year  = reference_date.year
            for month_name, month_num in _MONTH_MAP.items():
                if month_name in pref:
                    target_month = month_num
                    if month_num < reference_date.month:
                        target_year += 1
                    break
            year_match = re.search(r"\b(202\d)\b", pref)
            if year_match:
                target_year = int(year_match.group(1))
            try:
                candidate = today.replace(year=target_year, month=target_month, day=day_num)
                if candidate < today and target_month == reference_date.month and not year_match:
                    if target_month == 12:
                        candidate = candidate.replace(year=target_year + 1, month=1)
                    else:
                        candidate = candidate.replace(month=target_month + 1)
                return [candidate], True
            except ValueError:
                pass

    # Weekday name
    for day_name, target_weekday in _DAY_MAP.items():
        if day_name in pref:
            current_weekday = reference_date.weekday()
            days_ahead = (target_weekday - current_weekday) % 7
            if days_ahead == 0 and not force_next_week:
                candidate = today
            else:
                if force_next_week:
                    days_ahead = days_ahead if days_ahead > 0 else 7
                    days_ahead += 7 if days_ahead <= 7 and "next" in pref else 0
                candidate = today + timedelta(days=days_ahead or 7)
            return [candidate], True

    # Fallback: range (not confident)
    days_offset = 8 if "next week" in pref else 1
    return [today + timedelta(days=i) for i in range(days_offset, days_offset + 7)], False


# ── Time preference parser ───────────────────────────────────────────────────

def parse_time_preference(time_pref: str) -> tuple[tuple[int, int] | None, bool]:
    """
    Convert a time preference string to ((start_hour, end_hour), confident).

    Handles:
        "10am" / "10 am" / "10:30am"     → exact 2-hour window, confident
        "2pm" / "2 pm" / "14:00"         → exact 2-hour window, confident
        "2 afternoon" / "morning 10"      → band-resolved hour, confident
        "morning" / "afternoon" / "evening" → named band, confident
        "any" / ""                         → None (no filter)
    """
    pref = time_pref.lower().strip() if time_pref else ""

    if not pref or pref in ("any", "anytime", "any time", "flexible"):
        return None, True

    # Detect time-of-day band (longest match first)
    detected_band: str | None = None
    for band_name in sorted(_BAND_AMPM, key=len, reverse=True):
        if band_name in pref:
            detected_band = band_name
            break

    # Try explicit numeric hour: "10am", "2pm", "10:30", "14:00"
    time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", pref)
    if time_match:
        hour  = int(time_match.group(1))
        am_pm = time_match.group(3)

        if am_pm == "pm" and hour < 12:
            hour += 12
        elif am_pm == "am" and hour == 12:
            hour = 0
        elif am_pm is None and detected_band:
            implied = _BAND_AMPM[detected_band]
            if implied == "pm" and hour < 12:
                hour += 12
            elif implied == "am" and hour == 12:
                hour = 0
        elif am_pm is None and hour <= 6:
            hour += 12  # bare "2" → assume 2 PM

        return (hour, min(23, hour + 2)), True

    # Band-only match
    if detected_band:
        return _TIME_BAND_MAP[detected_band], True

    return None, False


# ── Echo-back summary ────────────────────────────────────────────────────────

def parse_datetime_summary(
    day_pref: str,
    time_pref: str,
    reference_date: datetime | None = None,
) -> tuple[str, bool]:
    """
    Return (human_readable_summary, needs_confirmation).

    Used by the FSM to echo back what was understood before offering slots.
    needs_confirmation=True when the date or time couldn't be parsed confidently.
    """
    if reference_date is None:
        reference_date = datetime.now(IST)

    dates, day_confident = parse_day_preference(day_pref, reference_date) if day_pref else ([], False)
    band,  time_confident = parse_time_preference(time_pref) if time_pref else (None, True)

    # Date summary
    if dates and day_confident:
        date_str = dates[0].strftime("%A, %d %b %Y")
    elif dates:
        date_str = f"sometime from {dates[0].strftime('%d %b %Y')}"
    else:
        date_str = day_pref or "a date to be confirmed"

    # Time summary
    if band and time_confident:
        start_h, end_h = band
        ampm = "AM" if start_h < 12 else "PM"
        disp = start_h
        if start_h == 0: disp = 12
        elif start_h > 12: disp = start_h - 12
        time_str = f"{disp}:00 {ampm} IST"
    elif band:
        for name, rng in _TIME_BAND_MAP.items():
            if rng == band:
                time_str = f"{name} IST"
                break
        else:
            time_str = time_pref or "flexible time"
    else:
        time_str = time_pref or "flexible time"

    needs_confirmation = not day_confident or (not time_confident and band is None)
    return f"{date_str} at {time_str}", needs_confirmation


# ── resolve_day_pref (used by match_slots + _load_all_available) ─────────────

def resolve_day_pref(day_pref: str) -> str:
    """
    Convert relative/named day phrases to YYYY-MM-DD ISO string.
    Weekday names (monday, tuesday…) are returned unchanged for weekday matching.
    """
    if not day_pref:
        return day_pref
    dates, confident = parse_day_preference(day_pref)
    if confident and dates:
        # Only return ISO if it's a pinned date (not a weekday-name result already)
        low = day_pref.lower().strip()
        # If input was a bare weekday name, keep it as weekday name for match_slots
        if low in _DAY_MAP or any(low.startswith(p) for p in ("next ", "this ")):
            # For "next monday" etc, return the resolved ISO date
            if any(low.startswith(p) for p in ("next ", "this ")):
                return dates[0].strftime("%Y-%m-%d")
            return day_pref  # bare "monday" → keep for weekday matching
        return dates[0].strftime("%Y-%m-%d")
    return day_pref


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
    p = Path(calendar_path)
    if not p.exists():
        # Generate a default 2-week rolling calendar so the voice agent always starts
        from datetime import datetime, timedelta
        slots = []
        base = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0)
        for day_offset in range(1, 15):
            d = base + timedelta(days=day_offset)
            if d.weekday() < 5:  # Mon–Fri only
                for hour in [10, 11, 12, 14, 15, 16]:
                    start = d.replace(hour=hour)
                    slots.append({
                        "slot_id": f"S{day_offset}{hour}",
                        "start":   start.isoformat(),
                        "end":     (start + timedelta(hours=1)).isoformat(),
                        "advisor": "ADV-001",
                    })
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"slots": slots}, indent=2))
    data = json.loads(p.read_text())
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
    """Return up to 2 available future slots matching day and time-of-day preference."""
    today = _today_ist()

    # Only future slots (today or later)
    available = [
        s for s in calendar
        if _slot_available(s) and (
            _slot_start_dt(s) is None or _slot_start_dt(s).date() >= today
        )
    ]
    if not available:
        return []

    # Day filter — supports ISO date string (YYYY-MM-DD) or weekday name
    if day_pref:
        resolved = resolve_day_pref(day_pref)
        resolved_lower = resolved.lower().strip()

        # ISO date match (today/tomorrow resolve to this)
        if len(resolved_lower) == 10 and resolved_lower[4] == "-":
            try:
                target_date = date.fromisoformat(resolved_lower)
                matched = [s for s in available if _slot_start_dt(s) and _slot_start_dt(s).date() == target_date]
                available = matched  # empty = triggers waitlist
            except ValueError:
                pass
        else:
            # Weekday name match
            target_weekday = next((v for k, v in _DAY_MAP.items() if k == resolved_lower or k in resolved_lower), None)
            if target_weekday is not None:
                matched = [
                    s for s in available
                    if _DAY_MAP.get(_slot_day_name(s)[:3]) == target_weekday
                ]
                available = matched  # empty = triggers waitlist

    if not available:
        return []

    # Period / time band filter — uses parse_time_preference for exact times + bands
    if period and period.lower() not in ("any", "anytime", "flexible", ""):
        time_band, _ = parse_time_preference(period)
        if time_band:
            time_matched = []
            for s in available:
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
                if slot_hour is not None and time_band[0] <= slot_hour < time_band[1]:
                    time_matched.append(s)
            # Empty = period specified but no slots match → triggers waitlist
            # Empty = period specified but no slots match → triggers waitlist
            available = time_matched

    # Chronological sort
    available.sort(key=lambda x: _slot_start_dt(x) or datetime.max)
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
