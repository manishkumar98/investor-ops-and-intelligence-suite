"""Phase 3 Eval — Review pipeline output quality checks."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

PII_PATTERNS = [
    r"\+?91[\s\-]?\d{10}",
    r"[\w.+\-]+@[\w\-]+\.[\w.]+",
    r"[A-Z]{5}\d{4}[A-Z]",
]

CHECKS = []

def check(label: str):
    def decorator(fn):
        CHECKS.append((label, fn))
        return fn
    return decorator


def run(session: dict | None = None) -> list[dict]:
    if session is None:
        # Use a mock session for standalone eval
        session = {
            "weekly_pulse": (
                "This week's top themes: Nominee Update issues (12 users), "
                "Login/OTP problems (9 users), SIP mandate failures (6 users).\n\n"
                "User quote: \"The nominee update screen shows a blank page.\"\n"
                "User quote: \"OTP not coming on registered number.\"\n"
                "User quote: \"SIP deducted but units not reflecting.\"\n\n"
                "Action Ideas:\n"
                "1. Escalate nominee update flow — P0 bug.\n"
                "2. Investigate OTP delivery — check SMS gateway.\n"
                "3. Audit SIP mandate pipeline."
            ),
            "top_theme": "Nominee Updates",
            "top_3_themes": ["Nominee Updates", "Login Issues", "SIP Failures"],
            "fee_bullets": [
                "Exit load is 1% if redeemed within 12 months.",
                "No exit load after 12 months for equity funds.",
                "ELSS has 3-year mandatory lock-in; no redemption before that.",
                "Exit load is charged on redemption amount.",
                "Refer to the fund SID for specific slabs.",
                "Last checked: 2026-04-22",
            ],
            "fee_sources": [
                "https://amfiindia.com/exit-load",
                "https://sebi.gov.in/mf-charges",
            ],
            "mcp_queue": [
                {"type": "notes_append", "status": "pending", "payload": {}},
                {"type": "email_draft",  "status": "pending", "payload": {}},
            ],
            "pulse_generated": True,
        }

    results = []
    for label, fn in CHECKS:
        try:
            passed, note = fn(session)
        except Exception as e:
            passed, note = False, str(e)
        results.append({"check": label, "passed": passed, "note": note})
    return results


@check("Pulse: word count ≤ 250")
def _(s):
    pulse = s.get("weekly_pulse", "")
    wc = len(pulse.split())
    return wc <= 250, f"{wc} words"

@check("Pulse: exactly 3 action ideas")
def _(s):
    pulse = s.get("weekly_pulse", "")
    count = len([l for l in pulse.split("\n") if re.match(r"^\d+\.", l.strip())])
    return count == 3, f"found {count} action lines"

@check("Pulse: top_theme set in session")
def _(s):
    theme = s.get("top_theme")
    return bool(theme), str(theme)

@check("Pulse: top_3_themes has 3 items")
def _(s):
    top3 = s.get("top_3_themes", [])
    return len(top3) == 3, f"found {len(top3)}"

@check("Fee: bullet count ≤ 6")
def _(s):
    bullets = s.get("fee_bullets", [])
    return len(bullets) <= 6, f"{len(bullets)} bullets"

@check("Fee: 2 source URLs")
def _(s):
    sources = s.get("fee_sources", [])
    return len(sources) == 2, f"{len(sources)} sources"

@check("Fee: 'Last checked' present in bullets")
def _(s):
    bullets = s.get("fee_bullets", [])
    has_last_checked = any("Last checked" in b for b in bullets)
    return has_last_checked, "present" if has_last_checked else "missing"

@check("MCP: notes_append action pending")
def _(s):
    queue = s.get("mcp_queue", [])
    has = any(a["type"] == "notes_append" and a["status"] == "pending" for a in queue)
    return has, "found" if has else "missing"

@check("MCP: email_draft action pending")
def _(s):
    queue = s.get("mcp_queue", [])
    has = any(a["type"] == "email_draft" and a["status"] == "pending" for a in queue)
    return has, "found" if has else "missing"

@check("PII: pulse is PII-free")
def _(s):
    pulse = s.get("weekly_pulse", "")
    for p in PII_PATTERNS:
        if re.search(p, pulse):
            return False, f"PII pattern matched: {p}"
    return True, "clean"


if __name__ == "__main__":
    results = run()
    passed = sum(1 for r in results if r["passed"])
    print(f"\nPhase 3 Pipeline Eval — {passed}/{len(results)} passed")
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        print(f"  {icon}  {r['check']:<45}  {r['note']}")
    sys.exit(0 if passed == len(results) else 1)
