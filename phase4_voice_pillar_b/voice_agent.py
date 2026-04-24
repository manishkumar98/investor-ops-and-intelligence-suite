"""Voice Agent FSM — M3-integrated version.

Integrates:
- PII scrubber (input guard, M3 phase1)
- Compliance guard (output guard, M3 phase2)
- DialogueContext (M3 phase2 state tracker)
- RAG injector for what_to_prepare (M3 phase0)
- Intent classifier with Groq→Anthropic→rule-based chain (M3 phase2)
- 8-state FSM compatible with app.py interface
"""
import os
import uuid
from datetime import datetime

from config import SECURE_BASE_URL
from .intent_classifier import classify
from .slot_filler import extract_topic, extract_time_pref
from .booking_engine import load_calendar, match_slots, book
from .pii_scrubber import scrub_pii
from .compliance_guard import ComplianceGuard
from .dialogue_states import DialogueContext, DialogueState, TOPIC_LABELS, IST  # IST used in __init__
from .rag_injector import get_rag_context

_guard = ComplianceGuard()

DISCLAIMER = (
    "This is an informational service only — not investment advice. "
    "I'll help you book a tentative call with a human advisor."
)


def _tts(text: str) -> bytes | None:
    """TTS: OpenAI tts-1 → silent fallback."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        resp = client.audio.speech.create(
            model="tts-1", voice="alloy", input=text, response_format="mp3",
        )
        return resp.content
    except Exception as exc:
        print(f"[voice_agent] TTS failed: {exc}")
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

        # M3 DialogueContext for rich slot tracking
        call_id = str(uuid.uuid4())[:8].upper()
        self._ctx = DialogueContext(
            call_id=call_id,
            session_start_ist=datetime.now(IST),
            current_state=DialogueState.IDLE,
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
            # Still process the cleaned input through the FSM
            response_text = pii_warning + self._dispatch(clean_input)
        else:
            response_text = self._dispatch(clean_input)

        # ── M3 Layer 3: Compliance guard output ───────────────────────────
        response_text = _guard.check_and_gate(response_text)

        return response_text, _tts(response_text)

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
                self.state = "TIMEPREF"
                self._ctx.current_state = DialogueState.TOPIC_COLLECTED
                label = TOPIC_LABELS.get(self._topic, self._topic)
                return (
                    f"Great! I'll help you book a call about {label}. "
                    "What day and time works best? (e.g., 'Monday morning', 'Friday afternoon')"
                )
            self.state = "TOPIC"
            return (
                "Great! What would you like to discuss with the advisor? "
                "Options: KYC / Onboarding, SIP / Mandates, Statements / Tax, "
                "Withdrawals & Timelines, or Account Changes / Nominee."
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

    def _handle_topic(self, utterance: str) -> str:
        topic = extract_topic(utterance)
        if not topic:
            self._ctx.topic_retry_count += 1
            return (
                "I didn't catch the topic. Please choose one: "
                "KYC / Onboarding, SIP / Mandates, Statements / Tax, "
                "Withdrawals, or Account Changes."
            )
        self._topic = topic
        self._ctx.topic = topic
        self._ctx.current_state = DialogueState.TOPIC_COLLECTED
        self.state = "TIMEPREF"
        label = TOPIC_LABELS.get(topic, topic)
        return (
            f"Got it — {label}. "
            "What day and time works best? (e.g., 'Monday morning', 'Wednesday afternoon')"
        )

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
            f"Option {i}: {s.get('day', '').title()} at {s.get('time', '')} IST"
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
        idx = 0
        if "2" in lower or "second" in lower or "two" in lower:
            idx = 1

        if idx >= len(self._offered_slots):
            idx = 0

        self._chosen_slot = self._offered_slots[idx]
        self._ctx.resolved_slot = self._chosen_slot
        self._ctx.current_state = DialogueState.SLOT_CONFIRMED
        self.state = "CONFIRM"

        topic_label = TOPIC_LABELS.get(self._topic or "", self._topic or "General Query")
        slot_str = f"{self._chosen_slot.get('day', '').title()} at {self._chosen_slot.get('time', '')} IST"
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

    def _handle_booked(self, _: str) -> str:
        code = self.session.get("booking_code", "N/A")
        return (
            f"Your appointment is confirmed! Booking code: {code}. "
            f"Please complete your details at {SECURE_BASE_URL}/complete/{code} — "
            "no personal information is collected on this call. "
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
        self._ctx.current_state = DialogueState.BOOKING_COMPLETE
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
                    "status":       "CONFIRMED",
                },
            },
            source="m3_voice",
        )

        pulse       = self.session.get("weekly_pulse", "")
        fee_bullets = self.session.get("fee_bullets", [])
        fee_sources = self.session.get("fee_sources", [])
        market_ctx  = " ".join(pulse.split()[:100]) if pulse else "No pulse generated yet."
        fee_section = "\n".join(f"• {b}" for b in fee_bullets) if fee_bullets else "N/A"
        topic_label = TOPIC_LABELS.get(self._topic, self._topic)

        enqueue_action(
            self.session,
            type="email_draft",
            payload={
                "subject": f"Advisor Pre-Booking: {topic_label} — {detail['date']}",
                "body": (
                    f"Hi [Advisor Name],\n\n"
                    f"Booking Summary:\n"
                    f"  Code:  {code}\n"
                    f"  Topic: {topic_label}\n"
                    f"  Slot:  {detail['slot']}\n\n"
                    f"Market Context (this week's top customer theme):\n"
                    f"{market_ctx}\n\n"
                    f"Fee Context:\n{fee_section}\n"
                    + ("\n".join(fee_sources) + "\n" if fee_sources else "")
                    + f"\n⚠ No investment advice implied.\n"
                    f"Complete booking: {SECURE_BASE_URL}/complete/{code}"
                ),
            },
            source="m3_voice",
        )

        self._ctx.calendar_hold_created = True
        self._ctx.notes_appended = True
        self._ctx.email_drafted = True

        return (
            f"Perfect! Your appointment is booked. "
            f"Booking code: {code}. "
            f"Date/Time: {detail['slot']} (IST). "
            f"Please complete your details at {SECURE_BASE_URL}/complete/{code} — "
            "no personal information is shared on this call. "
            "Check the Approval Center tab to review the calendar hold and advisor email."
        )
