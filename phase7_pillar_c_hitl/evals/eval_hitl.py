"""Phase 7 Eval — HITL MCP email completeness + action gate checks."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

CHECKS = []

def check(label: str):
    def decorator(fn):
        CHECKS.append((label, fn))
        return fn
    return decorator


def run(session: dict | None = None) -> list[dict]:
    if session is None:
        pulse = ("Top themes this week: Nominee Updates (12), Login Issues (9), SIP Failures (6). "
                 "Users frustrated with nominee update flow and OTP delivery. "
                 "Action: Fix nominee blank page, investigate OTP, audit SIP pipeline.")
        detail = {"date": "2026-04-24", "time": "10:00", "tz": "IST",
                  "topic": "Account Changes / Nominee", "code": "NL-A742"}
        fee_bullets = [
            "Exit load is 1% if redeemed within 12 months.",
            "No exit load after 12 months.",
            "ELSS has 3-year mandatory lock-in.",
            "Exit load on redemption amount.",
            "Last checked: 2026-04-22",
        ]
        fee_sources = ["https://amfiindia.com/exit-load", "https://sebi.gov.in/mf-charges"]

        pulse_snippet = " ".join(pulse.split()[:100])
        fee_text = "\n".join(f"• {b}" for b in fee_bullets)
        subject = f"Advisor Pre-Booking: {detail['topic']} — {detail['date']}"
        body = (
            f"Hi Advisor,\n\nBooking Code: NL-A742\n"
            f"Topic: {detail['topic']}\n"
            f"Slot: {detail['date']} at {detail['time']} {detail['tz']}\n\n"
            f"📊 Market Context:\n{pulse_snippet}\n\n"
            f"📋 Fee Context:\n{fee_text}\n\n"
            f"Sources: {', '.join(fee_sources)}\n\n"
            f"⚠ No investment advice implied.\n"
            f"Complete booking: https://app.example.com/complete/NL-A742"
        )
        session = {
            "weekly_pulse": pulse,
            "booking_code": "NL-A742",
            "booking_detail": detail,
            "fee_bullets": fee_bullets,
            "fee_sources": fee_sources,
            "mcp_queue": [
                {"action_id": "a1", "type": "calendar_hold",  "status": "pending",
                 "payload": {"title": f"Advisor Q&A — {detail['topic']} — NL-A742"}},
                {"action_id": "a2", "type": "notes_append",   "status": "pending",
                 "payload": {"entry": {"date": "2026-04-22", "topic": detail["topic"],
                                       "slot": "2026-04-24 10:00 IST", "booking_code": "NL-A742",
                                       "status": "CONFIRMED"}}},
                {"action_id": "a3", "type": "email_draft",    "status": "pending",
                 "payload": {"subject": subject, "body": body}},
            ],
        }

    results = []
    for label, fn in CHECKS:
        try:
            passed, note = fn(session)
        except Exception as e:
            passed, note = False, str(e)
        results.append({"check": label, "passed": passed, "note": note})
    return results


@check("Queue: all 3 action types present")
def _(s):
    types = {a["type"] for a in s.get("mcp_queue", [])}
    required = {"calendar_hold", "notes_append", "email_draft"}
    missing = required - types
    return len(missing) == 0, str(missing) if missing else "ok"

@check("Queue: all actions start as pending")
def _(s):
    non_pending = [a["type"] for a in s.get("mcp_queue", []) if a["status"] != "pending"]
    return len(non_pending) == 0, f"non-pending: {non_pending}" if non_pending else "ok"

@check("Notes: booking_code in entry payload")
def _(s):
    notes = next((a for a in s.get("mcp_queue", []) if a["type"] == "notes_append"), None)
    if not notes:
        return False, "no notes_append action"
    entry = notes["payload"].get("entry", {})
    code  = entry.get("booking_code") or entry.get("code", "")
    ok    = code == s.get("booking_code")
    return ok, f"entry.booking_code={code}"

@check("Calendar: title contains booking_code")
def _(s):
    code = s.get("booking_code", "")
    hold = next((a for a in s.get("mcp_queue", []) if a["type"] == "calendar_hold"), None)
    if not hold:
        return False, "no calendar_hold"
    title = hold["payload"].get("title", "")
    return code in title, f"title='{title[:50]}'"

@check("Email: subject has correct format")
def _(s):
    email = next((a for a in s.get("mcp_queue", []) if a["type"] == "email_draft"), None)
    if not email:
        return False, "no email_draft"
    subject = email["payload"].get("subject", "")
    ok = "Advisor Pre-Booking:" in subject
    return ok, f"subject='{subject[:60]}'"

@check("Email: body contains weekly_pulse text")
def _(s):
    email = next((a for a in s.get("mcp_queue", []) if a["type"] == "email_draft"), None)
    if not email:
        return False, "no email_draft"
    pulse_word = (s.get("weekly_pulse") or "").split()[0] if s.get("weekly_pulse") else ""
    body = email["payload"].get("body", "")
    ok = pulse_word in body if pulse_word else False
    return ok, f"first pulse word '{pulse_word}' in body: {ok}"

@check("Email: body contains fee bullets")
def _(s):
    email = next((a for a in s.get("mcp_queue", []) if a["type"] == "email_draft"), None)
    if not email:
        return False, "no email_draft"
    body = email["payload"].get("body", "")
    ok = "Exit load" in body or "expense" in body.lower()
    return ok, "fee context present" if ok else "missing"

@check("Email: compliance footer present")
def _(s):
    email = next((a for a in s.get("mcp_queue", []) if a["type"] == "email_draft"), None)
    if not email:
        return False, "no email_draft"
    body = email["payload"].get("body", "")
    ok = "No investment advice" in body
    return ok, "footer present" if ok else "missing"

@check("Email: secure link present")
def _(s):
    email = next((a for a in s.get("mcp_queue", []) if a["type"] == "email_draft"), None)
    if not email:
        return False, "no email_draft"
    body = email["payload"].get("body", "")
    code = s.get("booking_code", "")
    ok = code in body and "complete" in body.lower()
    return ok, "link present" if ok else "missing"


if __name__ == "__main__":
    results = run()
    passed = sum(1 for r in results if r["passed"])
    print(f"\nPhase 7 HITL Eval — {passed}/{len(results)} passed")
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        print(f"  {icon}  {r['check']:<55}  {r['note']}")
    sys.exit(0 if passed == len(results) else 1)
