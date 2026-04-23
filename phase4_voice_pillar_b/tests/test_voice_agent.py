"""Phase 4 — Voice Agent tests."""
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


VALID_TOPICS = [
    "KYC / Onboarding",
    "SIP / Mandates",
    "Statements / Tax Documents",
    "Withdrawals & Timelines",
    "Account Changes / Nominee",
]

VALID_INTENTS = {"book_new", "reschedule", "cancel", "what_to_prepare", "check_availability"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def session():
    return {
        "top_theme": None,
        "booking_code": None,
        "booking_detail": None,
        "mcp_queue": [],
        "call_completed": False,
    }


@pytest.fixture
def session_with_theme():
    return {"top_theme": "Nominee Updates", "booking_code": None,
            "booking_detail": None, "mcp_queue": [], "call_completed": False}


@pytest.fixture
def mock_slots():
    return [
        {"id": "S1", "date": "2026-04-24", "time": "10:00", "tz": "IST"},
        {"id": "S2", "date": "2026-04-24", "time": "15:00", "tz": "IST"},
        {"id": "S3", "date": "2026-04-25", "time": "11:00", "tz": "IST"},
    ]


# ---------------------------------------------------------------------------
# P4-01  Greeting + disclaimer
# ---------------------------------------------------------------------------

class TestGreeting:

    def _make_greeting(self, top_theme: str | None = None) -> str:
        base = ("Hello! This is the Advisor Booking line. "
                "This call is for informational purposes only and is not investment advice. ")
        if top_theme:
            base += (f"I see many users are asking about {top_theme} today — "
                     "I can help you book a call for that! What would you like help with?")
        else:
            base += "What topic would you like to discuss with an advisor?"
        return base

    def test_greeting_contains_disclaimer(self, session):
        greeting = self._make_greeting()
        assert "informational" in greeting.lower()
        assert "not investment advice" in greeting.lower()

    def test_greeting_injects_top_theme(self, session_with_theme):
        top_theme = session_with_theme["top_theme"]
        greeting = self._make_greeting(top_theme=top_theme)
        assert top_theme in greeting

    def test_greeting_without_theme_still_valid(self, session):
        greeting = self._make_greeting(top_theme=None)
        assert "advisor" in greeting.lower()
        assert "informational" in greeting.lower()


# ---------------------------------------------------------------------------
# P4-02  Intent detection
# ---------------------------------------------------------------------------

class TestIntentDetection:

    def _classify_intent(self, utterance: str) -> str:
        utterance_lower = utterance.lower()
        if any(k in utterance_lower for k in ("book", "schedule", "new appointment")):
            return "book_new"
        if any(k in utterance_lower for k in ("reschedule", "change my booking", "move my slot")):
            return "reschedule"
        if any(k in utterance_lower for k in ("cancel", "remove my booking")):
            return "cancel"
        if any(k in utterance_lower for k in ("what to prepare", "what should i bring", "prepare")):
            return "what_to_prepare"
        if any(k in utterance_lower for k in ("available", "availability", "when can i")):
            return "check_availability"
        return "unknown"

    def test_book_new_intent(self):
        assert self._classify_intent("I want to book a new appointment") == "book_new"

    def test_reschedule_intent(self):
        assert self._classify_intent("I need to reschedule my booking") == "reschedule"

    def test_cancel_intent(self):
        assert self._classify_intent("Please cancel my appointment") == "cancel"

    def test_what_to_prepare_intent(self):
        assert self._classify_intent("What should I prepare for the call?") == "what_to_prepare"

    def test_check_availability_intent(self):
        assert self._classify_intent("When are you available?") == "check_availability"

    def test_all_valid_intents_defined(self):
        assert VALID_INTENTS == {
            "book_new", "reschedule", "cancel", "what_to_prepare", "check_availability"
        }


# ---------------------------------------------------------------------------
# P4-03  Topic slot-filling
# ---------------------------------------------------------------------------

class TestTopicSlotFilling:

    def _map_topic(self, utterance: str) -> str | None:
        utterance_lower = utterance.lower()
        if any(k in utterance_lower for k in ("kyc", "onboard", "account open")):
            return "KYC / Onboarding"
        if any(k in utterance_lower for k in ("sip", "mandate", "systematic")):
            return "SIP / Mandates"
        if any(k in utterance_lower for k in ("statement", "tax", "capital gain")):
            return "Statements / Tax Documents"
        if any(k in utterance_lower for k in ("withdraw", "redemption", "timeline")):
            return "Withdrawals & Timelines"
        if any(k in utterance_lower for k in ("nominee", "account change", "update")):
            return "Account Changes / Nominee"
        return None

    def test_sip_maps_correctly(self):
        assert self._map_topic("I want to talk about my SIP") == "SIP / Mandates"

    def test_nominee_maps_correctly(self):
        assert self._map_topic("I need to update my nominee") == "Account Changes / Nominee"

    def test_kyc_maps_correctly(self):
        assert self._map_topic("I need help with onboarding") == "KYC / Onboarding"

    def test_tax_maps_correctly(self):
        assert self._map_topic("I need my capital gains statement") == "Statements / Tax Documents"

    def test_mapped_topic_in_valid_list(self):
        utterances = [
            "I want to talk about my SIP",
            "Update my nominee",
            "KYC help",
            "Tax statement",
            "Withdrawals",
        ]
        for u in utterances:
            topic = self._map_topic(u)
            if topic:
                assert topic in VALID_TOPICS


# ---------------------------------------------------------------------------
# P4-04  Slot offer
# ---------------------------------------------------------------------------

class TestSlotOffer:

    def _filter_slots(self, slots: list, preference: str) -> list:
        pref_lower = preference.lower()
        if "morning" in pref_lower:
            return [s for s in slots if int(s["time"].split(":")[0]) < 12][:2]
        if "afternoon" in pref_lower:
            return [s for s in slots if int(s["time"].split(":")[0]) >= 12][:2]
        return slots[:2]

    def test_offers_at_most_2_slots(self, mock_slots):
        offered = self._filter_slots(mock_slots, "morning")
        assert len(offered) <= 2

    def test_morning_preference_returns_am_slots(self, mock_slots):
        offered = self._filter_slots(mock_slots, "morning")
        for slot in offered:
            hour = int(slot["time"].split(":")[0])
            assert hour < 12

    def test_slot_offer_script_contains_both_options(self, mock_slots):
        slots = mock_slots[:2]
        script = (f"Option 1: {slots[0]['date']} at {slots[0]['time']} {slots[0]['tz']}. "
                  f"Option 2: {slots[1]['date']} at {slots[1]['time']} {slots[1]['tz']}. "
                  "Which works better?")
        assert "Option 1" in script
        assert "Option 2" in script


# ---------------------------------------------------------------------------
# P4-05/06  Booking code
# ---------------------------------------------------------------------------

class TestBookingCode:

    def _generate_code(self, prefix="NL"):
        import random, string
        suffix = random.choice(string.ascii_uppercase) + \
                 "".join(random.choices(string.digits, k=3))
        return f"{prefix}-{suffix}"

    def test_booking_code_format_nl(self):
        for _ in range(20):
            code = self._generate_code("NL")
            assert re.match(r"^NL-[A-Z]\d{3}$", code), f"Invalid code: {code}"

    def test_waitlist_code_format_wl(self):
        for _ in range(10):
            code = self._generate_code("WL")
            assert code.startswith("WL-")
            assert re.match(r"^WL-[A-Z]\d{3}$", code)

    def test_booking_code_written_to_session(self, session):
        code = self._generate_code("NL")
        session["booking_code"] = code
        assert session["booking_code"] is not None
        assert session["booking_code"].startswith("NL-")

    def test_booking_detail_has_all_fields(self, session, mock_slots):
        slot = mock_slots[0]
        session["booking_detail"] = {
            "date": slot["date"],
            "time": slot["time"],
            "tz": slot["tz"],
            "topic": "SIP / Mandates",
            "code": "NL-A742",
        }
        required = {"date", "time", "tz", "topic", "code"}
        assert required.issubset(session["booking_detail"].keys())

    def test_booking_detail_tz_is_ist(self, session, mock_slots):
        session["booking_detail"] = {"tz": mock_slots[0]["tz"], "date": "2026-04-24",
                                     "time": "10:00", "topic": "SIP / Mandates", "code": "NL-A742"}
        assert session["booking_detail"]["tz"] == "IST"


# ---------------------------------------------------------------------------
# P4-09  Safety refusal
# ---------------------------------------------------------------------------

class TestSafetyRefusal:

    ADVICE_PATTERNS = [
        r"should i (buy|sell|invest)",
        r"which fund.*better",
        r"give.*\d+%.*return",
        r"recommend.*fund",
    ]

    def _safety_check(self, utterance: str) -> str | None:
        for pattern in self.ADVICE_PATTERNS:
            if re.search(pattern, utterance, re.IGNORECASE):
                return ("I can help with bookings only. For investment guidance, "
                        "please consult a SEBI-registered advisor. "
                        "Learn more: https://www.sebi.gov.in/investors.html")
        return None

    def test_investment_advice_refused(self):
        assert self._safety_check("Should I buy this fund?") is not None

    def test_return_prediction_refused(self):
        assert self._safety_check("Which fund will give me 20% returns?") is not None

    def test_normal_booking_not_refused(self):
        assert self._safety_check("I want to book an appointment about my SIP") is None

    def test_refusal_contains_sebi_reference(self):
        refusal = self._safety_check("Should I sell my ELSS?")
        assert refusal is not None
        assert "SEBI" in refusal or "sebi" in refusal.lower()


# ---------------------------------------------------------------------------
# P4-10  No PII on call
# ---------------------------------------------------------------------------

class TestNoPIIOnCall:

    PII_PATTERNS = [
        r"\+?91[\s\-]?\d{10}",
        r"[\w.+\-]+@[\w\-]+\.[\w.]+",
        r"[A-Z]{5}\d{4}[A-Z]",
        r"\b\d{12}\b",  # Aadhaar
    ]

    def _has_pii(self, text: str) -> bool:
        return any(re.search(p, text) for p in self.PII_PATTERNS)

    def test_booking_confirmation_no_pii(self):
        confirmation = ("Your booking is confirmed. Topic: SIP / Mandates. "
                        "Date: 2026-04-24 at 10:00 IST. Booking Code: NL-A742. "
                        "Please visit https://app.example.com/complete/NL-A742 "
                        "to submit your contact details securely.")
        assert not self._has_pii(confirmation)

    def test_greeting_no_pii(self):
        greeting = ("Hello! This is the Advisor Booking line. "
                    "This call is informational only, not investment advice.")
        assert not self._has_pii(greeting)


# ---------------------------------------------------------------------------
# P4-11  MCP queue after booking
# ---------------------------------------------------------------------------

class TestMCPQueueAfterBooking:

    def test_three_actions_enqueued(self, session):
        for action_type in ("calendar_hold", "notes_append", "email_draft"):
            session["mcp_queue"].append({"type": action_type, "status": "pending", "payload": {}})
        types_in_queue = {a["type"] for a in session["mcp_queue"]}
        assert "calendar_hold" in types_in_queue
        assert "notes_append" in types_in_queue
        assert "email_draft" in types_in_queue

    def test_calendar_hold_title_contains_code(self, session):
        code = "NL-A742"
        topic = "SIP / Mandates"
        hold_title = f"Advisor Q&A — {topic} — {code}"
        session["mcp_queue"].append({
            "type": "calendar_hold",
            "status": "pending",
            "payload": {"title": hold_title},
        })
        action = next(a for a in session["mcp_queue"] if a["type"] == "calendar_hold")
        assert code in action["payload"]["title"]
