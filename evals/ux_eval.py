import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def run_ux_eval(session: dict, agent=None) -> dict:
    """3 checks: pulse word count, action count, top_theme in greeting."""
    pulse     = session.get("weekly_pulse", "")
    top_theme = session.get("top_theme", "")

    word_count   = len(pulse.split())
    action_count = len(re.findall(r"^\d+\.", pulse, re.MULTILINE))

    # Check theme appears in greeting
    theme_in_greeting = False
    if agent and top_theme:
        try:
            greeting, _ = agent.get_greeting()
            theme_in_greeting = top_theme.lower() in greeting.lower()
        except Exception:
            theme_in_greeting = False
    elif top_theme and not agent:
        # If no agent passed, skip gracefully
        theme_in_greeting = None

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
    }


if __name__ == "__main__":
    session = {"weekly_pulse": "", "top_theme": ""}
    result = run_ux_eval(session)
    for check, data in result.items():
        status = "PASS ✓" if data["passed"] else "FAIL ✗"
        print(f"  {check}: {data['value']} — {status}")
