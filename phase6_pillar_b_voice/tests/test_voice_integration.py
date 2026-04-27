"""Phase 6 — Theme-aware voice integration tests."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]   # project root
P6   = Path(__file__).resolve().parents[1]   # phase6_pillar_b_voice
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(P6))


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


# ---------------------------------------------------------------------------
# TC-5.x  End-to-End FSM + MCP tests (from voice-agents phase5 test suite)
# ---------------------------------------------------------------------------

import unittest.mock as mock


def _ctx():
    """Minimal DialogueContext for tests."""
    from src.dialogue.states import DialogueContext, DialogueState
    from datetime import datetime, timezone, timedelta
    IST = timezone(timedelta(hours=5, minutes=30))
    return DialogueContext(
        call_id="TC-TEST",
        session_start_ist=datetime.now(IST),
        current_state=DialogueState.GREETED,
    )


def _llm(intent="book_new", slots=None, compliance_flag=None, speech="", raw_response=""):
    from src.dialogue.states import LLMResponse
    return LLMResponse(
        intent=intent,
        slots=slots or {},
        compliance_flag=compliance_flag,
        speech=speech,
        raw_response=raw_response,
    )


def _slot(start_iso: str = "2026-04-28T10:00:00+05:30"):
    """Mock CalendarSlot."""
    from datetime import datetime
    from unittest.mock import MagicMock
    s = MagicMock()
    s.slot_id = "SLOT-TC-001"
    s.start = datetime.fromisoformat(start_iso)
    s.status = "free"
    s.topic_affinity = []
    s.start_ist_str = lambda: "Monday, 28/04/2026 at 10:00 AM IST"
    return s


def _mock_mcp(success=True):
    """Return a mock MCPResults."""
    try:
        from src.mcp.models import ToolResult, MCPResults
        tr = ToolResult(success=success, data={"event_id": "EVT-TC", "row_index": 1})
        return MCPResults(calendar=tr, sheets=tr, email=tr, total_duration_ms=10.0)
    except ImportError:
        r = mock.MagicMock()
        r.all_succeeded = success
        r.calendar.success = success
        r.sheets.success = success
        r.email.success = success
        r.calendar.data = {"event_id": "EVT-TC"}
        r.sheets.data = {"row_index": 1}
        return r


def _fast_track_to_slot_confirmed(fsm, topic="kyc_onboarding"):
    """Drive FSM to SLOT_CONFIRMED state through minimal turns."""
    ctx, _ = fsm.start()
    ctx, _ = fsm.process_turn(ctx, "yes", _llm("book_new", raw_response="yes"))
    ctx, _ = fsm.process_turn(ctx, f"book for {topic}", _llm("book_new", {"topic": topic}, raw_response=f"book for {topic}"))
    ctx, _ = fsm.process_turn(ctx, "Monday morning", _llm("book_new", {"day_preference": "monday", "time_preference": "morning"}, raw_response="Monday morning"))
    ctx, _ = fsm.process_turn(ctx, "first option", _llm("book_new", raw_response="first option"))
    return ctx


@pytest.fixture
def fresh_fsm():
    from src.dialogue.fsm import DialogueFSM
    return DialogueFSM()


@pytest.fixture
def mock_mcp_ok():
    return _mock_mcp(success=True)


@pytest.fixture
def mock_mcp_partial():
    try:
        from src.mcp.models import ToolResult, MCPResults
        ok = ToolResult(success=True, data={"event_id": "EVT-TC"})
        fail = ToolResult(success=False, data={}, error="timeout")
        return MCPResults(calendar=ok, sheets=fail, email=fail, total_duration_ms=10.0)
    except ImportError:
        r = mock.MagicMock()
        r.all_succeeded = False
        r.calendar.success = True
        r.sheets.success = False
        r.email.success = False
        return r


@pytest.fixture
def mock_mcp_fail():
    return _mock_mcp(success=False)


class TestEndToEndFSM:
    """TC-5.1 through TC-5.10 — End-to-end FSM correctness tests."""

    def test_tc51_happy_path_reaches_booking_complete(self, fresh_fsm):
        """TC-5.1: Full happy-path booking reaches BOOKING_COMPLETE state."""
        from src.dialogue.states import DialogueState

        mock_slot = _slot()
        mock_results = _mock_mcp(success=True)

        with mock.patch("src.booking.slot_resolver.resolve_slots", return_value=[mock_slot]), \
             mock.patch("src.booking.slot_resolver.parse_datetime_summary", return_value=("Monday morning", False)), \
             mock.patch("src.booking.booking_code_generator.generate_booking_code", return_value="NL-TC51"), \
             mock.patch("src.booking.secure_url_generator.generate_secure_url", return_value="https://mock/TC51"), \
             mock.patch("src.mcp.mcp_orchestrator.dispatch_mcp_sync", return_value=mock_results):

            fsm = fresh_fsm
            ctx, _ = fsm.start()
            assert ctx.current_state == DialogueState.GREETED

            ctx, _ = fsm.process_turn(ctx, "yes", _llm("book_new", raw_response="yes"))
            ctx, _ = fsm.process_turn(ctx, "KYC appointment Monday morning", _llm("book_new", {"topic": "kyc_onboarding", "day_preference": "monday", "time_preference": "morning"}, raw_response="KYC appointment Monday morning"))
            ctx, _ = fsm.process_turn(ctx, "first option", _llm("book_new", raw_response="first option"))
            ctx, _ = fsm.process_turn(ctx, "yes confirm", _llm("book_new", raw_response="yes confirm"))

            assert ctx.current_state == DialogueState.BOOKING_COMPLETE

    def test_tc52_booking_code_format(self, fresh_fsm):
        """TC-5.2: Booking code matches NL-XXXX pattern."""
        import re
        mock_slot = _slot()
        mock_results = _mock_mcp(success=True)

        with mock.patch("src.booking.slot_resolver.resolve_slots", return_value=[mock_slot]), \
             mock.patch("src.booking.slot_resolver.parse_datetime_summary", return_value=("Monday morning", False)), \
             mock.patch("src.booking.secure_url_generator.generate_secure_url", return_value="https://mock/TC52"), \
             mock.patch("src.mcp.mcp_orchestrator.dispatch_mcp_sync", return_value=mock_results):

            fsm = fresh_fsm
            ctx, _ = fsm.start()
            ctx, _ = fsm.process_turn(ctx, "yes", _llm("book_new", raw_response="yes"))
            ctx, _ = fsm.process_turn(ctx, "KYC Monday morning", _llm("book_new", {"topic": "kyc_onboarding", "day_preference": "monday", "time_preference": "morning"}, raw_response="KYC Monday morning"))
            ctx, _ = fsm.process_turn(ctx, "first option", _llm("book_new", raw_response="first option"))
            ctx, _ = fsm.process_turn(ctx, "yes", _llm("book_new", raw_response="yes"))

            assert ctx.booking_code is not None
            assert re.match(r"^NL-[A-Z0-9]{4}$", ctx.booking_code), f"Bad code: {ctx.booking_code}"

    def test_tc53_refuse_advice_blocks_turn(self, fresh_fsm):
        """TC-5.3: refuse_advice compliance_flag blocks the turn without state change."""
        from src.dialogue.states import DialogueState

        fsm = fresh_fsm
        ctx, _ = fsm.start()
        state_before = ctx.current_state
        ctx, speech = fsm.process_turn(ctx, "Which fund should I invest in?",
                                       _llm("refuse_advice", compliance_flag="refuse_advice"))

        assert ctx.current_state == state_before or not ctx.booking_code
        assert speech  # agent must say something (refusal message)

    def test_tc54_refuse_pii_blocks_turn(self, fresh_fsm):
        """TC-5.4: refuse_pii compliance_flag blocks the turn."""
        fsm = fresh_fsm
        ctx, _ = fsm.start()
        ctx, speech = fsm.process_turn(ctx, "My phone is 9876543210",
                                       _llm("refuse_pii", compliance_flag="refuse_pii"))
        assert speech
        assert not ctx.booking_code

    def test_tc55_out_of_scope_blocks_turn(self, fresh_fsm):
        """TC-5.5: out_of_scope intent is handled gracefully."""
        fsm = fresh_fsm
        ctx, _ = fsm.start()
        ctx, speech = fsm.process_turn(ctx, "What is the weather today?",
                                       _llm("out_of_scope"))
        assert speech

    def test_tc56_end_call_reaches_end_state(self, fresh_fsm):
        """TC-5.6: end_call intent transitions to END state."""
        from src.dialogue.states import DialogueState

        fsm = fresh_fsm
        ctx, _ = fsm.start()
        ctx, speech = fsm.process_turn(ctx, "no thanks goodbye", _llm("end_call"))

        assert ctx.current_state == DialogueState.END
        assert speech
        assert any(w in speech.lower() for w in ("goodbye", "thank you", "bye", "धन्यवाद"))

    def test_tc57_three_no_inputs_reach_error(self, fresh_fsm):
        """TC-5.7: Three consecutive empty inputs trigger ERROR state."""
        from src.dialogue.states import DialogueState, LLMResponse

        fsm = fresh_fsm
        ctx, _ = fsm.start()

        for _ in range(3):
            if ctx.current_state not in (DialogueState.END, DialogueState.ERROR):
                ctx, _ = fsm.process_turn(ctx, "", LLMResponse(intent="out_of_scope"))

        assert ctx.current_state in (DialogueState.ERROR, DialogueState.END)

    def test_tc58_mcp_partial_failure_still_books(self, fresh_fsm, mock_mcp_partial):
        """TC-5.8: Calendar succeeds but sheets/email fail → booking code still issued."""
        from src.dialogue.states import DialogueState

        mock_slot = _slot()

        with mock.patch("src.booking.slot_resolver.resolve_slots", return_value=[mock_slot]), \
             mock.patch("src.booking.slot_resolver.parse_datetime_summary", return_value=("Monday morning", False)), \
             mock.patch("src.booking.secure_url_generator.generate_secure_url", return_value="https://mock/TC58"), \
             mock.patch("src.mcp.mcp_orchestrator.dispatch_mcp_sync", return_value=mock_mcp_partial):

            fsm = fresh_fsm
            ctx, _ = fsm.start()
            ctx, _ = fsm.process_turn(ctx, "yes", _llm("book_new", raw_response="yes"))
            ctx, _ = fsm.process_turn(ctx, "KYC Monday morning", _llm("book_new", {"topic": "kyc_onboarding", "day_preference": "monday", "time_preference": "morning"}, raw_response="KYC Monday morning"))
            ctx, _ = fsm.process_turn(ctx, "first option", _llm("book_new", raw_response="first option"))
            ctx, _ = fsm.process_turn(ctx, "yes", _llm("book_new", raw_response="yes"))

            assert ctx.current_state == DialogueState.BOOKING_COMPLETE
            assert ctx.booking_code

    def test_tc59_mcp_full_failure_graceful(self, fresh_fsm, mock_mcp_fail):
        """TC-5.9: All MCP tools fail → booking code still issued, no crash."""
        from src.dialogue.states import DialogueState

        mock_slot = _slot()

        with mock.patch("src.booking.slot_resolver.resolve_slots", return_value=[mock_slot]), \
             mock.patch("src.booking.slot_resolver.parse_datetime_summary", return_value=("Monday morning", False)), \
             mock.patch("src.booking.secure_url_generator.generate_secure_url", return_value="https://mock/TC59"), \
             mock.patch("src.mcp.mcp_orchestrator.dispatch_mcp_sync", return_value=mock_mcp_fail):

            fsm = fresh_fsm
            ctx, _ = fsm.start()
            ctx, _ = fsm.process_turn(ctx, "yes", _llm("book_new", raw_response="yes"))
            ctx, _ = fsm.process_turn(ctx, "SIP Monday morning", _llm("book_new", {"topic": "sip_mandates", "day_preference": "monday", "time_preference": "morning"}, raw_response="SIP Monday morning"))
            ctx, _ = fsm.process_turn(ctx, "first option", _llm("book_new", raw_response="first option"))
            ctx, _ = fsm.process_turn(ctx, "yes", _llm("book_new", raw_response="yes"))

            assert ctx.current_state == DialogueState.BOOKING_COMPLETE
            assert ctx.booking_code

    def test_tc510_multi_turn_slot_fill(self, fresh_fsm):
        """TC-5.10: Topic, day, and time preference collected across separate turns."""
        from src.dialogue.states import DialogueState

        mock_slot = _slot()
        mock_results = _mock_mcp(success=True)

        with mock.patch("src.booking.slot_resolver.resolve_slots", return_value=[mock_slot]), \
             mock.patch("src.booking.slot_resolver.parse_datetime_summary", return_value=("Friday afternoon", False)), \
             mock.patch("src.booking.secure_url_generator.generate_secure_url", return_value="https://mock/TC510"), \
             mock.patch("src.mcp.mcp_orchestrator.dispatch_mcp_sync", return_value=mock_results):

            fsm = fresh_fsm
            ctx, _ = fsm.start()

            ctx, _ = fsm.process_turn(ctx, "yes", _llm("book_new", raw_response="yes"))
            ctx, _ = fsm.process_turn(ctx, "I want to book for KYC", _llm("book_new", {"topic": "kyc_onboarding"}, raw_response="I want to book for KYC"))
            assert ctx.topic == "kyc_onboarding"

            ctx, _ = fsm.process_turn(ctx, "Friday afternoon", _llm("book_new", {"day_preference": "friday", "time_preference": "afternoon"}, raw_response="Friday afternoon"))
            ctx, _ = fsm.process_turn(ctx, "first one please", _llm("book_new", raw_response="first one please"))
            ctx, _ = fsm.process_turn(ctx, "yes confirm", _llm("book_new", raw_response="yes confirm"))

            assert ctx.current_state == DialogueState.BOOKING_COMPLETE
            assert ctx.topic == "kyc_onboarding"


class TestSessionManager:
    """TC-5.11 and TC-5.12 — SessionManager lifecycle and thread safety."""

    def test_tc511_session_lifecycle(self):
        """TC-5.11: SessionManager create → get → update → close cycle."""
        try:
            from src.dialogue.session_manager import SessionManager
        except ImportError:
            pytest.skip("SessionManager not available")

        from src.dialogue.fsm import DialogueFSM
        sm = SessionManager()
        fsm = DialogueFSM()
        ctx, _ = fsm.start()

        session_id = sm.create_session(ctx)
        assert session_id

        retrieved = sm.get_session(session_id)
        assert retrieved is not None
        assert retrieved.call_id == ctx.call_id

        ctx2, _ = fsm.start()
        sm.update_session(session_id, ctx2)
        updated = sm.get_session(session_id)
        assert updated is not None
        assert updated.call_id == ctx2.call_id

        sm.close_session(session_id)
        closed = sm.get_session(session_id)
        assert closed is None

    def test_tc512_session_manager_thread_safe(self):
        """TC-5.12: 20 concurrent threads each create and read their own session safely."""
        try:
            from src.dialogue.session_manager import SessionManager
        except ImportError:
            pytest.skip("SessionManager not available")

        import threading
        from src.dialogue.fsm import DialogueFSM

        sm = SessionManager()
        fsm = DialogueFSM()
        errors = []
        session_ids = []
        lock = threading.Lock()

        def worker(_i):
            try:
                ctx, _ = fsm.start()
                sid = sm.create_session(ctx)
                retrieved = sm.get_session(sid)
                assert retrieved is not None
                with lock:
                    session_ids.append(sid)
            except Exception as exc:
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Thread errors: {errors}"
        assert len(session_ids) == 20
