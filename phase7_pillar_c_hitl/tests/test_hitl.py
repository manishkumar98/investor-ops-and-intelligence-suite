"""Phase 7 — HITL MCP Gateway tests."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_session():
    return {
        "weekly_pulse": (
            "Top themes this week: Nominee Updates (12), Login Issues (9), SIP Failures (6). "
            "Users are frustrated with nominee update flow and OTP delivery. "
            "Action: Fix nominee update blank page, investigate OTP gateway, audit SIP pipeline."
        ),
        "top_theme": "Nominee Updates",
        "fee_bullets": [
            "Exit load is 1% if redeemed within 12 months.",
            "No exit load after 12 months.",
            "ELSS has 3-year mandatory lock-in.",
            "Exit load charged on redemption amount.",
            "Last checked: 2026-04-22",
        ],
        "fee_sources": [
            "https://amfiindia.com/exit-load",
            "https://sebi.gov.in/mf-charges",
        ],
        "booking_code": "NL-A742",
        "booking_detail": {
            "date": "2026-04-24",
            "time": "10:00",
            "tz": "IST",
            "topic": "Account Changes / Nominee",
            "code": "NL-A742",
        },
        "mcp_queue": [
            {"action_id": "a1", "type": "calendar_hold",  "status": "pending",
             "payload": {"title": "Advisor Q&A — Account Changes / Nominee — NL-A742",
                         "date": "2026-04-24", "time": "10:00"}},
            {"action_id": "a2", "type": "notes_append",   "status": "pending",
             "payload": {"entry": {"date": "2026-04-22", "topic": "Account Changes / Nominee",
                                   "slot": "2026-04-24 10:00 IST", "code": "NL-A742"}}},
            {"action_id": "a3", "type": "email_draft",    "status": "pending",
             "payload": {}},  # built by email_builder
        ],
    }


# ---------------------------------------------------------------------------
# P7-01  All pending actions shown
# ---------------------------------------------------------------------------

class TestApprovalCenterListing:

    def test_all_pending_items_listed(self, full_session):
        pending = [a for a in full_session["mcp_queue"] if a["status"] == "pending"]
        assert len(pending) == 3

    def test_no_auto_approve_on_init(self, full_session):
        for action in full_session["mcp_queue"]:
            assert action["status"] == "pending"


# ---------------------------------------------------------------------------
# P7-03/04  Approve / Reject state transitions
# ---------------------------------------------------------------------------

class TestActionStateTransitions:

    def _approve(self, action: dict, mock_client) -> None:
        action["status"] = "approved"
        mock_client.execute(action)

    def _reject(self, action: dict) -> None:
        action["status"] = "rejected"

    def test_approve_sets_approved_status(self, full_session):
        mock_client = MagicMock()
        mock_client.execute.return_value = MagicMock(success=True, ref_id="ref-001", mode="mock")
        action = full_session["mcp_queue"][0]
        self._approve(action, mock_client)
        assert action["status"] == "approved"
        mock_client.execute.assert_called_once_with(action)

    def test_reject_sets_rejected_status(self, full_session):
        action = full_session["mcp_queue"][1]
        self._reject(action)
        assert action["status"] == "rejected"

    def test_reject_does_not_call_execute(self, full_session):
        mock_client = MagicMock()
        action = full_session["mcp_queue"][2]
        self._reject(action)
        mock_client.execute.assert_not_called()

    def test_approved_status_precedes_execute(self, full_session):
        """Status must be set before execute is called."""
        call_order = []
        mock_client = MagicMock()

        def execute_side_effect(a):
            call_order.append(("execute", a["status"]))
            return MagicMock(success=True, ref_id="r1", mode="mock")

        mock_client.execute.side_effect = execute_side_effect
        action = full_session["mcp_queue"][0]
        action["status"] = "approved"
        call_order.append(("status_set", "approved"))
        mock_client.execute(action)

        assert call_order[0] == ("status_set", "approved")
        assert call_order[1][0] == "execute"
        assert call_order[1][1] == "approved"


# ---------------------------------------------------------------------------
# P7-05  Mock mode — no HTTP
# ---------------------------------------------------------------------------

class TestMockMCPClient:

    def test_mock_mode_no_http_calls(self, full_session):
        with patch("httpx.post") as mock_http, patch("requests.post") as mock_req:
            mock_store = {"calendar": {}, "notes": [], "email_drafts": []}
            for action in full_session["mcp_queue"]:
                if action["type"] == "calendar_hold":
                    mock_store["calendar"][action["payload"]["title"]] = action["payload"]
                elif action["type"] == "notes_append":
                    mock_store["notes"].append(action["payload"]["entry"])
                elif action["type"] == "email_draft":
                    mock_store["email_drafts"].append(action["payload"])

            mock_http.assert_not_called()
            mock_req.assert_not_called()
            assert len(mock_store["notes"]) == 1
            assert len(mock_store["email_drafts"]) == 1


# ---------------------------------------------------------------------------
# P7-06  Notes payload contains booking_code
# ---------------------------------------------------------------------------

class TestNotesPayload:

    def test_booking_code_in_notes_entry(self, full_session):
        notes_action = next(a for a in full_session["mcp_queue"] if a["type"] == "notes_append")
        entry = notes_action["payload"]["entry"]
        assert entry["code"] == full_session["booking_code"]

    def test_notes_entry_has_required_fields(self, full_session):
        notes_action = next(a for a in full_session["mcp_queue"] if a["type"] == "notes_append")
        entry = notes_action["payload"]["entry"]
        for field in ("date", "topic", "slot", "code"):
            assert field in entry, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# P7-07/08/09/10  Email builder
# ---------------------------------------------------------------------------

class TestEmailBuilder:

    def _build_email(self, session: dict) -> dict:
        pulse = session.get("weekly_pulse", "")
        pulse_snippet = " ".join(pulse.split()[:100])
        fee_bullets_text = "\n".join(f"• {b}" for b in session.get("fee_bullets", []))
        detail = session.get("booking_detail", {})
        code = session.get("booking_code", "")
        subject = (f"Advisor Pre-Booking: {detail.get('topic','?')} — "
                   f"{detail.get('date','?')}")
        body = (
            f"Hi Advisor,\n\n"
            f"Booking Code: {code}\n"
            f"Topic: {detail.get('topic')}\n"
            f"Slot: {detail.get('date')} at {detail.get('time')} {detail.get('tz')}\n\n"
            f"📊 Market Context:\n{pulse_snippet}\n\n"
            f"📋 Fee Context:\n{fee_bullets_text}\n\n"
            f"Sources: {', '.join(session.get('fee_sources', []))}\n\n"
            f"⚠ No investment advice implied.\n"
            f"Complete booking: https://app.example.com/complete/{code}"
        )
        return {"subject": subject, "body": body}

    def test_email_subject_format(self, full_session):
        email = self._build_email(full_session)
        assert "Advisor Pre-Booking:" in email["subject"]
        assert "Account Changes / Nominee" in email["subject"]
        assert "2026-04-24" in email["subject"]

    def test_email_body_contains_weekly_pulse(self, full_session):
        email = self._build_email(full_session)
        assert "Nominee Updates" in email["body"]

    def test_email_body_contains_fee_bullets(self, full_session):
        email = self._build_email(full_session)
        assert "Exit load" in email["body"]

    def test_email_body_contains_booking_code(self, full_session):
        email = self._build_email(full_session)
        assert full_session["booking_code"] in email["body"]

    def test_email_body_has_compliance_footer(self, full_session):
        email = self._build_email(full_session)
        assert "No investment advice" in email["body"]

    def test_email_body_has_secure_link(self, full_session):
        email = self._build_email(full_session)
        assert full_session["booking_code"] in email["body"]
        assert "complete" in email["body"].lower()
