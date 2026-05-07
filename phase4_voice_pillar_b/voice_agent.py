"""Voice Agent FSM — M3-integrated version.

Integrates:
- PII scrubber (input guard, M3 phase1)
- Compliance guard (output guard, M3 phase2)
- DialogueContext (M3 phase2 state tracker)
- RAG injector for what_to_prepare (M3 phase0)
- Intent classifier with Groq→Anthropic→rule-based chain (M3 phase2)
- 11-state FSM: GREET / INTENT / TOPIC / TIMEPREF / OFFERSLOTS / CONFIRM /
                BOOKED / WAITLIST_OFFER / WAITLIST /
                RESCHEDULE_CODE / CANCEL_CODE / CANCEL_CONFIRM
"""
import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from config import SECURE_BASE_URL
from phase4_voice_pillar_b.intent_classifier import classify
from phase4_voice_pillar_b.slot_filler import extract_topic, extract_time_pref
from phase4_voice_pillar_b.booking_engine import load_calendar, book, _to_12h
from phase4_voice_pillar_b.pii_scrubber import scrub_pii
from phase4_voice_pillar_b.compliance_guard import ComplianceGuard
from phase4_voice_pillar_b.dialogue_states import DialogueContext, DialogueState, TOPIC_LABELS, IST
from phase4_voice_pillar_b.rag_injector import get_rag_context

_guard = ComplianceGuard()

DISCLAIMER = (
    "This is an informational service only — not investment advice. "
    "I'll help you book a tentative call with a human advisor."
)

_CODE_RE = re.compile(r'\b([A-Z]{2}-[A-Z0-9]{4,6})\b', re.IGNORECASE)

MAX_NO_INPUT    = 3   # consecutive empty turns before graceful exit
MAX_TOPIC_RETRY = 4   # topic extraction failures before circuit-breaker
MAX_CODE_RETRY  = 3   # bad/unknown booking codes before circuit-breaker


def _slot_display(slot: dict) -> str:
    """Return 'Day, YYYY-MM-DD at HH:MM IST' from a slot dict."""
    from phase4_voice_pillar_b.booking_engine import _slot_start_dt
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
    # Strip any embedded IST/timezone suffix before appending " IST"
    time_clean = time_str.replace(" IST", "").replace(" UTC", "").strip()
    return f"{day.title()}{date_part} at {_to_12h(time_clean)} IST".strip()


