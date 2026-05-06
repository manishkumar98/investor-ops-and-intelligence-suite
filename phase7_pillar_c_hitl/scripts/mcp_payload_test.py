"""
End-to-end test: simulate a voice booking → enqueue MCP actions →
execute each in 'live' mode with the underlying tool stubbed,
and assert the constructed MCPPayload has correct ISO datetimes
and a real created_at_ist (not the slot date).

Catches the Railway-prod bug where:
  - calendar_hold built MCPPayload(slot_start_iso="10:00") → invalid ISO
  - sheet_entry's created_at_ist was set to the slot date, not now()
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

logging.getLogger().setLevel(logging.CRITICAL)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ["MCP_MODE"] = "live"  # exercise live-path code without real API calls

from phase7_pillar_c_hitl.mcp_client import MCPClient, enqueue_action  # noqa: E402

OK = "✅"
NO = "❌"


def _box(t):
    print()
    print("═" * 70)
    print(f"  {t}")
    print("═" * 70)


def main() -> None:
    session: dict = {}

    # Simulate what voice_agent enqueues for a booking
    enqueue_action(session, type="calendar_hold", source="m3_voice", payload={
        "title":        "Advisor Q&A — KYC and Onboarding — NL-AB23",
        "date":         "2026-05-08",
        "time":         "10:00",
        "tz":           "IST",
        "topic":        "kyc_onboarding",
        "booking_code": "NL-AB23",
    })
    enqueue_action(session, type="sheet_entry", source="m3_voice", payload={
        "booking_code":   "NL-AB23",
        "topic_key":      "kyc_onboarding",
        "topic_label":    "KYC and Onboarding",
        "slot_start_ist": "Friday, 2026-05-08 at 10:00 AM IST",
        "date":           "2026-05-08",
        "status":         "CONFIRMED",
        "call_id":        "call-test-001",
    })
    enqueue_action(session, type="email_draft", source="m3_voice", payload={
        "subject":        "Pre-Booking Alert: KYC and Onboarding — 2026-05-08 @ 10:00",
        "booking_code":   "NL-AB23",
        "topic_label":    "KYC and Onboarding",
        "slot_start_ist": "Friday, 2026-05-08 at 10:00 AM IST",
        "body":           "Dear Advisor, ...",
    })
    enqueue_action(session, type="notes_append", source="m3_voice", payload={
        "doc_title": "Advisor Pre-Bookings",
        "entry":     {"date": "2026-05-08", "topic": "KYC", "slot": "10:00 AM IST",
                      "booking_code": "NL-AB23", "status": "CONFIRMED"},
    })

    print(f"Enqueued {len(session['mcp_queue'])} actions")

    # ── Stub external tools so we capture the MCPPayload they receive ────────
    captured: dict = {}

    def fake_create_calendar_hold(payload):
        captured["calendar"] = payload
        from phase7_pillar_c_hitl.mcp.models import ToolResult
        return ToolResult(success=True, data={"event_id": "test-evt-1"})

    def fake_append_row_sync(payload, event_id=None):
        captured["sheet"] = (payload, event_id)
        return {"row_index": 7}

    def fake_send_advisor_email(payload):
        captured["email"] = payload
        return None

    def fake_append_notes_sync(payload):
        captured["notes"] = payload
        return None

    client = MCPClient(mode="live")

    with patch("phase7_pillar_c_hitl.mcp.calendar_tool.create_calendar_hold",
               side_effect=fake_create_calendar_hold), \
         patch("phase7_pillar_c_hitl.mcp.sheets_tool._append_row_sync",
               side_effect=fake_append_row_sync), \
         patch("phase7_pillar_c_hitl.mcp_client._send_advisor_email_live",
               side_effect=fake_send_advisor_email), \
         patch("phase7_pillar_c_hitl.mcp.docs_tool.append_notes_sync",
               side_effect=fake_append_notes_sync):
        for action in session["mcp_queue"]:
            res = client.execute(action)
            label = action["type"]
            if res.success:
                print(f"  {OK} execute({label}) → success")
            else:
                print(f"  {NO} execute({label}) FAILED: {action.get('error_msg')}")

    # ── Assertions ───────────────────────────────────────────────────────────
    _box("CALENDAR_HOLD MCPPayload")
    cal = captured["calendar"]
    print(f"  slot_start_iso = {cal.slot_start_iso}")
    print(f"  slot_end_iso   = {cal.slot_end_iso}")
    print(f"  created_at_ist = {cal.created_at_ist}")
    assert cal.slot_start_iso.startswith("2026-05-08T10:00:00"), "calendar slot_start_iso wrong"
    assert datetime.fromisoformat(cal.slot_start_iso), "calendar slot_start_iso unparseable"
    assert cal.slot_end_iso.startswith("2026-05-08T10:30:00"), "calendar slot_end_iso wrong"
    # created_at must be a recent timestamp, NOT the slot date "2026-05-08"
    assert datetime.fromisoformat(cal.created_at_ist).year >= 2025, "calendar created_at not real"
    assert not cal.created_at_ist.startswith("2026-05-08T00:00"), "calendar created_at == slot date (BUG)"
    print(f"  {OK} ISO datetime is parseable")
    print(f"  {OK} created_at is a real timestamp (not slot date)")

    _box("SHEET_ENTRY MCPPayload")
    sheet, _ = captured["sheet"]
    print(f"  slot_start_iso = {sheet.slot_start_iso}")
    print(f"  slot_start_ist = {sheet.slot_start_ist}")
    print(f"  created_at_ist = {sheet.created_at_ist}")
    assert sheet.slot_start_iso.startswith("2026-05-08T10:00:00"), \
        f"sheet slot_start_iso wrong: {sheet.slot_start_iso!r}"
    assert datetime.fromisoformat(sheet.created_at_ist).year >= 2025, "sheet created_at not real"
    assert not sheet.created_at_ist.startswith("2026-05-08"), "sheet created_at == slot date (BUG)"
    print(f"  {OK} slot_start_iso is parseable ISO datetime")
    print(f"  {OK} slot_start_ist preserved as human display string")
    print(f"  {OK} created_at is a real timestamp (not slot date)")

    _box("EMAIL + NOTES")
    print(f"  email payload received: subject={captured['email'].get('subject')!r}")
    print(f"  notes payload received: doc_title={captured['notes'].get('doc_title')!r}")
    print(f"  {OK} all 4 action types executed successfully")

    print()
    print("═" * 70)
    print("  ALL ASSERTIONS PASSED")
    print("═" * 70)


if __name__ == "__main__":
    main()
