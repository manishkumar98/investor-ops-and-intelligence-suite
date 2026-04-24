"""7-state Voice Agent FSM for Investor Ops booking."""
import os
import re

import anthropic

from config import SECURE_BASE_URL
from .intent_classifier import classify
from .slot_filler import extract_topic, extract_time_pref
from .booking_engine import load_calendar, match_slots, book, generate_waitlist_code

# ── Safety patterns (refuse investment advice / PII requests on the call) ──
_SAFETY_PATTERNS = [
    r"(which|what|best|better|recommend).*(fund|invest|scheme)",
    r"(return|profit|earn|gain).*(predict|expect|will|next)",
    r"(pan|aadhaar|account number|email|phone|password)",
]

_client = None

DISCLAIMER = (
    "This is an informational service only — not investment advice. "
    "I'll help you book a tentative call with a human advisor."
)


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def _is_unsafe(utterance: str) -> bool:
    lower = utterance.lower()
    return any(re.search(p, lower) for p in _SAFETY_PATTERNS)


def _tts(text: str) -> bytes | None:
    """Convert text to MP3 audio bytes using OpenAI tts-1. Returns None on failure."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
            response_format="mp3",
        )
        return resp.content
    except Exception as exc:
        print(f"[voice_agent] TTS failed: {exc}")
        return None


class VoiceAgent:
    """7-state FSM: GREET → INTENT → TOPIC → TIMEPREF → OFFERSLOTS → CONFIRM → BOOKED."""

    STATES = ("GREET", "INTENT", "TOPIC", "TIMEPREF", "OFFERSLOTS", "CONFIRM", "BOOKED", "WAITLIST")

    def __init__(self, session: dict, calendar_path: str = "data/mock_calendar.json"):
        self.session = session
        self.calendar = load_calendar(calendar_path)
        self.state = "GREET"
        self._topic: str | None = None
        self._time_pref: dict = {}
        self._offered_slots: list[dict] = []
        self._chosen_slot: dict | None = None

    # ── Public API ────────────────────────────────────────────────────────

    def get_greeting(self) -> tuple[str, bytes | None]:
        """Return (text, audio_bytes). Call once before the first step()."""
        top_theme = self.session.get("top_theme")
        if top_theme:
            theme_line = (
                f"I see many users are asking about {top_theme} this week — "
                f"I can help you book a call for that! "
            )
        else:
            theme_line = ""

        text = (
            f"Welcome to Investor Ops Booking. {DISCLAIMER} "
            f"{theme_line}"
            f"Would you like to book a call, reschedule, or cancel an appointment?"
        )
        return text, _tts(text)

    def step(self, utterance: str) -> tuple[str, bytes | None]:
        """Process one user turn. Returns (response_text, audio_bytes_or_None)."""
        if _is_unsafe(utterance):
            text = (
                "I'm not able to provide investment advice or collect personal information. "
                "Please visit https://www.amfiindia.com for educational resources. "
                "Would you like to book a call with an advisor instead?"
            )
            return text, _tts(text)

        handler = getattr(self, f"_handle_{self.state.lower()}", self._handle_unknown)
        text = handler(utterance)
        return text, _tts(text)

    # ── State Handlers ────────────────────────────────────────────────────

    def _handle_greet(self, utterance: str) -> str:
        self.state = "INTENT"
        return self._handle_intent(utterance)

    def _handle_intent(self, utterance: str) -> str:
        intent_result = classify(utterance)   # returns dict {intent, slots, compliance_flag, speech}
        intent = intent_result.get("intent", "book_new")
        slots  = intent_result.get("slots", {})

        if intent == "book_new":
            # Pre-fill topic from classify slots to reduce turns
            if slots.get("topic"):
                self._topic = slots["topic"]
                self.state = "TIMEPREF"
                return (
                    f"Great! I'll help you book a call about {self._topic}. "
                    "What day and time works best? "
                    "(e.g., 'Monday morning', 'Wednesday afternoon')"
                )
            self.state = "TOPIC"
            return (
                "Great! What would you like to discuss with the advisor? "
                "Options: KYC / Onboarding, SIP / Mandates, Statements / Tax Documents, "
                "Withdrawals & Timelines, or Account Changes / Nominee."
            )
        elif intent == "reschedule":
            return (
                "To reschedule, please share your existing booking code "
                "and I'll note the request for our team. "
                "What is your booking code?"
            )
        elif intent == "cancel":
            return (
                "To cancel, please share your booking code "
                "and our team will process it within one business day."
            )
        elif intent == "what_to_prepare":
            return (
                "Please keep your account details, any relevant statements, "
                "and your specific questions ready. "
                "No personal documents are needed on this call."
            )
        elif intent == "check_availability":
            self.state = "TIMEPREF"
            return (
                "I can check available slots. "
                "Which day and time works for you? "
                "(e.g., 'Thursday morning' or 'Friday afternoon')"
            )
        else:
            return "I didn't catch that. Would you like to book a new appointment?"

    def _handle_topic(self, utterance: str) -> str:
        self._topic = extract_topic(utterance)
        self.state = "TIMEPREF"
        return (
            f"Got it — {self._topic}. "
            "What day and time works best for you? "
            "(e.g., 'Monday morning', 'Wednesday afternoon')"
        )

    def _handle_timepref(self, utterance: str) -> str:
        self._time_pref = extract_time_pref(utterance)
        day = self._time_pref.get("day")
        period = self._time_pref.get("period")

        self._offered_slots = match_slots(self.calendar, day, period)

        if not self._offered_slots:
            self.state = "WAITLIST"
            return self._handle_waitlist(utterance)

        self.state = "OFFERSLOTS"
        slot_lines = []
        for i, s in enumerate(self._offered_slots, 1):
            slot_lines.append(
                f"Option {i}: {s.get('day', '').title()} at {s.get('time', '')} IST"
            )
        return (
            "Here are the available slots:\n"
            + "\n".join(slot_lines)
            + "\nWhich option would you prefer? (say '1' or '2')"
        )

    def _handle_offerslots(self, utterance: str) -> str:
        lower = utterance.lower()
        idx = 0
        if "1" in lower or "first" in lower or "one" in lower:
            idx = 0
        elif "2" in lower or "second" in lower or "two" in lower:
            idx = 1

        if idx >= len(self._offered_slots):
            idx = 0

        self._chosen_slot = self._offered_slots[idx]
        self.state = "CONFIRM"

        topic_str = self._topic or "General Query"
        slot_str  = f"{self._chosen_slot.get('day', '').title()} at {self._chosen_slot.get('time', '')} IST"
        return (
            f"To confirm: booking for {topic_str} on {slot_str}. "
            "Does that sound right? (say 'yes' to confirm)"
        )

    def _handle_confirm(self, utterance: str) -> str:
        if "yes" in utterance.lower() or "confirm" in utterance.lower() or "ok" in utterance.lower():
            return self._complete_booking()
        self.state = "OFFERSLOTS"
        return "No problem. Would you like to choose a different slot?"

    def _handle_booked(self, _: str) -> str:
        code = self.session.get("booking_code", "N/A")
        return (
            f"Your appointment is confirmed! Booking code: {code}. "
            f"Please complete your details at {SECURE_BASE_URL}/complete/{code} — "
            "no personal information is collected on this call. "
            "Is there anything else I can help you with?"
        )

    def _handle_waitlist(self, _: str) -> str:
        code = generate_waitlist_code()
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
                    "topic":        self._topic or "General",
                    "slot":         "Waitlist",
                    "booking_code": code,
                },
            },
            source="m3_voice",
        )
        enqueue_action(
            self.session,
            type="email_draft",
            payload={
                "subject": f"Waitlist Request — {self._topic or 'General'} — {code}",
                "body": (
                    f"A user has been added to the waitlist.\n"
                    f"Topic: {self._topic or 'General'}\n"
                    f"Waitlist code: {code}\n"
                    f"Please follow up to offer available slots."
                ),
            },
            source="m3_voice",
        )

        return (
            f"No exact slots match right now. I've added you to the waitlist "
            f"with code {code}. Our team will reach out with available slots. "
            f"Complete your details at {SECURE_BASE_URL}/complete/{code}"
        )

    def _handle_unknown(self, _: str) -> str:
        return "I'm not sure how to help with that. Would you like to book an advisor call?"

    # ── Booking completion ────────────────────────────────────────────────

    def _complete_booking(self) -> str:
        if not self._chosen_slot or not self._topic:
            return "Something went wrong. Let's start again — what topic would you like to discuss?"

        detail = book(self._chosen_slot, self._topic, self.session)
        code   = detail["booking_code"]
        self.state = "BOOKED"

        from phase7_pillar_c_hitl.mcp_client import enqueue_action
        enqueue_action(
            self.session,
            type="calendar_hold",
            payload={
                "title":        f"Advisor Q&A — {self._topic} — {code}",
                "date":         detail["date"],
                "time":         detail["time"],
                "tz":           "IST",
                "topic":        self._topic,
                "booking_code": code,
            },
            source="m3_voice",
        )
        enqueue_action(
            self.session,
            type="notes_append",
            payload={
                "doc_title": "Advisor Pre-Bookings",
                "entry": {
                    "date":         detail["date"],
                    "topic":        self._topic,
                    "slot":         detail["slot"],
                    "booking_code": code,
                },
            },
            source="m3_voice",
        )

        # Build advisor email only if pulse is available
        pulse = self.session.get("weekly_pulse", "")
        fee_bullets = self.session.get("fee_bullets", [])
        fee_sources = self.session.get("fee_sources", [])

        market_ctx = " ".join(pulse.split()[:100]) if pulse else "No pulse generated yet."
        fee_section = "\n".join(f"• {b}" for b in fee_bullets) if fee_bullets else "N/A"
        sources_section = "\n".join(fee_sources) if fee_sources else ""

        email_body = (
            f"Hi [Advisor Name],\n\n"
            f"Booking Summary:\n"
            f"  Code:  {code}\n"
            f"  Topic: {self._topic}\n"
            f"  Slot:  {detail['slot']}\n\n"
            f"Market Context (this week's top customer theme):\n"
            f"{market_ctx}\n\n"
            f"Fee Context:\n{fee_section}\n"
            f"{sources_section}\n\n"
            f"⚠ No investment advice implied.\n"
            f"Complete booking: {SECURE_BASE_URL}/complete/{code}"
        )

        enqueue_action(
            self.session,
            type="email_draft",
            payload={
                "subject": f"Advisor Pre-Booking: {self._topic} — {detail['date']}",
                "body":    email_body,
            },
            source="m3_voice",
        )

        return (
            f"Perfect! Your appointment is booked. "
            f"Booking code: {code}. "
            f"Date/Time: {detail['slot']} (IST). "
            f"Please complete your details at {SECURE_BASE_URL}/complete/{code} — "
            "no personal information is shared on this call. "
            "Check the Approval Center tab to review the calendar hold and advisor email."
        )