def _tts(text: str) -> bytes | None:
    """TTS: Sarvam AI bulbul:v2 → gTTS fallback."""
    try:
        from phase6_pillar_b_voice.voice.tts_engine import TTSEngine
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
    """11-state FSM voice booking agent.

    States (self.state string):
      GREET → INTENT → TOPIC → TIMEPREF → OFFERSLOTS → CONFIRM → BOOKED
      WAITLIST_OFFER → WAITLIST
      RESCHEDULE_CODE → TIMEPREF (reused for new slot)
      CANCEL_CODE → CANCEL_CONFIRM
    """

    STATES = (
        "GREET", "INTENT", "TOPIC", "TIMEPREF", "OFFERSLOTS", "CONFIRM",
        "BOOKED", "WAITLIST_OFFER", "WAITLIST",
        "RESCHEDULE_CODE", "CANCEL_CODE", "CANCEL_CONFIRM",
    )

    def __init__(self, session: dict, calendar_path: str = ""):
        if not calendar_path:
            calendar_path = str(Path(__file__).resolve().parents[1] / "data" / "mock_calendar.json")
        self.session        = session
        self.calendar       = load_calendar(calendar_path)
        self._topic: str | None        = None
        self._time_pref: dict          = {}
        self._offered_slots: list[dict]= []
        self._chosen_slot: dict | None = None
        self._all_available: list[dict]= []
        self._slot_page: int           = 0

        # Counters (Phase A)
        self._no_input_count: int    = 0
        self._topic_retry: int       = 0
        self._code_retry: int        = 0

        # Reschedule / cancel working memory
        self._pending_code: str      = ""   # code being validated
        self._is_reschedule: bool    = False  # True while in reschedule flow

        call_id = str(uuid.uuid4())[:8].upper()
        self._ctx = DialogueContext(
            call_id=call_id,
            session_start_ist=datetime.now(IST),
            current_state=DialogueState.IDLE,
        )

        # Single source of truth — always use _set_state()
        self._state: str = "GREET"

    # ── State property (canonical) ────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @state.setter
    def state(self, value: str) -> None:
        """Keep _ctx.current_state in sync whenever self.state changes."""
        self._state = value
        _state_map = {
            "GREET":          DialogueState.IDLE,
            "INTENT":         DialogueState.DISCLAIMER_CONFIRMED,
            "TOPIC":          DialogueState.INTENT_IDENTIFIED,
            "TIMEPREF":       DialogueState.TOPIC_COLLECTED,
            "OFFERSLOTS":     DialogueState.SLOTS_OFFERED,
            "CONFIRM":        DialogueState.SLOT_CONFIRMED,
            "BOOKED":         DialogueState.BOOKING_COMPLETE,
            "WAITLIST_OFFER": DialogueState.WAITLIST_OFFERED,
            "WAITLIST":       DialogueState.WAITLIST_CONFIRMED,
            "RESCHEDULE_CODE":DialogueState.RESCHEDULE_CODE_COLLECTED,
            "CANCEL_CODE":    DialogueState.CANCEL_CODE_COLLECTED,
            "CANCEL_CONFIRM": DialogueState.CANCEL_CODE_COLLECTED,
        }
        if value in _state_map:
            self._ctx.current_state = _state_map[value]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _available_days_hint(self) -> str:
        from phase4_voice_pillar_b.booking_engine import _slot_available, _slot_day_name
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
        t = topic or self._topic or ""
        if t == "top_theme":
            return self.session.get("top_theme", "Top Theme")
        return TOPIC_LABELS.get(t, t) if t else "General Query"

    def _topic_options(self) -> str:
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
        norm = re.sub(r'\b([ap])\.m\.?\b', r'\1m', text.lower())
        m = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b', norm)
        if m:
            h, ap = int(m.group(1)), m.group(3).lower()
            if ap == "pm" and h != 12:
                h += 12
            elif ap == "am" and h == 12:
                h = 0
            return h
        m = re.search(r'\b([01]?\d|2[0-3]):([0-5]\d)\b', norm)
        if m:
            return int(m.group(1))
        return None

    @staticmethod
    def _parse_ordinal_day(day_str: str) -> int | None:
        if not day_str:
            return None
        m = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', day_str.lower())
        if m:
            val = int(m.group(1))
            if 1 <= val <= 31:
                return val
        return None

    @staticmethod
    def _parse_month_day(text: str) -> tuple[int | None, int | None]:
        """
        Parse date references → (day, month) ints.  Returns (None, None) if not found.

        Handles:
          '9th May' / 'May 9' / '9 may'      → month-name + ordinal
          '5/9' / '5-9' / '5/9/2026'          → DD/MM or DD-MM (day first, Indian convention)
        """
        _MONTHS = {
            "jan": 1, "january": 1, "feb": 2, "february": 2,
            "mar": 3, "march": 3, "apr": 4, "april": 4,
            "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
            "aug": 8, "august": 8, "sep": 9, "september": 9,
            "oct": 10, "october": 10, "nov": 11, "november": 11,
            "dec": 12, "december": 12,
        }
        low = text.lower()
        month_pat = '|'.join(_MONTHS.keys())
        # "9th May" or "May 9th"
        m = re.search(rf'\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pat})\b', low)
        if m:
            day, month_str = int(m.group(1)), m.group(2)
            month = _MONTHS.get(month_str)
            return (day, month) if month and 1 <= day <= 31 else (None, None)
        m = re.search(rf'\b({month_pat})\s+(\d{{1,2}})(?:st|nd|rd|th)?\b', low)
        if m:
            month_str, day = m.group(1), int(m.group(2))
            month = _MONTHS.get(month_str)
            return (day, month) if month and 1 <= day <= 31 else (None, None)
        # "5/9" or "5-9" or "5/9/2026"  (DD/MM Indian convention)
        m = re.search(r'\b(\d{1,2})[/\-](\d{1,2})(?:[/\-]\d{2,4})?\b', low)
        if m:
            day, month = int(m.group(1)), int(m.group(2))
            if 1 <= day <= 31 and 1 <= month <= 12:
                return day, month
        return None, None

    @staticmethod
    def _slot_hour(slot: dict) -> int:
        from phase4_voice_pillar_b.booking_engine import _slot_start_dt
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
        """Populate self._all_available with multi-strategy fallback (Phase B)."""
        from phase4_voice_pillar_b.booking_engine import (
            _slot_available, _slot_start_dt, _slot_day_name,
            _DAY_MAP, resolve_day_pref, parse_time_preference, _today_ist,
        )
        from datetime import date as _date, timedelta
        today = _today_ist()

        all_future = [
            s for s in self.calendar
            if _slot_available(s) and (
                _slot_start_dt(s) is None or _slot_start_dt(s).date() >= today
            )
        ]

        if not day and not period:
            self._all_available = all_future
            self._slot_page = 0
            return

        # ── Strategy 1: exact day + period filter ────────────────────────────
        pool = list(all_future)

        if day:
            resolved = resolve_day_pref(day)
            resolved_lower = resolved.lower().strip()
            if len(resolved_lower) == 10 and resolved_lower[4] == "-":
                try:
                    target_date = _date.fromisoformat(resolved_lower)
                    day_filtered = [s for s in pool if _slot_start_dt(s) and _slot_start_dt(s).date() == target_date]
                    pool = day_filtered if day_filtered else []
                except ValueError:
                    pass
            else:
                target_wd = next(
                    (v for k, v in _DAY_MAP.items() if k == resolved_lower or k in resolved_lower), None
                )
                if target_wd is not None:
                    day_filtered = [s for s in pool if _DAY_MAP.get(_slot_day_name(s)[:3]) == target_wd]
                    if day_filtered:
                        pool = day_filtered
                    else:
                        # ── Strategy 2: day not available → try next week same day ──
                        # (Only if not a specific/pinned date)
                        is_pinned = len(resolved_lower) == 10 and resolved_lower[4] == "-"
                        if not is_pinned:
                            next_week = [
                                s for s in all_future
                                if _slot_start_dt(s) and _slot_start_dt(s).date() >= today + timedelta(days=7)
                                and _DAY_MAP.get(_slot_day_name(s)[:3]) == target_wd
                            ]
                            pool = next_week if next_week else []
                        else:
                            pool = []

        if period and period.lower() not in ("any", "anytime", "flexible", "") and pool:
            time_band, _ = parse_time_preference(period)
            if time_band:
                period_filtered = []
                for s in pool:
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
                    if h is not None and time_band[0] <= h < time_band[1]:
                        period_filtered.append(s)

                if period_filtered:
                    pool = period_filtered
                else:
                    # ── Strategy 3: period not available on that day → same day any time ──
                    # (Only fallback if it was a broad period, not a specific hour)
                    is_specific = any(c.isdigit() for c in (period or ""))
                    if not is_specific:
                        pass # pool stays as day-filtered
                    else:
                        pool = []

        # ── Strategy 4: still empty → broadest available ─────────────────────
        # Only fallback to all future slots if the user didn't specify any constraints.
        if not pool and not day and not period:
            pool = all_future

        self._all_available = pool
        self._slot_page = 0

    def _offer_next_page(self) -> str:
        """Present up to 2 slots. Falls to WAITLIST_OFFER when exhausted."""
        start = self._slot_page * 2
        batch = self._all_available[start:start + 2]
        if not batch:
            self.state = "WAITLIST_OFFER"
            return self._handle_waitlist_offer("")
        self._slot_page += 1
        self._offered_slots = batch
        self._ctx.offered_slots = batch
        self.state = "OFFERSLOTS"
        slot_lines = [f"Option {i}: {_slot_display(s)}" for i, s in enumerate(batch, 1)]
        has_more = len(self._all_available) > start + 2
        more_hint = " Say 'other' to see more options." if has_more else ""
        options_hint = "(say '1')" if len(batch) == 1 else "(say '1' or '2')"
        return (
            "Here are available slots:\n"
            + "\n".join(slot_lines)
            + f"\nWhich option works for you? {options_hint}{more_hint}"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def get_greeting(self) -> tuple[str, bytes | None]:
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
        self.state = "GREET"
        return text, _tts(text)

    def step(self, utterance: str) -> tuple[str, bytes | None]:
        """Process one user turn. Returns (response_text, audio_or_None)."""
        self._ctx.turn_count += 1

        # ── No-input / silence handling ───────────────────────────────────────
        if not utterance or not utterance.strip():
            self._no_input_count += 1
            if self._no_input_count >= MAX_NO_INPUT:
                self.state = "BOOKED"  # terminal — treated as natural end
                farewell = (
                    "I haven't heard anything for a while — ending the call. "
                    "Feel free to call back whenever you're ready. Goodbye!"
                )
                self._log_interaction("", farewell)
                return farewell, _tts(farewell)
            prompts = {
                1: "I didn't catch that — could you say that again?",
                2: "Still here! Please speak when you're ready.",
            }
            msg = prompts.get(self._no_input_count, "I didn't catch that.")
            self._log_interaction("", msg)
            return msg, _tts(msg)
        self._no_input_count = 0  # reset on valid input

        # ── Global end_call intercept (works in any state) ────────────────────
        _low = utterance.lower().strip()
        _end_phrases = (
            "bye", "goodbye", "good bye", "end the call", "hang up",
            "i'm done", "i am done", "that's all", "that is all",
            "nothing else", "no thanks", "no thank you", "never mind",
            "forget it", "not interested", "leave it",
        )
        if self.state not in ("BOOKED",) and any(p in _low for p in _end_phrases):
            self.state = "BOOKED"
            farewell = "Thank you for calling. Feel free to call back whenever you're ready. Goodbye!"
            self._log_interaction(utterance, farewell)
            return farewell, _tts(farewell)

        # ── Global intent-switch intercept (cancel / reschedule) ──────────────
        # Mid-reschedule slot collection (TIMEPREF/OFFERSLOTS/CONFIRM) is excluded —
        # "Monday at 10am" can mis-classify as book_new but we must stay in flow.
        _mid_reschedule_slot = (
            self._is_reschedule
            and self.state in ("TIMEPREF", "OFFERSLOTS", "CONFIRM")
        )
        if (self.state not in ("GREET", "INTENT", "BOOKED",
                               "RESCHEDULE_CODE", "CANCEL_CODE", "CANCEL_CONFIRM")
                and not _mid_reschedule_slot):
            _switch_keywords = {
                "cancel":           ("cancel my", "cancel the booking", "want to cancel",
                                     "cancel my appointment", "cancel my booking",
                                     "cancel this", "please cancel"),
                "reschedule":       ("reschedule", "change my appointment",
                                     "move my booking", "different day instead",
                                     "rebook", "change the slot"),
                "what_to_prepare":  ("what to bring", "what to prepare", "documents needed",
                                     "what should i", "checklist", "what do i need"),
                "check_availability": ("check availability", "when are you free",
                                       "available slots", "free slots"),
            }
            for _new_intent, _kws in _switch_keywords.items():
                if any(k in _low for k in _kws):
                    self.state = "INTENT"
                    _resp = self._dispatch(utterance)
                    self._log_interaction(utterance, _resp)
                    return _resp, _tts(_resp)

        # ── PII scrub input ───────────────────────────────────────────────────
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

        # ── Compliance guard output ───────────────────────────────────────────
        response_text = _guard.check_and_gate(response_text)

        self._log_interaction(utterance, response_text)
        return response_text, _tts(response_text)

    def _log_interaction(self, user_text: str, agent_text: str) -> None:
        try:
            log_path = Path(__file__).resolve().parents[1] / "data" / "logs" / "voice_interactions.jsonl"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {
                "ts":      datetime.now(IST).isoformat(),
                "call_id": self._ctx.call_id,
                "turn":    self._ctx.turn_count,
                "state":   self.state,
                "user":    user_text,
                "agent":   agent_text,
                "topic":   self._topic,
                "booking": self._ctx.booking_code,
            }
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # ── FSM dispatcher ────────────────────────────────────────────────────────

    def _dispatch(self, utterance: str) -> str:
        handler = getattr(self, f"_handle_{self.state.lower()}", self._handle_unknown)
        return handler(utterance)

    # ── State Handlers ────────────────────────────────────────────────────────

    def _handle_greet(self, utterance: str) -> str:
        self.state = "INTENT"
        return self._handle_intent(utterance)

    def _handle_intent(self, utterance: str) -> str:
        result = classify(utterance, context=self._ctx.slots_filled())
        intent = result.get("intent", "book_new")
        slots  = result.get("slots", {})

        self._ctx.intent = intent
        self._ctx.apply_slots(slots)

        if result.get("compliance_flag") in ("refuse_advice", "refuse_pii", "out_of_scope"):
            return result.get("speech", "I can only help with advisor appointment scheduling.")

        if intent == "end_call":
            self.state = "BOOKED"
            return "Thank you for calling. We'll be happy to help whenever you're ready. Goodbye!"

        if intent == "timezone_query":
            return (
                "All our advisor slots are in IST (India Standard Time, UTC+5:30). "
                "Please use a timezone converter for your local equivalent. "
                "Shall I show you available slots?"
            )

        if intent == "book_new":
            # Check if code was embedded in the utterance (user switched from reschedule/cancel)
            if self._ctx.topic:
                self._topic = self._ctx.topic
                label = self._get_topic_label()
                self._load_all_available()
                return f"Great! I'll help you book a call about {label}. " + self._offer_next_page()
            self.state = "TOPIC"
            return (
                "Great! What would you like to discuss with the advisor? "
                f"Options: {self._topic_options()}."
            )

        if intent == "reschedule":
            self._is_reschedule = True
            self._code_retry = 0
            self._pending_code = slots.get("existing_booking_code", "").upper()
            self.state = "RESCHEDULE_CODE"
            if self._pending_code:
                # Code already provided in the same utterance — process immediately
                return self._handle_reschedule_code(self._pending_code)
            return (
                "To reschedule, please share your existing booking code "
                "(for example: NL-AB23)."
            )

        if intent == "cancel":
            self._is_reschedule = False
            self._code_retry = 0
            self._pending_code = slots.get("existing_booking_code", "").upper()
            self.state = "CANCEL_CODE"
            if self._pending_code:
                return self._handle_cancel_code(self._pending_code)
            return (
                "To cancel, please share your booking code "
                "(for example: NL-AB23)."
            )

        if intent == "what_to_prepare":
            return self._handle_what_to_prepare(utterance)

        if intent == "check_availability":
            self._is_reschedule = False
            self.state = "TIMEPREF"
            return (
                "I can check available slots. "
                "Which day and time works for you? (e.g., 'Thursday morning')"
            )

        return "I didn't catch that. Would you like to book a new appointment with an advisor?"

    # ── Reschedule code collection & validation ───────────────────────────────

    def _handle_reschedule_code(self, utterance: str) -> str:
        """Collect and validate booking code for reschedule."""
        code = self._extract_code(utterance)

        if not code:
            self._code_retry += 1
            if self._code_retry >= MAX_CODE_RETRY:
                self.state = "BOOKED"
                return (
                    "I wasn't able to find your booking code after several tries. "
                    "Please contact support or try again. Goodbye!"
                )
            hints = {1: "Please say your code clearly, e.g. 'NL-AB23'.",
                     2: "One more try — your code should be in format NL-XXXX."}
            return f"I didn't catch a valid booking code. {hints.get(self._code_retry, '')}"

        # Validate code exists
        original_topic = self._validate_booking_code(code)
        if original_topic is None:
            self._code_retry += 1
            if self._code_retry >= MAX_CODE_RETRY:
                self.state = "BOOKED"
                return (
                    f"I couldn't find booking {code} after several attempts. "
                    "Please check your code or contact support. Goodbye!"
                )
            return (
                f"I couldn't find a booking with code {code}. "
                "Please double-check and try again."
            )

        # Code valid — restore topic and move to time preference
        self._code_retry = 0
        self._pending_code = code
        if original_topic:
            self._topic = original_topic
            self._ctx.topic = original_topic
        self._is_reschedule = True
        self.state = "TIMEPREF"
        topic_label = self._get_topic_label()
        return (
            f"Found your booking {code} — {topic_label}. "
            "What new day and time would you like? (e.g., 'Monday afternoon')"
        )

    # ── Cancel code collection & validation ──────────────────────────────────

    def _handle_cancel_code(self, utterance: str) -> str:
        """Collect and validate booking code for cancellation."""
        code = self._extract_code(utterance)

        if not code:
            self._code_retry += 1
            if self._code_retry >= MAX_CODE_RETRY:
                self.state = "BOOKED"
                return (
                    "I wasn't able to find your booking code. "
                    "Please contact support or try again. Goodbye!"
                )
            hints = {1: "Please say your code clearly, e.g. 'NL-AB23'.",
                     2: "One more try — your code should be in format NL-XXXX."}
            return f"I didn't catch a valid booking code. {hints.get(self._code_retry, '')}"

        original_topic = self._validate_booking_code(code)
        if original_topic is None:
            self._code_retry += 1
            if self._code_retry >= MAX_CODE_RETRY:
                self.state = "BOOKED"
                return (
                    f"I couldn't find booking {code} after several attempts. "
                    "Please check your code or contact support. Goodbye!"
                )
            return (
                f"I couldn't find a booking with code {code}. "
                "Please double-check and try again."
            )

        self._code_retry = 0
        self._pending_code = code
        if original_topic:
            self._topic = original_topic
            self._ctx.topic = original_topic
        topic_label = self._get_topic_label()
        self.state = "CANCEL_CONFIRM"
        return (
            f"I found booking {code} — {topic_label}. "
            "Just to confirm — would you like to cancel this appointment? "
            "Please say 'yes' to cancel or 'no' to keep it."
        )

    # ── Cancel confirmation ───────────────────────────────────────────────────

    def _handle_cancel_confirm(self, utterance: str) -> str:
        lower = utterance.lower()

        # If user re-states their booking code (e.g. said "NLCZS7" instead of "yes"),
        # treat it as implicit confirmation — this is the most common stuck-state cause.
        restated_code = self._extract_code(utterance)
        if restated_code and restated_code == self._pending_code:
            return self._complete_cancellation()

        # Also accept a raw alphanumeric match that looks like a code fragment
        _stripped = utterance.strip().upper().replace("-", "").replace(" ", "")
        if (
            self._pending_code
            and _stripped
            and _stripped in self._pending_code.replace("-", "")
            and len(_stripped) >= 4
        ):
            return self._complete_cancellation()

        if any(w in lower for w in ("yes", "confirm", "ok", "sure", "go ahead", "yeah", "yep",
                                     "proceed", "cancel it", "do it", "please cancel")):
            return self._complete_cancellation()

        if any(w in lower for w in ("no", "keep", "don't", "cancel that", "never mind",
                                     "nevermind", "keep it", "don't cancel")):
            self.state = "INTENT"
            self._pending_code = ""
            return (
                "No problem — your booking is kept as-is. "
                "Is there anything else I can help you with?"
            )

        return (
            f"Please say 'yes' to cancel booking {self._pending_code}, "
            "or 'no' to keep it."
        )

    def _complete_cancellation(self) -> str:
        """Execute cancellation: enqueue MCP actions and update state."""
        from phase7_pillar_c_hitl.mcp_client import enqueue_action
        from datetime import date

        code = self._pending_code
        topic = self._topic or self._ctx.topic or "General"
        topic_label = self._get_topic_label(topic)

        enqueue_action(
            self.session,
            type="calendar_hold",
            payload={
                "action":       "cancel",
                "booking_code": code,
                "topic":        topic,
                "topic_label":  topic_label,
            },
            source="m3_voice",
        )
        enqueue_action(
            self.session,
            type="notes_append",
            payload={
                "doc_title": "Advisor Pre-Bookings",
                "entry": {
                    "date":         str(date.today()),
                    "topic":        topic_label,
                    "slot":         "CANCELLED",
                    "booking_code": code,
                    "status":       "CANCELLED",
                },
            },
            source="m3_voice",
        )
        enqueue_action(
            self.session,
            type="email_draft",
            payload={
                "subject": f"Cancellation Request — {topic_label} — {code}",
                "body": (
                    f"Booking {code} ({topic_label}) has been requested for cancellation.\n"
                    "Please process the cancellation and notify any waitlisted users."
                ),
            },
            source="m3_voice",
        )
        enqueue_action(
            self.session,
            type="sheet_entry",
            payload={
                "booking_code": code,
                "topic_key":    topic,
                "topic_label":  topic_label,
                "status":       "CANCELLED",
                "date":         str(date.today()),
            },
            source="m3_voice",
        )

        self.session["booking_code"] = code
        self.state = "BOOKED"

        return (
            f"Done — booking {code} has been cancelled. "
            "Your cancellation actions are queued for team review. "
            "Feel free to rebook anytime. Goodbye!"
        )

    # ── Code helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_code(text: str) -> str:
        """Extract booking code from utterance. Returns '' if none found.

        Handles 'NL-AB23', 'N L A B 2 3' (spoken), 'EN EL AB23' (Whisper Indian-English
        mishear of N-L), via the robust regex set in intent_classifier._extract_booking_code.
        """
        # First try the strict pattern
        m = _CODE_RE.search(text)
        if m:
            return m.group(1).upper()
        # Fall back to spoken-form parser
        from phase4_voice_pillar_b.intent_classifier import _extract_booking_code
        return (_extract_booking_code(text) or "").upper()

    @staticmethod
    def _validate_booking_code(code: str) -> str | None:
        """Return original topic string if code exists in session/sheets, else None.

        Tries sheets lookup first; falls back to accepting any well-formed code
        (NL-XXXX pattern) so demo works without live Sheets integration.
        """
        try:
            from phase7_pillar_c_hitl.mcp.sheets_tool import _get_booking_details_sync
            row = _get_booking_details_sync(code)
            if row:
                # Prioritize topic_label for cancellation/reschedule displays
                raw_label = row.get("topic_label") or row.get("topic_key") or "General"
                # Clean up: strip "Advisor Q&A — " and the booking code suffix if present
                clean = re.sub(r'^Advisor Q&A\s*—\s*', '', raw_label)
                clean = re.sub(r'\s*—\s*NL-[A-Z0-9]{4}$', '', clean)
                return clean or "General"
        except Exception as e:
            logger.error(f"Sheet lookup failed for {code}: {e}")
            pass
        return None

    # ── What-to-prepare ───────────────────────────────────────────────────────

    def _handle_what_to_prepare(self, utterance: str) -> str:
        topic = self._ctx.topic or self._topic
        self._ctx.prepare_shown = True
        rag_context = get_rag_context(
            query=utterance or "what documents do I need",
            topic=topic or "kyc_onboarding",
        )
        self.state = "INTENT"  # allow user to say "yes" → book_new flow
        return (
            f"Here's what to have ready for your advisor call:\n\n{rag_context}\n\n"
            "Would you like to book a call now? I can check available slots."
        )

    # ── Top theme selection ───────────────────────────────────────────────────

    def _is_selecting_top_theme(self, utterance: str) -> bool:
        top = self.session.get("top_theme", "")
        if not top:
            return False
        low = utterance.lower().strip()
        _triggers = {"that", "that one", "first", "first one", "top", "top theme",
                     "the theme", "this week", "this week's", "it", "same"}
        if any(low == t or low.startswith(t + " ") or low.endswith(" " + t) for t in _triggers):
            return True
        _top_words = {w for w in top.lower().split() if len(w) > 3}
        _utter_words = set(low.split())
        return len(_top_words & _utter_words) >= 2

    # ── Topic collection with circuit breaker ────────────────────────────────

    def _handle_topic(self, utterance: str) -> str:
        top = self.session.get("top_theme", "")
        if top and self._is_selecting_top_theme(utterance):
            self._topic = "top_theme"
            self._ctx.topic = "top_theme"
            self._topic_retry = 0
            self._load_all_available()
            return f"Got it — {top}. " + self._offer_next_page()

        topic = extract_topic(utterance)
        if not topic:
            self._topic_retry += 1
            if self._topic_retry >= MAX_TOPIC_RETRY:
                self.state = "BOOKED"
                return (
                    "I'm having trouble understanding the topic. "
                    "A human advisor will reach out to assist you directly. "
                    "Thank you for calling — goodbye!"
                )
            msgs = {
                1: f"I didn't catch the topic. Please choose one: {self._topic_options()}.",
                2: f"Still didn't catch it. To connect you with the right advisor, please say one of: {self._topic_options()}.",
                3: f"One last try — please clearly say the topic, for example 'SIP' or 'KYC'.",
            }
            return msgs.get(self._topic_retry, f"Please choose a topic: {self._topic_options()}.")

        self._topic_retry = 0
        self._topic = topic
        self._ctx.topic = topic
        label = self._get_topic_label(topic)
        self._load_all_available()
        return f"Got it — {label}. " + self._offer_next_page()

    # ── Time preference ───────────────────────────────────────────────────────

    def _handle_timepref(self, utterance: str) -> str:
        # Guard: if mid-reschedule, don't let "Monday" trigger book_new
        result = classify(utterance, context=self._ctx.slots_filled())
        if result.get("intent") == "end_call":
            self.state = "BOOKED"
            return "No problem! Call us whenever you're ready. Goodbye!"

        # Ignore book_new intent if we're mid-reschedule slot collection
        if not self._is_reschedule and result.get("intent") in ("cancel", "reschedule"):
            return self._handle_intent(utterance)

        self._time_pref = extract_time_pref(utterance)
        new_day = self._time_pref.get("day")
        new_period = self._time_pref.get("period")

        if new_day:
            self._ctx.day_preference = new_day
        if new_period:
            self._ctx.time_preference = new_period

        day = self._ctx.day_preference
        period = self._ctx.time_preference

        self._load_all_available(day, period)

        from phase4_voice_pillar_b.booking_engine import parse_datetime_summary
        summary, needs_confirm = parse_datetime_summary(day or "", period or "")
        echo = f"I understood: {summary}. "

        if not self._all_available:
            self.state = "WAITLIST_OFFER"
            return (
                f"{echo}I'm sorry, I don't have any available slots for that preference. "
                + self._handle_waitlist_offer(utterance)
            )

        confirm_hint = " Could you confirm that's right?" if needs_confirm else ""
        return echo + confirm_hint + "\n" + self._offer_next_page()

    # ── Slot offering ─────────────────────────────────────────────────────────

    def _handle_offerslots(self, utterance: str) -> str:
        result = classify(utterance, context=self._ctx.slots_filled())
        if result.get("intent") == "end_call":
            self.state = "BOOKED"
            return "No problem! Call us whenever you're ready. Goodbye!"

        # Allow intent switch to cancel/reschedule (but guard mid-reschedule)
        if not self._is_reschedule and result.get("intent") in ("cancel", "reschedule"):
            return self._handle_intent(utterance)

        lower = utterance.lower()

        _change_signals = {"other", "another", "different", "else", "instead",
                           "change", "different time", "not these", "none of these"}
        wants_change = any(w in lower for w in _change_signals)

        new_pref   = extract_time_pref(utterance)
        new_day    = new_pref.get("day")
        new_period = new_pref.get("period")

        # Detect "9th May", "May 9th" etc. that extract_time_pref misses
        _md_day, _md_month = self._parse_month_day(utterance)
        specific_hour = self._parse_specific_hour(utterance)

        has_new_day    = bool(new_day and new_day != self._ctx.day_preference) or _md_day is not None
        has_new_period = new_period and new_period != self._ctx.time_preference
        
        is_matching_offer = False
        if specific_hour is not None:
            for s in (self._offered_slots or []):
                if self._slot_hour(s) == specific_hour:
                    is_matching_offer = True
                    break
        has_new_hour = specific_hour is not None and not is_matching_offer

        if wants_change or has_new_day or has_new_period or has_new_hour:
            ordinal_day = _md_day if _md_day is not None else (self._parse_ordinal_day(new_day) if new_day else None)

            if has_new_day or has_new_period or has_new_hour:
                if new_day:
                    self._ctx.day_preference = new_day
                if new_period:
                    self._ctx.time_preference = new_period
                if specific_hour is not None:
                    # Update period to the specific hour if it's a new request
                    self._ctx.time_preference = f"{specific_hour}:00"
                
                # Clear any previously chosen slot to ensure we search fresh
                self._chosen_slot = None
                self._ctx.resolved_slot = None

                from phase4_voice_pillar_b.booking_engine import (
                    _slot_available, _slot_start_dt, _slot_day_name,
                    _DAY_MAP, resolve_day_pref, _today_ist,
                )
                from datetime import date as _date
                _today = _today_ist()
                pool = [
                    s for s in self.calendar
                    if _slot_available(s) and (
                        _slot_start_dt(s) is None or _slot_start_dt(s).date() >= _today
                    )
                ]

                if ordinal_day is not None:
                    _target_month = _md_month
                    if _target_month is None:
                        # Bare ordinal like "the 15th" — assume current month; roll to next if date passed
                        _target_month = _today.month
                        if ordinal_day < _today.day:
                            _target_month = (_today.month % 12) + 1
                    day_filtered = [s for s in pool
                                    if (dt := _slot_start_dt(s)) and dt.day == ordinal_day
                                    and dt.month == _target_month]
                    if day_filtered:
                        pool = day_filtered
                elif new_day:
                    resolved_day = resolve_day_pref(new_day)
                    resolved_lower = resolved_day.lower().strip()
                    if len(resolved_lower) == 10 and resolved_lower[4] == "-":
                        try:
                            target_date = _date.fromisoformat(resolved_lower)
                            wf = [s for s in pool if _slot_start_dt(s) and _slot_start_dt(s).date() == target_date]
                            if wf:
                                pool = wf
                        except ValueError:
                            pass
                    else:
                        target_wd = next(
                            (v for k, v in _DAY_MAP.items() if k == resolved_lower or k in resolved_lower), None
                        )
                        if target_wd is not None:
                            wf = [s for s in pool if _DAY_MAP.get(_slot_day_name(s)[:3]) == target_wd]
                            if wf:
                                pool = wf

                if specific_hour is not None:
                    hour_filtered = [s for s in pool if abs(self._slot_hour(s) - specific_hour) <= 1]
                    if hour_filtered:
                        # If we have only 1 slot in the ±1h window, but more exist on the same day,
                        # add the next closest slot so the user has two options.
                        if len(hour_filtered) < 2 and len(pool) > len(hour_filtered):
                            others = [s for s in pool if s not in hour_filtered]
                            # Sort others by proximity to the specific hour
                            others.sort(key=lambda s: abs(self._slot_hour(s) - specific_hour))
                            hour_filtered.extend(others[:2 - len(hour_filtered)])
                        pool = hour_filtered

                # Chronological sort
                pool.sort(key=lambda s: _slot_start_dt(s) or datetime.max)
                
                self._all_available = pool
                self._slot_page = 0
                if not self._all_available:
                    self.state = "WAITLIST_OFFER"
                    return self._handle_waitlist_offer(utterance)
            return self._offer_next_page()

        idx = 0
        if "2" in lower or "second" in lower or "two" in lower:
            idx = 1
        
        # If user restated the specific hour, pick that one
        if specific_hour is not None:
            for i, slot in enumerate(self._offered_slots):
                if self._slot_hour(slot) == specific_hour:
                    idx = i
                    break

        if not self._offered_slots:
            # Fallback if session lost offered slots
            self.state = "TIMEPREF"
            return "I'm sorry, I lost track of those options. Which day and time would you like me to look for again?"

        if idx >= len(self._offered_slots):
            idx = 0

        self._chosen_slot = self._offered_slots[idx]
        self._ctx.resolved_slot = self._chosen_slot
        self.state = "CONFIRM"
        topic_label = self._get_topic_label()
        slot_str = _slot_display(self._chosen_slot)
        return (
            f"To confirm: booking for {topic_label} on {slot_str}. "
            "Does that sound right? (say 'yes' to confirm)"
        )

    # ── Booking confirmation ──────────────────────────────────────────────────

    def _handle_confirm(self, utterance: str) -> str:
        lower = utterance.lower()
        if any(w in lower for w in ("yes", "confirm", "ok", "sure", "correct", "yep", "yeah")):
            if self._is_reschedule:
                return self._complete_reschedule()
            return self._complete_booking()
        if any(w in lower for w in ("no", "change", "different", "other")):
            self.state = "OFFERSLOTS"
            return "No problem. " + self._handle_offerslots(utterance)
        # User said a new date/time (e.g. "9th May 10am") instead of yes/no
        # — treat as wanting a different slot
        new_pref = extract_time_pref(utterance)
        specific_hour = self._parse_specific_hour(utterance)
        if new_pref.get("day") or new_pref.get("period") or specific_hour is not None:
            self.state = "OFFERSLOTS"
            return "No problem — let me find that slot. " + self._handle_offerslots(utterance)
        return "Please say 'yes' to confirm or 'no' to choose a different slot."

    # ── Booked / terminal ─────────────────────────────────────────────────────

    def _handle_booked(self, utterance: str) -> str:
        lower = utterance.lower()
        if any(w in lower for w in ("bye", "goodbye", "thank", "thanks", "that's all",
                                    "that is all", "nothing else", "no thanks", "done")):
            return "Thank you for calling! Have a wonderful day. Goodbye!"
        code = self.session.get("booking_code", "N/A")
        return (
            f"Your appointment is confirmed! Booking code: {code}. "
            "Please click the '→ Go to Super-Agent MCP Workflow' button below "
            "to go to the Action Centre and approve your pending actions. "
            "Is there anything else I can help you with?"
        )

    # ── Waitlist offer (Phase B: ask before enrolling) ────────────────────────

    def _handle_waitlist_offer(self, utterance: str) -> str:
        lower = utterance.lower()
        if any(w in lower for w in ("yes", "ok", "sure", "add me", "waitlist", "yeah", "yep")):
            return self._handle_waitlist(utterance)
        if any(w in lower for w in ("no", "other", "different", "try", "change")):
            self.state = "TIMEPREF"
            return "No problem. What day or time would you prefer? I'll look for slots."
        # First call (no user input yet) — just show the prompt
        day_pref  = self._ctx.day_preference or "flexible"
        time_pref = self._ctx.time_preference or "any"
        return (
            f"There are no slots available for {day_pref} {time_pref} right now. "
            "I can add you to the waitlist and our team will reach out when a slot opens. "
            "Would you like to join the waitlist? (say 'yes') "
            "Or say 'other' to try a different day or time."
        )

    def _handle_waitlist(self, _: str) -> str:
        from phase4_voice_pillar_b.waitlist_handler import create_waitlist_entry

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
        self.session["booking_code"] = code
        self.state = "WAITLIST"

        from phase7_pillar_c_hitl.mcp_client import enqueue_action
        from datetime import date

        enqueue_action(
            self.session, type="waitlist_entry",
            payload={
                "waitlist_code":   code,
                "date_pref":       day_pref,
                "time_pref":       time_pref,
                "topic_label":     topic,
                "status":          "ACTIVE",
                "created_at_ist":  datetime.now(IST).isoformat(),
                "call_id":         self._ctx.call_id,
            },
            source="m3_voice",
        )
        enqueue_action(
            self.session, type="notes_append",
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
            self.session, type="email_draft",
            payload={
                "subject": f"Waitlist Request — {topic} — {code}",
                "body": (
                    f"A user has been added to the waitlist.\n"
                    f"Topic: {topic}\nPreferred: {day_pref} {time_pref}\n"
                    f"Waitlist code: {code}\nEntry: {entry.summary()}\n"
                    "Please follow up to offer available slots."
                ),
            },
            source="m3_voice",
        )

        return (
            f"Done! I've added you to the waitlist with code {code}. "
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
        self.state = "BOOKED"

        topic_label = self._get_topic_label()
        self._enqueue_booking_actions(detail, code, topic_label)

        self._ctx.calendar_hold_created = False
        self._ctx.notes_appended = False
        self._ctx.email_drafted = False

        return (
            f"Your appointment is confirmed! "
            f"Booking code: {code}. "
            f"Slot: {detail['slot']}. "
            "Your booking actions are ready for review. "
            "Please click the Go to Super-Agent MCP Workflow button below "
            "to head to the Action Centre and approve the calendar hold, notes, and email draft. "
            "Thank you for calling — have a great day!"
        )

    def _complete_reschedule(self) -> str:
        """Confirm the new slot for a reschedule flow."""
        if not self._chosen_slot:
            return "Something went wrong with the reschedule. Please try again."

        old_code    = self._pending_code
        topic       = self._topic or self._ctx.topic or "General"
        topic_label = self._get_topic_label(topic)

        # Extract precise date/time from the chosen slot (handles ISO 'start' or 'date'/'time' keys)
        from phase4_voice_pillar_b.booking_engine import _slot_start_dt
        dt = _slot_start_dt(self._chosen_slot)
        s_date = self._chosen_slot.get("date") or (dt.strftime("%Y-%m-%d") if dt else "")
        s_time = self._chosen_slot.get("time") or (dt.strftime("%H:%M") if dt else "")
        slot_str = _slot_display(self._chosen_slot)

        from phase7_pillar_c_hitl.mcp_client import enqueue_action
        from datetime import date

        enqueue_action(
            self.session, type="calendar_hold",
            payload={
                "action":       "reschedule",
                "booking_code": old_code,
                "title":        f"Advisor Q&A — {topic_label} — {old_code}",
                "date":         s_date,
                "time":         s_time,
                "tz":           "IST",
                "topic":        topic,
                "topic_label":  topic_label,
            },
            source="m3_voice",
        )
        enqueue_action(
            self.session, type="notes_append",
            payload={
                "doc_title": "Advisor Pre-Bookings",
                "entry": {
                    "date":         str(date.today()),
                    "topic":        topic_label,
                    "slot":         slot_str,
                    "booking_code": old_code,
                    "status":       "RESCHEDULED",
                },
            },
            source="m3_voice",
        )
        enqueue_action(
            self.session, type="email_draft",
            payload={
                "subject":        f"Reschedule Alert: {topic_label} — {old_code}",
                "booking_code":   old_code,
                "topic":          topic,
                "topic_label":    topic_label,
                "date":           s_date,
                "slot_start_ist": slot_str,
                "body": (
                    f"Dear Advisor,\n\nA booking has been rescheduled.\n\n"
                    f"Booking Code: {old_code}\n"
                    f"Topic:        {topic_label}\n"
                    f"New Slot:     {slot_str}\n\n"
                    "Please update the calendar event accordingly."
                ),
            },
            source="m3_voice",
        )
        enqueue_action(
            self.session, type="sheet_entry",
            payload={
                "booking_code":   old_code,
                "topic_key":      topic,
                "topic_label":    topic_label,
                "slot_start_ist": slot_str,
                "date":           s_date,
                "status":         "RESCHEDULED",
            },
            source="m3_voice",
        )

        self.session["booking_code"] = old_code
        self.state = "BOOKED"
        self._is_reschedule = False

        return (
            f"Done! Booking {old_code} has been rescheduled to {slot_str}. "
            "The reschedule actions are queued for team review. "
            "Thank you for calling — have a great day!"
        )

    def _enqueue_booking_actions(self, detail: dict, code: str, topic_label: str) -> None:
        """Run Claude super-agent (or fallback) to enqueue MCP actions."""
        from phase7_pillar_c_hitl.super_agent import run as _super_agent_run
        from phase7_pillar_c_hitl.mcp_client import enqueue_action

        _booking_ctx = {
            "booking_code": code,
            "topic":        self._topic,
            "topic_label":  topic_label,
            "date":         detail["date"],
            "time":         detail.get("time", detail.get("slot", "")),
            "slot":         detail.get("slot", detail.get("time", "")),
            "call_id":      self._ctx.call_id,
        }

        _agent_actions = _super_agent_run(_booking_ctx, self.session)

        if _agent_actions:
            if "mcp_queue" not in self.session:
                self.session["mcp_queue"] = []
            for _action in _agent_actions:
                self.session["mcp_queue"] = [
                    a for a in self.session["mcp_queue"]
                    if not (a["status"] == "pending" and a["type"] == _action["type"]
                            and a.get("source") == _action.get("source"))
                ]
                self.session["mcp_queue"].append(_action)
        else:
            pulse       = self.session.get("weekly_pulse", "")
            fee_bullets = self.session.get("fee_bullets", [])
            fee_sources = self.session.get("fee_sources", [])
            top_3       = self.session.get("top_3_themes", [])
            market_ctx  = " ".join(pulse.split()[:120]) if pulse else "No pulse data available."
            themes_line = (
                "Top themes: " + "  |  ".join(f"#{i+1} {t}" for i, t in enumerate(top_3[:3]))
                if top_3 else ""
            )
            fee_section  = "\n".join(f"  • {b}" for b in fee_bullets) if fee_bullets else "  N/A"
            fee_src_line = "\n  Sources: " + ", ".join(fee_sources) if fee_sources else ""
            div = "─" * 52

            enqueue_action(self.session, type="calendar_hold", source="m3_voice", payload={
                "title":        f"Advisor Q&A — {topic_label} — {code}",
                "date":         detail["date"],
                "time":         detail.get("time", detail.get("slot", "")),
                "tz":           "IST",
                "topic":        self._topic,
                "booking_code": code,
            })
            enqueue_action(self.session, type="notes_append", source="m3_voice", payload={
                "doc_title": "Advisor Pre-Bookings",
                "entry": {
                    "date": detail["date"], "topic": topic_label,
                    "slot": detail.get("slot", ""), "booking_code": code,
                    "status": "CONFIRMED", "top_3_themes": top_3,
                    "weekly_pulse": pulse[:300] if pulse else "",
                    "fee_scenario": fee_bullets[0] if fee_bullets else "",
                },
            })
            enqueue_action(self.session, type="email_draft", source="m3_voice", payload={
                "subject":        f"Pre-Booking Alert: {topic_label} — {detail['date']} @ {detail.get('slot', '')}",
                "booking_code":   code,
                "topic":          self._topic,
                "topic_label":    topic_label,
                "date":           detail["date"],
                "slot_start_ist": detail.get("slot", ""),
                "call_id":        self._ctx.call_id,
                # Structured context fields — used directly by _advisor_html
                "top_themes":     top_3,
                "market_context": market_ctx,
                "fee_bullets":    fee_bullets,
                "fee_sources":    fee_sources,
                # Plain-text body for the HITL preview panel
                "body": (
                    f"Dear Advisor,\n\nA new appointment has been pre-booked.\n\n"
                    f"{div}\n MEETING DETAILS\n{div}\n"
                    f"  Booking Code : {code}\n  Topic        : {topic_label}\n"
                    f"  Date         : {detail['date']}\n  Time Slot    : {detail.get('slot', '')} IST\n\n"
                    f"{div}\n MARKET CONTEXT  (this week's customer pulse)\n{div}\n"
                    + (f"  {themes_line}\n\n" if themes_line else "")
                    + f"  {market_ctx}\n\n"
                    f"{div}\n FEE CONTEXT\n{div}\n{fee_section}{fee_src_line}\n\n"
                    f"\u26a0  No investment advice implied.\n\nBest regards,\nINDMoney Advisor Suite"
                ),
            })
            enqueue_action(self.session, type="sheet_entry", source="m3_voice", payload={
                "booking_code": code, "topic_key": self._topic, "topic_label": topic_label,
                "slot_start_ist": detail.get("slot", ""), "date": detail["date"],
                "status": "CONFIRMED", "call_id": self._ctx.call_id,
            })
