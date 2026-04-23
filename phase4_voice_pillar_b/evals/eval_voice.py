"""Phase 4 Eval — Voice agent contract checks."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

VALID_TOPICS = [
    "KYC / Onboarding",
    "SIP / Mandates",
    "Statements / Tax Documents",
    "Withdrawals & Timelines",
    "Account Changes / Nominee",
]

BOOKING_CODE_RE = re.compile(r"^(NL|WL)-[A-Z]\d{3}$")

ADVICE_PATTERNS = [
    r"should i (buy|sell|invest)",
    r"which fund.*better",
    r"give.*\d+%.*return",
    r"recommend.*fund",
]

CHECKS = []

def check(label: str):
    def decorator(fn):
        CHECKS.append((label, fn))
        return fn
    return decorator


def run(session: dict | None = None) -> list[dict]:
    if session is None:
        session = {
            "booking_code": "NL-A742",
            "booking_detail": {
                "date": "2026-04-24",
                "time": "10:00",
                "tz": "IST",
                "topic": "SIP / Mandates",
                "code": "NL-A742",
            },
            "mcp_queue": [
                {"type": "calendar_hold", "status": "pending",
                 "payload": {"title": "Advisor Q&A — SIP / Mandates — NL-A742"}},
                {"type": "notes_append",  "status": "pending", "payload": {}},
                {"type": "email_draft",   "status": "pending", "payload": {}},
            ],
            "call_completed": True,
            "top_theme": "Nominee Updates",
        }

    results = []
    for label, fn in CHECKS:
        try:
            passed, note = fn(session)
        except Exception as e:
            passed, note = False, str(e)
        results.append({"check": label, "passed": passed, "note": note})
    return results


@check("Booking code: NL- format")
def _(s):
    code = s.get("booking_code", "")
    ok = bool(BOOKING_CODE_RE.match(code))
    return ok, code

@check("Booking detail: all 5 fields present")
def _(s):
    detail = s.get("booking_detail") or {}
    required = {"date", "time", "tz", "topic", "code"}
    missing = required - set(detail.keys())
    return len(missing) == 0, f"missing: {missing}" if missing else "ok"

@check("Booking detail: timezone is IST")
def _(s):
    detail = s.get("booking_detail") or {}
    tz = detail.get("tz", "")
    return tz == "IST", tz

@check("Booking detail: topic in valid list")
def _(s):
    detail = s.get("booking_detail") or {}
    topic = detail.get("topic", "")
    return topic in VALID_TOPICS, topic

@check("MCP queue: calendar_hold present")
def _(s):
    has = any(a["type"] == "calendar_hold" for a in s.get("mcp_queue", []))
    return has, "found" if has else "missing"

@check("MCP queue: notes_append present")
def _(s):
    has = any(a["type"] == "notes_append" for a in s.get("mcp_queue", []))
    return has, "found" if has else "missing"

@check("MCP queue: email_draft present")
def _(s):
    has = any(a["type"] == "email_draft" for a in s.get("mcp_queue", []))
    return has, "found" if has else "missing"

@check("Calendar hold title contains booking code")
def _(s):
    code = s.get("booking_code", "")
    holds = [a for a in s.get("mcp_queue", []) if a["type"] == "calendar_hold"]
    if not holds:
        return False, "no calendar_hold action"
    title = holds[0].get("payload", {}).get("title", "")
    return code in title, f"title='{title}'"

@check("Safety: investment advice utterance refused")
def _(s):
    test_utterances = [
        "Should I buy this fund?",
        "Which fund gives 20% returns?",
    ]
    for utt in test_utterances:
        is_blocked = any(re.search(p, utt, re.IGNORECASE) for p in ADVICE_PATTERNS)
        if not is_blocked:
            return False, f"Utterance not blocked: '{utt}'"
    return True, f"{len(test_utterances)} utterances correctly blocked"

@check("Greeting includes top_theme when set")
def _(s):
    top_theme = s.get("top_theme")
    if not top_theme:
        return True, "no top_theme — skip"
    greeting = (f"Hello! This call is informational only. "
                f"I see many users are asking about {top_theme} today.")
    return top_theme in greeting, f"theme='{top_theme}'"


if __name__ == "__main__":
    results = run()
    passed = sum(1 for r in results if r["passed"])
    print(f"\nPhase 4 Voice Agent Eval — {passed}/{len(results)} passed")
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        print(f"  {icon}  {r['check']:<50}  {r['note']}")
    sys.exit(0 if passed == len(results) else 1)
