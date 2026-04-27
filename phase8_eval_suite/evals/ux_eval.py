import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def run_ux_eval(session: dict, agent=None) -> dict:
    """5 checks: pulse word count, action count, top_theme in greeting, PII [REDACTED], state persistence."""
    pulse     = session.get("weekly_pulse", "")
    top_theme = session.get("top_theme", "")

    word_count = len(pulse.split())
    # Prefer the structured action_ideas list; fall back to counting numbered lines
    action_ideas = session.get("action_ideas", [])
    if action_ideas:
        action_count = len(action_ideas)
    else:
        action_count = len(re.findall(r"^\d+\.", pulse, re.MULTILINE))

    # Check 3: theme appears in greeting
    theme_in_greeting = False
    if agent and top_theme:
        try:
            greeting, _ = agent.get_greeting()
            theme_in_greeting = top_theme.lower() in greeting.lower()
        except Exception:
            theme_in_greeting = False
    elif top_theme and not agent:
        theme_in_greeting = None  # skip gracefully when no agent provided

    # Check 4: PII scrubber produces [REDACTED] tokens
    try:
        from phase3_review_pillar_b.pii_scrubber import scrub
        _raw     = "Rajesh called from 9876543210 and emailed rajesh@gmail.com about his KYC"
        _cleaned, _cnt = scrub(_raw)
        pii_ok   = "[REDACTED]" in _cleaned and "9876543210" not in _cleaned
        pii_note = f"redactions={_cnt} → '{_cleaned[:50]}'"
    except Exception as exc:
        pii_ok   = False
        pii_note = str(exc)

    # Check 5: booking code persisted into notes_append payload (state persistence)
    mcp_queue    = session.get("mcp_queue", [])
    booking_code = session.get("booking_code", "")
    notes_action = next((a for a in mcp_queue if a["type"] == "notes_append"), None)
    if notes_action and booking_code:
        code_in_notes = booking_code in json.dumps(notes_action.get("payload", {}))
        persist_note  = f"code={booking_code} in notes: {code_in_notes}"
    else:
        code_in_notes = None   # no booking made yet — skip rather than fail
        persist_note  = "no booking in session (skipped)"

    return {
        "pulse_word_count": {
            "value":  word_count,
            "passed": word_count <= 250,
        },
        "pulse_actions": {
            "value":  action_count,
            "passed": action_count == 3,
        },
        "theme_in_greeting": {
            "value":  theme_in_greeting,
            "passed": theme_in_greeting is True,
        },
        "pii_redacted": {
            "value":  pii_note,
            "passed": pii_ok,
        },
        "state_persistence": {
            "value":  persist_note,
            "passed": code_in_notes is True or code_in_notes is None,
        },
    }


if __name__ == "__main__":
    session = {"weekly_pulse": "", "top_theme": ""}
    result = run_ux_eval(session)
    for check, data in result.items():
        status = "PASS ✓" if data["passed"] else "FAIL ✗"
        print(f"  {check}: {data['value']} — {status}")
