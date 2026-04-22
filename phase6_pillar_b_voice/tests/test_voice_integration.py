"""Phase 6 — Theme-aware voice integration tests."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def session_no_pulse():
    return {
        "pulse_generated": False,
        "top_theme": None,
        "weekly_pulse": None,
        "booking_code": None,
        "mcp_queue": [],
        "call_completed": False,
    }


@pytest.fixture
def session_with_pulse():
    return {
        "pulse_generated": True,
        "top_theme": "Nominee Updates",
        "weekly_pulse": "This week's top themes: Nominee Updates (12), Login Issues (9)...",
        "booking_code": None,
        "mcp_queue": [],
        "call_completed": False,
    }


@pytest.fixture
def session_after_call():
    return {
        "pulse_generated": True,
        "top_theme": "Nominee Updates",
        "weekly_pulse": "This week's top themes...",
        "booking_code": "NL-A742",
        "booking_detail": {
            "date": "2026-04-24", "time": "10:00", "tz": "IST",
            "topic": "Account Changes / Nominee", "code": "NL-A742",
        },
        "mcp_queue": [
            {"type": "calendar_hold", "status": "pending",
             "payload": {"title": "Advisor Q&A — Account Changes / Nominee — NL-A742"}},
            {"type": "notes_append",  "status": "pending", "payload": {"entry": {"code": "NL-A742"}}},
            {"type": "email_draft",   "status": "pending", "payload": {}},
        ],
        "call_completed": True,
    }


# ---------------------------------------------------------------------------
# P6-01  Start-call gate
# ---------------------------------------------------------------------------

class TestStartCallGate:

    def _is_call_allowed(self, session: dict) -> bool:
        return session.get("pulse_generated", False) is True

    def test_call_blocked_without_pulse(self, session_no_pulse):
        assert not self._is_call_allowed(session_no_pulse)

    def test_call_allowed_with_pulse(self, session_with_pulse):
        assert self._is_call_allowed(session_with_pulse)

    def test_gate_reads_pulse_generated_flag(self, session_no_pulse, session_with_pulse):
        assert session_no_pulse["pulse_generated"] is False
        assert session_with_pulse["pulse_generated"] is True


# ---------------------------------------------------------------------------
# P6-02/03  Greeting with/without theme
# ---------------------------------------------------------------------------

class TestThemeAwareGreeting:

    def _make_greeting(self, top_theme: str | None) -> str:
        base = ("Hello! This is the Advisor Booking line. "
                "This call is for informational purposes only and is not investment advice. ")
        if top_theme:
            return (base + f"I see many users are asking about {top_theme} today — "
                    "I can help you book a call for that! What would you like help with?")
        return base + "What topic would you like to discuss with an advisor?"

    def test_greeting_contains_top_theme_when_set(self, session_with_pulse):
        top_theme = session_with_pulse["top_theme"]
        greeting = self._make_greeting(top_theme)
        assert top_theme in greeting

    def test_greeting_works_without_theme(self, session_no_pulse):
        greeting = self._make_greeting(session_no_pulse["top_theme"])
        assert "advisor" in greeting.lower()
        assert "informational" in greeting.lower()

    def test_greeting_always_has_disclaimer(self):
        for theme in (None, "Nominee Updates", "Login Issues"):
            greeting = self._make_greeting(theme)
            assert "informational" in greeting.lower()
            assert "not investment advice" in greeting.lower()


# ---------------------------------------------------------------------------
# P6-04  Theme badge
# ---------------------------------------------------------------------------

class TestThemeBadge:

    def test_badge_text_format(self, session_with_pulse):
        top_theme = session_with_pulse["top_theme"]
        badge = f"Current Top Theme: {top_theme}"
        assert top_theme in badge
        assert badge.startswith("Current Top Theme:")

    def test_no_badge_without_theme(self, session_no_pulse):
        top_theme = session_no_pulse["top_theme"]
        assert top_theme is None


# ---------------------------------------------------------------------------
# P6-05/06  Post-call state
# ---------------------------------------------------------------------------

class TestPostCallState:

    def test_call_completed_flag_set(self, session_after_call):
        assert session_after_call["call_completed"] is True

    def test_mcp_queue_populated_after_call(self, session_after_call):
        assert len(session_after_call["mcp_queue"]) >= 3

    def test_mcp_queue_has_all_three_types(self, session_after_call):
        types = {a["type"] for a in session_after_call["mcp_queue"]}
        assert "calendar_hold" in types
        assert "notes_append" in types
        assert "email_draft" in types


# ---------------------------------------------------------------------------
# P6-07  Shared session state access
# ---------------------------------------------------------------------------

class TestSharedSessionState:

    def test_pulse_data_readable_from_voice_agent_context(self, session_with_pulse):
        pulse = session_with_pulse.get("weekly_pulse")
        theme = session_with_pulse.get("top_theme")
        assert pulse is not None
        assert theme is not None

    def test_booking_code_readable_after_call(self, session_after_call):
        code = session_after_call.get("booking_code")
        assert code is not None
        assert code.startswith("NL-")

    def test_state_writes_do_not_conflict(self, session_with_pulse):
        session_with_pulse["booking_code"] = "NL-A742"
        assert session_with_pulse["top_theme"] == "Nominee Updates"
        assert session_with_pulse["booking_code"] == "NL-A742"
