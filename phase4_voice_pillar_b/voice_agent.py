"""Voice Agent FSM — M3-integrated version.

Integrates:
- PII scrubber (input guard, M3 phase1)
- Compliance guard (output guard, M3 phase2)
- DialogueContext (M3 phase2 state tracker)
- RAG injector for what_to_prepare (M3 phase0)
- Intent classifier with Groq→Anthropic→rule-based chain (M3 phase2)
- 8-state FSM compatible with app.py interface
"""
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from config import SECURE_BASE_URL
from .intent_classifier import classify
from .slot_filler import extract_topic, extract_time_pref
from .booking_engine import load_calendar, match_slots, book, _to_12h
from .pii_scrubber import scrub_pii
from .compliance_guard import ComplianceGuard
from .dialogue_states import DialogueContext, DialogueState, TOPIC_LABELS, IST  # IST used in __init__
from .rag_injector import get_rag_context

_guard = ComplianceGuard()

DISCLAIMER = (
    "This is an informational service only — not investment advice. "
    "I'll help you book a tentative call with a human advisor."
)


def _slot_display(slot: dict) -> str:
    """Return 'Day, YYYY-MM-DD at HH:MM IST' from a slot dict."""
    from .booking_engine import _slot_start_dt
    day = slot.get("day", "")
    time_str = slot.get("time", "")
    slot_date = slot.get("date", "")
    dt = _slot_start_dt(slot)
    if dt:
        if not day:
            day = dt.strftime("%A")
        if not time_str:
            time_str = dt.strftime("%H:%M")
        if not slot_date:
            slot_date = dt.strftime("%Y-%m-%d")
    date_part = f", {slot_date}" if slot_date else ""
    return f"{day.title()}{date_part} at {_to_12h(time_str)} IST".strip()


def _tts(text: str) -> bytes | None:
    """TTS: Sarvam AI bulbul:v2 → gTTS fallback."""
    try:
        from voice.tts_engine import TTSEngine
        r = TTSEngine().synthesise(text, language="en-IN")
        if not r.is_empty:
            return r.audio_bytes
    except Exception as exc:
        print(f"[voice_agent] Sarvam TTS failed: {exc}")
    try:
        import io
        from gtts import gTTS
        buf = io.BytesIO()
        gTTS(text=text, lang="en", tld="co.in", slow=False).write_to_fp(buf)
        buf.seek(0)
        return buf.read()
    except Exception as exc:
        print(f"[voice_agent] gTTS fallback failed: {exc}")
        return None


