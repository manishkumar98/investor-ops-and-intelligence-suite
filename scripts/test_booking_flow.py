"""
Simulate a complete voice-agent booking flow without microphone/TTS.
Drives the FSM text-only so you can verify MCP output gets queued.

Run from repo root:
    python scripts/test_booking_flow.py
"""
import sys
import json
from pathlib import Path

# Ensure repo root is on the path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from phase4_voice_pillar_b.voice_agent import VoiceAgent

# ── Mock session (mirrors what Streamlit puts in st.session_state) ────────────
session = {
    "pulse_data": {
        "top_3_themes": ["App Performance", "SIP Management", "KYC Issues"],
        "themes": ["App Performance", "SIP Management", "KYC Issues", "Fee Transparency", "UI/UX"],
        "weekly_note": "Users report frequent app crashes during market hours.",
        "action_ideas": ["Fix crash on order screen", "Add SIP pause feature", "Improve KYC flow"],
        "quotes": ["App freezes every morning at 9:15.", "SIP got deducted twice.", "KYC keeps failing."],
    },
    "mcp_queue": [],   # will be populated on BOOKED
}

CALENDAR = str(ROOT / "data" / "mock_calendar.json")

# ── Conversation script: user utterances through each FSM state ───────────────
SCRIPT = [
    # GREET  → user acknowledges disclaimer
    "yes I understand",
    # INTENT → booking
    "I want to book a call with an advisor",
    # TOPIC  → SIP
    "mutual funds and SIP",
    # TIMEPREF → morning
    "morning",
    # OFFERSLOTS → pick first slot
    "1",
    # CONFIRM → confirm booking
    "yes confirm",
]

DIVIDER = "─" * 60

def main():
    print(f"\n{'═'*60}")
    print("  VOICE AGENT — BOOKING FLOW SIMULATION (text-only)")
    print(f"{'═'*60}\n")

    agent = VoiceAgent(session=session, calendar_path=CALENDAR)
    greeting, _ = agent.get_greeting()
    print(f"[AGENT — GREET]\n{greeting}\n{DIVIDER}")

    for i, utterance in enumerate(SCRIPT):
        print(f"[USER] {utterance}")
        response, _ = agent.step(utterance)
        print(f"[AGENT — {agent.state}]\n{response}\n{DIVIDER}")

        if agent.state in ("BOOKED", "WAITLIST"):
            print(f"\n✅ Flow complete — final state: {agent.state}")
            break

    # ── Show what was queued for MCP ──────────────────────────────────────────
    queue = session.get("mcp_queue", [])
    if queue:
        print(f"\n📋 MCP QUEUE ({len(queue)} item(s)):")
        print(json.dumps(queue, indent=2, ensure_ascii=False))
    else:
        print("\n⚠️  mcp_queue is empty — check if BOOKED state pushes to session['mcp_queue']")

    # ── Persist queue to data/mcp_state.json so Streamlit app picks it up ────
    mcp_state_path = ROOT / "data" / "mcp_state.json"
    if queue:
        existing = []
        if mcp_state_path.exists():
            try:
                existing = json.loads(mcp_state_path.read_text())
                if not isinstance(existing, list):
                    existing = []
            except Exception:
                existing = []
        merged = existing + [a for a in queue if a not in existing]
        mcp_state_path.write_text(json.dumps(merged, indent=2, ensure_ascii=False))
        print(f"\n💾 Saved {len(queue)} action(s) → {mcp_state_path}")
        print("   Reload the Streamlit app (Tab 3 — Super-Agent MCP Workflow) to see pending approvals.")

    # ── Show booking log ──────────────────────────────────────────────────────
    log = ROOT / "data" / "bookings.json"
    if log.exists():
        bookings = json.loads(log.read_text())
        latest = bookings[-1] if isinstance(bookings, list) else bookings
        print(f"\n📅 LATEST BOOKING (data/bookings.json):")
        print(json.dumps(latest, indent=2, ensure_ascii=False))
    else:
        print("\n⚠️  data/bookings.json not found")


if __name__ == "__main__":
    main()
