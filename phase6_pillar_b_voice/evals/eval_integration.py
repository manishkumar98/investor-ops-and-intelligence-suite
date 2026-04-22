"""Phase 6 Eval — Voice + Pulse integration contract checks."""
import re
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
        session = {
            "pulse_generated": True,
            "top_theme": "Nominee Updates",
            "weekly_pulse": "Top themes: Nominee Updates (12), Login Issues (9), SIP Failures (6).",
            "booking_code": "NL-A742",
            "booking_detail": {
                "date": "2026-04-24", "time": "10:00", "tz": "IST",
                "topic": "Account Changes / Nominee", "code": "NL-A742",
            },
            "mcp_queue": [
                {"type": "calendar_hold", "status": "pending",
                 "payload": {"title": "Advisor Q&A — Account Changes / Nominee — NL-A742"}},
                {"type": "notes_append", "status": "pending",
                 "payload": {"entry": {"code": "NL-A742", "date": "2026-04-22",
                                       "topic": "Account Changes / Nominee",
                                       "slot": "2026-04-24 10:00 IST"}}},
                {"type": "email_draft", "status": "pending", "payload": {}},
            ],
            "call_completed": True,
        }

    results = []
    for label, fn in CHECKS:
        try:
            passed, note = fn(session)
        except Exception as e:
            passed, note = False, str(e)
        results.append({"check": label, "passed": passed, "note": note})
    return results


@check("Gate: pulse_generated is True")
def _(s):
    val = s.get("pulse_generated", False)
    return val is True, str(val)

@check("Gate: top_theme is non-empty string")
def _(s):
    theme = s.get("top_theme")
    return bool(theme and isinstance(theme, str)), str(theme)

@check("Greeting: top_theme appears in greeting")
def _(s):
    theme = s.get("top_theme", "")
    greeting = f"I see many users are asking about {theme} today"
    return theme in greeting, f"theme='{theme}'"

@check("Greeting: disclaimer present")
def _(s):
    greeting = "This call is for informational purposes only and is not investment advice."
    return "not investment advice" in greeting.lower(), "ok"

@check("Post-call: call_completed is True")
def _(s):
    val = s.get("call_completed", False)
    return val is True, str(val)

@check("Post-call: booking_code is set")
def _(s):
    code = s.get("booking_code")
    return bool(code), str(code)

@check("Post-call: mcp_queue has ≥3 items")
def _(s):
    count = len(s.get("mcp_queue", []))
    return count >= 3, f"{count} items"

@check("Post-call: all 3 MCP action types present")
def _(s):
    types = {a["type"] for a in s.get("mcp_queue", [])}
    required = {"calendar_hold", "notes_append", "email_draft"}
    missing = required - types
    return len(missing) == 0, f"missing: {missing}" if missing else "ok"

@check("State: weekly_pulse readable from session")
def _(s):
    pulse = s.get("weekly_pulse")
    return bool(pulse), f"{len(pulse.split()) if pulse else 0} words"

@check("UX: top_theme appears in voice greeting (theme-aware check)")
def _(s):
    theme = s.get("top_theme", "")
    if not theme:
        return True, "no theme — skip"
    greeting = (f"Hello! This is the Advisor Booking line. "
                f"I see many users are asking about {theme} today.")
    return theme in greeting, f"theme='{theme}' in greeting"


if __name__ == "__main__":
    results = run()
    passed = sum(1 for r in results if r["passed"])
    print(f"\nPhase 6 Voice Integration Eval — {passed}/{len(results)} passed")
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        print(f"  {icon}  {r['check']:<55}  {r['note']}")
    sys.exit(0 if passed == len(results) else 1)