class VoiceAgent:
    """8-state FSM: GREET → INTENT → TOPIC → TIMEPREF → OFFERSLOTS → CONFIRM → BOOKED / WAITLIST."""

    STATES = ("GREET", "INTENT", "TOPIC", "TIMEPREF", "OFFERSLOTS", "CONFIRM", "BOOKED", "WAITLIST")

    def __init__(self, session: dict, calendar_path: str = "data/mock_calendar.json"):
        self.session = session
        self.calendar = load_calendar(calendar_path)
        self.state = "GREET"
        self._topic: str | None = None
        self._time_pref: dict = {}
        self._offered_slots: list[dict] = []
        self._chosen_slot: dict | None = None
        self._all_available: list[dict] = []   # full list of available slots for pagination
        self._slot_page: int = 0               # which page of 2 slots we're on

        # M3 DialogueContext for rich slot tracking
        call_id = str(uuid.uuid4())[:8].upper()
        self._ctx = DialogueContext(
            call_id=call_id,
            session_start_ist=datetime.now(IST),
            current_state=DialogueState.IDLE,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _available_days_hint(self) -> str:
        """Return a short spoken hint of available days from the calendar, e.g. 'Monday, Tuesday and Wednesday'."""
        from .booking_engine import _slot_available, _slot_day_name
        seen = []
        for s in self.calendar:
            if _slot_available(s):
                day = _slot_day_name(s).capitalize()
                if day and day not in seen:
                    seen.append(day)
        if not seen:
            return ""
        if len(seen) == 1:
            return seen[0]
        return ", ".join(seen[:-1]) + " and " + seen[-1]

    def _get_topic_label(self, topic: str | None = None) -> str:
        """Human-readable label for a topic key, handling the special 'top_theme' key."""
        t = topic or self._topic or ""
        if t == "top_theme":
            return self.session.get("top_theme", "Top Theme")
        return TOPIC_LABELS.get(t, t) if t else "General Query"

    def _topic_options(self) -> str:
        """Return spoken topic options, prepending the current week's top theme if available."""
        top = self.session.get("top_theme", "")
        base = (
            "KYC and Onboarding, SIP and Mandates, Statements and Tax, "
            "Withdrawals and Timelines, or Account Changes and Nominee Updates"
        )
        if top:
            return f"this week's top theme — {top}, {base}"
        return base

    @staticmethod
    def _parse_specific_hour(text: str) -> int | None:
        """'2 pm', '2 p.m.', '14:00' → hour in 24h. 'morning' → None."""
        import re as _re
        # Normalise a.m./p.m. → am/pm
        norm = _re.sub(r'\b([ap])\.m\.?\b', r'\1m', text.lower())
        m = _re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', norm)
        if m:
            h, ap = int(m.group(1)), m.group(3).lower()
            if ap == "pm" and h != 12:
                h += 12
            elif ap == "am" and h == 12:
                h = 0
            return h
        m = _re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', norm)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _parse_ordinal_day(day_str: str) -> int | None:
        """'28th' or '28' → 28, 'monday' → None."""
        import re as _re
        if not day_str:
            return None
        m = _re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', day_str.lower())
        if m:
            val = int(m.group(1))
            if 1 <= val <= 31:
                return val
        return None

    @staticmethod
    def _slot_hour(slot: dict) -> int:
        """Return slot start hour (0-23), or -1 if unknown."""
        from .booking_engine import _slot_start_dt
        dt = _slot_start_dt(slot)
        if dt:
            return dt.hour
        t = slot.get("time", "")
        if t:
            try:
                return int(t.split(":")[0])
            except Exception:
                pass
        return -1

    def _load_all_available(self, day: str | None = None, period: str | None = None) -> None:
        """Populate self._all_available and reset pagination. Optionally filter by day/period."""
        from .booking_engine import _slot_available
        if day or period:
            self._all_available = match_slots(self.calendar, day, period) * 100  # already limited to 2; expand
            # re-fetch without the :2 cap by inlining the filter
            from .booking_engine import _slot_day_name, _slot_start_dt, _DAY_MAP, _TIME_BAND_MAP
            available = [s for s in self.calendar if _slot_available(s)]
            if day:
                day_lower = day.lower()
                target_wd = next((v for k, v in _DAY_MAP.items() if k in day_lower), None)
                if target_wd is not None:
                    available = [s for s in available if _DAY_MAP.get(_slot_day_name(s)[:3]) == target_wd]
                else:
                    filtered = [s for s in available if day_lower in _slot_day_name(s)]
                    if filtered:
                        available = filtered
            if period and available:
                period_lower = period.lower()
                band = _TIME_BAND_MAP.get(period_lower)
                matched = []
                for s in available:
                    if period_lower in s.get("period", "").lower():
                        matched.append(s)
                        continue
                    h = None
                    if "time" in s:
                        try:
                            h = int(s["time"].split(":")[0])
                        except Exception:
                            pass
                    if h is None:
                        dt = _slot_start_dt(s)
                        if dt:
                            h = dt.hour
                    if band and h is not None and band[0] <= h < band[1]:
                        matched.append(s)
                if matched:
                    available = matched
            self._all_available = available
        else:
            self._all_available = [s for s in self.calendar if _slot_available(s)]
        self._slot_page = 0

    def _offer_next_page(self) -> str:
        """Present the next 2 slots from _all_available. Falls to waitlist when exhausted."""
        start = self._slot_page * 2
        batch = self._all_available[start:start + 2]
        if not batch:
            self._ctx.current_state = DialogueState.WAITLIST_OFFERED
            self.state = "WAITLIST"
            return self._handle_waitlist("")
        self._slot_page += 1
        self._offered_slots = batch
        self._ctx.offered_slots = batch
        self._ctx.current_state = DialogueState.SLOTS_OFFERED
        self.state = "OFFERSLOTS"
        slot_lines = [f"Option {i}: {_slot_display(s)}" for i, s in enumerate(batch, 1)]
        has_more = len(self._all_available) > start + 2
        more_hint = " Say 'other' to see more options." if has_more else ""
        return (
            "Here are available slots:\n"
            + "\n".join(slot_lines)
            + f"\nWhich option works for you? (say '1' or '2'){more_hint}"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def get_greeting(self) -> tuple[str, bytes | None]:
        """Return (text, audio). Called once before first step()."""
        top_theme = self.session.get("top_theme")
        theme_line = (
            f"I see many users are asking about {top_theme} this week — "
            "I can help you book a call for that! "
        ) if top_theme else ""

        text = (
            f"Welcome to Investor Ops Booking. {DISCLAIMER} "
            f"{theme_line}"
            "Would you like to book a call, reschedule, or cancel an appointment?"
        )
        self._ctx.current_state = DialogueState.GREETED
        return text, _tts(text)

    def step(self, utterance: str) -> tuple[str, bytes | None]:
        """Process one user turn. Returns (response_text, audio_or_None)."""
        self._ctx.turn_count += 1

        # ── M3 Layer 1: PII scrub input ────────────────────────────────────
        pii_result = scrub_pii(utterance)
        clean_input = pii_result.cleaned_text
        if pii_result.pii_found:
            pii_warning = (
                "⚠️ Personal information detected and redacted. "
                "Please don't share sensitive details on this call — "
                "you'll receive a secure link to submit your contact info after booking. "
            )
            response_text = pii_warning + self._dispatch(clean_input)
        else:
            response_text = self._dispatch(clean_input)

        # ── M3 Layer 3: Compliance guard output ───────────────────────────
        response_text = _guard.check_and_gate(response_text)

        # ── Interaction log ───────────────────────────────────────────────
        self._log_interaction(utterance, response_text)

        return response_text, _tts(response_text)

    def _log_interaction(self, user_text: str, agent_text: str) -> None:
        """Append one JSONL line to data/logs/voice_interactions.jsonl."""
        try:
            log_path = Path("data/logs/voice_interactions.jsonl")
            log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts":        datetime.now(IST).isoformat(),
                "call_id":   self._ctx.call_id,
                "turn":      self._ctx.turn_count,
                "state":     self.state,
                "user":      user_text,
                "agent":     agent_text,
                "topic":     self._topic,
                "booking":   self._ctx.booking_code,
            }
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass  # logging must never break the call

    # ── FSM dispatcher ────────────────────────────────────────────────────────

    def _dispatch(self, utterance: str) -> str:
        handler = getattr(self, f"_handle_{self.state.lower()}", self._handle_unknown)
        return handler(utterance)

    # ── State Handlers ────────────────────────────────────────────────────────

    def _handle_greet(self, utterance: str) -> str:
        self.state = "INTENT"
        self._ctx.current_state = DialogueState.DISCLAIMER_CONFIRMED
        return self._handle_intent(utterance)

    def _handle_intent(self, utterance: str) -> str:
        result = classify(utterance, context=self._ctx.slots_filled())
        intent = result.get("intent", "book_new")
        slots  = result.get("slots", {})

        self._ctx.intent = intent
        self._ctx.apply_slots(slots)
        self._ctx.current_state = DialogueState.INTENT_IDENTIFIED

        if result.get("compliance_flag") in ("refuse_advice", "refuse_pii", "out_of_scope"):
            return result.get("speech", "I can only help with advisor appointment scheduling.")

        if intent == "end_call":
            self._ctx.current_state = DialogueState.END
            return "Thank you for calling. We'll be happy to help whenever you're ready. Goodbye!"

        if intent == "timezone_query":
            return (
                "All our advisor slots are in IST (India Standard Time, UTC+5:30). "
                "Please use a timezone converter for your local equivalent. "
                "Shall I show you available slots?"
            )

        if intent == "book_new":
            if self._ctx.topic:
                self._topic = self._ctx.topic
                self._ctx.current_state = DialogueState.TOPIC_COLLECTED
                label = self._get_topic_label()
                self._load_all_available()
                return f"Great! I'll help you book a call about {label}. " + self._offer_next_page()
            self.state = "TOPIC"
            return (
                "Great! What would you like to discuss with the advisor? "
                f"Options: {self._topic_options()}."
            )

        if intent == "reschedule":
            self._ctx.current_state = DialogueState.RESCHEDULE_CODE_COLLECTED
            return (
                "To reschedule, please share your existing booking code "
                "(format: NL-XXXX) and I'll note the request for our team."
            )

        if intent == "cancel":
            self._ctx.current_state = DialogueState.CANCEL_CODE_COLLECTED
            return (
                "To cancel, please share your booking code (format: NL-XXXX) "
                "and our team will process it within one business day."
            )

        if intent == "what_to_prepare":
            return self._handle_what_to_prepare(utterance)

        if intent == "check_availability":
            self.state = "TIMEPREF"
            self._ctx.current_state = DialogueState.TIME_PREFERENCE_COLLECTED
            return (
                "I can check available slots. "
                "Which day and time works for you? (e.g., 'Thursday morning')"
            )

        return "I didn't catch that. Would you like to book a new appointment with an advisor?"

    def _handle_what_to_prepare(self, utterance: str) -> str:
        """Use RAG injector for topic-specific checklist (M3 phase0)."""
        topic = self._ctx.topic or self._topic
        self._ctx.prepare_shown = True

        rag_context = get_rag_context(
            query=utterance or "what documents do I need",
            topic=topic or "kyc_onboarding",
        )
        response = (
            f"Here's what to have ready for your advisor call:\n\n{rag_context}\n\n"
            "Would you like to book a call now? I can check available slots."
        )
        return response

    def _is_selecting_top_theme(self, utterance: str) -> bool:
        """Return True if the utterance is selecting the week's top theme."""
        top = self.session.get("top_theme", "")
        if not top:
            return False
        low = utterance.lower().strip()
        # Direct trigger words that clearly mean "the first/top option"
        _triggers = {"that", "that one", "first", "first one", "top", "top theme",
                     "the theme", "this week", "this week's", "it", "same"}
        if any(low == t or low.startswith(t + " ") or low.endswith(" " + t) for t in _triggers):
            return True
        # Word-overlap: ≥2 words in common with the theme text
        _top_words = {w for w in top.lower().split() if len(w) > 3}
        _utter_words = set(low.split())
        return len(_top_words & _utter_words) >= 2

    def _handle_topic(self, utterance: str) -> str:
        # Check if user is selecting this week's top theme before standard extraction
        top = self.session.get("top_theme", "")
        if top and self._is_selecting_top_theme(utterance):
            self._topic = "top_theme"
            self._ctx.topic = "top_theme"
            self._ctx.current_state = DialogueState.TOPIC_COLLECTED
            self._load_all_available()
            return f"Got it — {top}. " + self._offer_next_page()

        topic = extract_topic(utterance)
        if not topic:
            self._ctx.topic_retry_count += 1
            return f"I didn't catch the topic. Please choose one: {self._topic_options()}."
        self._topic = topic
        self._ctx.topic = topic
        self._ctx.current_state = DialogueState.TOPIC_COLLECTED
        label = self._get_topic_label(topic)
        self._load_all_available()
        return f"Got it — {label}. " + self._offer_next_page()

    def _handle_timepref(self, utterance: str) -> str:
        # Re-classify in case user expressed intent change
        result = classify(utterance, context=self._ctx.slots_filled())
        if result.get("intent") == "end_call":
            return "No problem! Call us whenever you're ready. Goodbye!"

        self._time_pref = extract_time_pref(utterance)
        day    = self._ctx.day_preference or self._time_pref.get("day")
        period = self._ctx.time_preference or self._time_pref.get("period")

        # Merge extracted slots into context
        if day:
            self._ctx.day_preference = day
        if period:
            self._ctx.time_preference = period

        self._offered_slots = match_slots(self.calendar, day, period)

        if not self._offered_slots:
            self._ctx.current_state = DialogueState.WAITLIST_OFFERED
            self.state = "WAITLIST"
            return self._handle_waitlist(utterance)

        self._ctx.offered_slots = self._offered_slots
        self._ctx.current_state = DialogueState.SLOTS_OFFERED
        self.state = "OFFERSLOTS"

        slot_lines = [
            f"Option {i}: {_slot_display(s)}"
            for i, s in enumerate(self._offered_slots, 1)
        ]
        return (
            "Here are the available slots:\n"
            + "\n".join(slot_lines)
            + "\nWhich option would you prefer? (say '1' or '2')"
        )

    def _handle_offerslots(self, utterance: str) -> str:
        # Re-classify to catch end_call / change of mind
        result = classify(utterance, context=self._ctx.slots_filled())
        if result.get("intent") == "end_call":
            return "No problem! Call us whenever you're ready. Goodbye!"

        lower = utterance.lower()

        # Detect if user is requesting a different slot or stating new day/time preference
        _change_signals = {"other", "another", "different", "else", "instead",
                           "change", "different time", "not these", "none of these"}
        wants_change = any(w in lower for w in _change_signals)

        new_pref = extract_time_pref(utterance)
        new_day = new_pref.get("day")
        new_period = new_pref.get("period")

        # A new specific day/time that differs from what was previously offered
        has_new_day = new_day and new_day != self._ctx.day_preference
        has_new_period = new_period and new_period != self._ctx.time_preference

        if wants_change or has_new_day or has_new_period:
            # Parse directly from raw utterance — covers "p.m." dots and ordinals
            specific_hour = self._parse_specific_hour(utterance)
            ordinal_day   = self._parse_ordinal_day(new_day) if new_day else None

            if has_new_day or has_new_period:
                if new_day:
                    self._ctx.day_preference = new_day
                if new_period:
                    self._ctx.time_preference = new_period

                # Build a precisely filtered candidate pool from the full calendar
                from .booking_engine import _slot_available, _slot_start_dt, _slot_day_name, _DAY_MAP
                pool = [s for s in self.calendar if _slot_available(s)]

                if ordinal_day is not None:
                    day_filtered = [s for s in pool
                                    if (dt := _slot_start_dt(s)) and dt.day == ordinal_day]
                    if day_filtered:
                        pool = day_filtered
                elif new_day:
                    day_lower = new_day.lower()
                    target_wd = next((v for k, v in _DAY_MAP.items() if k in day_lower), None)
                    if target_wd is not None:
                        wf = [s for s in pool
                              if _DAY_MAP.get(_slot_day_name(s)[:3]) == target_wd]
                        if wf:
                            pool = wf

                if specific_hour is not None:
                    hour_filtered = [s for s in pool
                                     if abs(self._slot_hour(s) - specific_hour) <= 1]
                    if hour_filtered:
                        pool = hour_filtered

                # User specified both a day AND a specific time → skip options, go direct to confirm
                if (ordinal_day is not None or new_day) and specific_hour is not None and pool:
                    best = min(pool, key=lambda s: abs(self._slot_hour(s) - specific_hour))
                    self._chosen_slot = best
                    self._ctx.resolved_slot = best
                    self._ctx.current_state = DialogueState.SLOT_CONFIRMED
                    self.state = "CONFIRM"
                    return (
                        f"Got it! To confirm: booking for {self._get_topic_label()} "
                        f"on {_slot_display(best)}. "
                        "Does that sound right? (say 'yes' to confirm)"
                    )

                # Only day or only time specified — show filtered page
                self._all_available = pool
                self._slot_page = 0
                if not self._all_available:
                    self._ctx.current_state = DialogueState.WAITLIST_OFFERED
                    self.state = "WAITLIST"
                    return self._handle_waitlist(utterance)
            # "other"/"more" with no new preference — paginate current pool
            return self._offer_next_page()

        idx = 0
        if "2" in lower or "second" in lower or "two" in lower:
            idx = 1

        if idx >= len(self._offered_slots):
            idx = 0

        self._chosen_slot = self._offered_slots[idx]
        self._ctx.resolved_slot = self._chosen_slot
        self._ctx.current_state = DialogueState.SLOT_CONFIRMED
        self.state = "CONFIRM"

        topic_label = self._get_topic_label()
        slot_str = _slot_display(self._chosen_slot)
        return (
            f"To confirm: booking for {topic_label} on {slot_str}. "
            "Does that sound right? (say 'yes' to confirm)"
        )

    def _handle_confirm(self, utterance: str) -> str:
        lower = utterance.lower()
        if any(w in lower for w in ("yes", "confirm", "ok", "sure", "correct", "yep", "yeah")):
            return self._complete_booking()
        if any(w in lower for w in ("no", "change", "different", "other")):
            self.state = "OFFERSLOTS"
            self._ctx.current_state = DialogueState.SLOTS_OFFERED
            return "No problem. " + self._handle_offerslots(utterance)
        return "Please say 'yes' to confirm the booking or 'no' to choose a different slot."

    def _handle_booked(self, utterance: str) -> str:
        lower = utterance.lower()
        # Graceful farewell on any goodbye / thanks signal
        if any(w in lower for w in ("bye", "goodbye", "thank", "thanks", "that's all",
                                    "that is all", "nothing else", "no thanks", "done")):
            return "Thank you for calling! Have a wonderful day. Goodbye!"
        code = self.session.get("booking_code", "N/A")
        return (
            f"Your appointment is confirmed! Booking code: {code}. "
            f"Complete your details at {SECURE_BASE_URL}/complete/{code}. "
            "Is there anything else I can help you with?"
        )

    def _handle_waitlist(self, _: str) -> str:
        from .waitlist_handler import create_waitlist_entry

        day_pref  = self._ctx.day_preference or "flexible"
        time_pref = self._ctx.time_preference or "any"
        topic     = self._topic or self._ctx.topic or "General"

        entry = create_waitlist_entry(
            topic=topic,
            day_preference=day_pref,
            time_preference=time_pref,
        )
        code = entry.waitlist_code
        self._ctx.waitlist_code = code
        self._ctx.current_state = DialogueState.WAITLIST_CONFIRMED
        self.session["booking_code"] = code
        self.state = "WAITLIST"

        from phase7_pillar_c_hitl.mcp_client import enqueue_action
        from datetime import date

        enqueue_action(
            self.session,
            type="notes_append",
            payload={
                "doc_title": "Advisor Pre-Bookings",
                "entry": {
                    "date":         str(date.today()),
                    "topic":        topic,
                    "slot":         f"Waitlist ({day_pref} {time_pref})",
                    "booking_code": code,
                    "status":       "WAITLIST",
                },
            },
            source="m3_voice",
        )
        enqueue_action(
            self.session,
            type="email_draft",
            payload={
                "subject": f"Waitlist Request — {topic} — {code}",
                "body": (
                    f"A user has been added to the waitlist.\n"
                    f"Topic: {topic}\n"
                    f"Preferred: {day_pref} {time_pref}\n"
                    f"Waitlist code: {code}\n"
                    f"Entry: {entry.summary()}\n"
                    "Please follow up to offer available slots."
                ),
            },
            source="m3_voice",
        )

        return (
            f"No exact slots match your preference right now. "
            f"I've added you to the waitlist with code {code}. "
            "Our team will reach out with available slots soon. "
            f"Complete your details at {SECURE_BASE_URL}/complete/{code}"
        )

    def _handle_unknown(self, _: str) -> str:
        return "I'm not sure how to help with that. Would you like to book an advisor call?"

    # ── Booking completion ────────────────────────────────────────────────────

    def _complete_booking(self) -> str:
        if not self._chosen_slot or not self._topic:
            return "Something went wrong. Let's start again — what topic would you like to discuss?"

        detail = book(self._chosen_slot, self._topic, self.session)
        code   = detail["booking_code"]
        self._ctx.booking_code = code
        if not self._ctx.topic:
            self._ctx.topic = self._topic
        self._ctx.current_state = DialogueState.BOOKING_COMPLETE
        self.state = "BOOKED"

        topic_label = self._get_topic_label()

        # ── Enqueue for Approval Center HITL panel ────────────────────────
        from phase7_pillar_c_hitl.mcp_client import enqueue_action

        enqueue_action(
            self.session,
            type="calendar_hold",
            payload={
                "title":        f"Advisor Q&A — {topic_label} — {code}",
                "date":         detail["date"],
                "time":         detail["time"],
                "tz":           "IST",
                "topic":        self._topic,
                "booking_code": code,
            },
            source="m3_voice",
        )
        pulse       = self.session.get("weekly_pulse", "")
        fee_bullets = self.session.get("fee_bullets", [])
        top_3       = self.session.get("top_3_themes", [])
        fee_scenario = self.session.get("fee_sources", [])

        enqueue_action(
            self.session,
            type="notes_append",
            payload={
                "doc_title": "Advisor Pre-Bookings",
                "entry": {
                    "date":         detail["date"],
                    "topic":        topic_label,
                    "slot":         detail["slot"],
                    "booking_code": code,
                    "status":       "CONFIRMED",
                    # M2 context — links pulse data to this booking
                    "top_3_themes": top_3,
                    "weekly_pulse": pulse[:300] if pulse else "",
                    "fee_scenario": fee_bullets[0] if fee_bullets else "",
                },
            },
            source="m3_voice",
        )

        pulse       = self.session.get("weekly_pulse", "")
        fee_bullets = self.session.get("fee_bullets", [])
        fee_sources = self.session.get("fee_sources", [])
        top_3       = self.session.get("top_3_themes", [])

        market_ctx  = " ".join(pulse.split()[:120]) if pulse else "No pulse data available."
        themes_line = (
            "Top themes: " + "  |  ".join(f"#{i+1} {t}" for i, t in enumerate(top_3[:3]))
            if top_3 else ""
        )
        fee_section = "\n".join(f"  • {b}" for b in fee_bullets) if fee_bullets else "  N/A"
        fee_src_line = "\n  Sources: " + ", ".join(fee_sources) if fee_sources else ""
        div = "─" * 52

        enqueue_action(
            self.session,
            type="email_draft",
            payload={
                "subject":        f"Pre-Booking Alert: {topic_label} — {detail['date']} @ {detail['slot']}",
                "booking_code":   code,
                "topic_label":    topic_label,
                "slot_start_ist": detail["slot"],
                "body": (
                    f"Dear Advisor,\n\n"
                    f"A new advisor appointment has been pre-booked via the INDMoney Voice Agent. "
                    f"Please review the details below and prepare accordingly.\n\n"
                    f"{div}\n"
                    f" MEETING DETAILS\n"
                    f"{div}\n"
                    f"  Booking Code : {code}\n"
                    f"  Topic        : {topic_label}\n"
                    f"  Date         : {detail['date']}\n"
                    f"  Time Slot    : {detail['slot']} IST\n"
                    f"  Status       : CONFIRMED\n\n"
                    f"{div}\n"
                    f" MARKET CONTEXT  (this week's customer pulse)\n"
                    f"{div}\n"
                    + (f"  {themes_line}\n\n" if themes_line else "")
                    + f"  {market_ctx}\n\n"
                    f"{div}\n"
                    f" FEE CONTEXT\n"
                    f"{div}\n"
                    f"{fee_section}{fee_src_line}\n\n"
                    f"{div}\n\n"
                    f"⚠  No investment advice implied. Factual summaries only.\n\n"
                    f"Best regards,\n"
                    f"INDMoney Advisor Suite\n"
                    f"Auto-generated — do not reply to this message."
                ),
            },
            source="m3_voice",
        )

        enqueue_action(
            self.session,
            type="sheet_entry",
            payload={
                "booking_code":   code,
                "topic_key":      self._topic,
                "topic_label":    topic_label,
                "slot_start_ist": detail["slot"],
                "date":           detail["date"],
                "status":         "CONFIRMED",
                "call_id":        self._ctx.call_id,
            },
            source="m3_voice",
        )

        self._ctx.calendar_hold_created = True
        self._ctx.notes_appended = True
        self._ctx.email_drafted = True

        # ── Dispatch to Google Calendar, Sheets, and Gmail in background ──
        def _mcp_dispatch_bg(session: dict, ctx, chosen_slot: dict, topic: str, tlabel: str) -> None:
            try:
                from phase6_pillar_b_voice.src.mcp.mcp_orchestrator import build_payload, dispatch_mcp_sync
                from datetime import datetime as _dt
                payload = build_payload(ctx)
                if topic == "top_theme":
                    payload.topic_label = tlabel
                _slot = ctx.resolved_slot or chosen_slot
                if _slot:
                    _iso = _slot.get("start", "")
                    if _iso:
                        _sdt = _dt.fromisoformat(_iso)
                        _h = _sdt.hour % 12 or 12
                        _ap = "AM" if _sdt.hour < 12 else "PM"
                        payload.slot_start_ist = (
                            f"{_sdt.strftime('%A, %Y-%m-%d')} at {_h}:{_sdt.strftime('%M')} {_ap} IST"
                        )
                mcp_results = dispatch_mcp_sync(payload)
                session["mcp_dispatch"] = {
                    "calendar": mcp_results.calendar.success,
                    "sheets":   mcp_results.sheets.success,
                    "email":    mcp_results.email.success,
                    "summary":  mcp_results.summary(),
                }
            except Exception as exc:
                session["mcp_dispatch"] = {"error": str(exc)}

        threading.Thread(
            target=_mcp_dispatch_bg,
            args=(self.session, self._ctx, self._chosen_slot, self._topic, topic_label),
            daemon=True,
        ).start()

        return (
            f"Your appointment is confirmed! "
            f"Booking code: {code}. "
            f"Slot: {detail['slot']}. "
            f"Please complete your details at {SECURE_BASE_URL}/complete/{code}. "
            "No personal information is shared on this call. "
            "Thank you for calling — have a great day!"
        )
