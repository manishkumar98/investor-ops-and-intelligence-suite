import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def run_ux_eval(session: dict, agent=None) -> dict:
    """6 checks: pulse word count, action count, top_theme in greeting, PII [REDACTED],
    M2 MCP actions enqueued, state persistence (booking_code in m3 notes payload)."""
    pulse     = session.get("weekly_pulse", "")
    top_theme = session.get("top_theme", "")

    word_count = len(pulse.split())
    action_ideas = session.get("action_ideas", [])
    if action_ideas:
        action_count = len(action_ideas)
    else:
        action_count = len(re.findall(r"^\d+\.", pulse, re.MULTILINE))

    # Check 3: theme appears in voice greeting
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

    # Check 5: M2 pipeline enqueued notes_append + email_draft into mcp_queue
    mcp_queue = session.get("mcp_queue", [])
    m2_notes  = any(a.get("source") == "m2_pipeline" and a.get("type") == "notes_append"  for a in mcp_queue)
    m2_email  = any(a.get("source") == "m2_pipeline" and a.get("type") == "email_draft"   for a in mcp_queue)
    m2_ok     = m2_notes and m2_email
    m2_note   = f"notes_append={'✓' if m2_notes else '✗'} email_draft={'✓' if m2_email else '✗'}"

    # Check 6: booking_code persisted into m3_voice notes_append payload
    booking_code = session.get("booking_code", "")
    m3_notes_action = next(
        (a for a in mcp_queue if a.get("source") == "m3_voice" and a.get("type") == "notes_append"),
        None,
    )
    if m3_notes_action and booking_code:
        code_in_notes = booking_code in json.dumps(m3_notes_action.get("payload", {}))
        persist_note  = f"code={booking_code} in m3 notes: {code_in_notes}"
    else:
        code_in_notes = None   # no booking made yet — skip rather than fail
        persist_note  = "no m3 booking in session (skipped)"

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
        "m2_mcp_enqueued": {
            "value":  m2_note,
            "passed": m2_ok,
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
