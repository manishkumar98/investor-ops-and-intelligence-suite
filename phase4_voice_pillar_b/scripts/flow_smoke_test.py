"""
End-to-end smoke test for voice agent flows.

Simulates voice utterances (text in, text out — TTS bypassed) for:
  1. Booking happy path
  2. Booking with specific date "9th May"
  3. Booking with slash date "5/9"
  4. Booking with bare ordinal "the 15th"
  5. Reschedule with code-in-utterance
  6. Reschedule with code on second turn + invalid code retry
  7. Cancel with confirmation
  8. Cancel then "no, keep it"
  9. End-call mid-flow ("never mind")
 10. Intent switch mid-flow (book → cancel)

Run:  python -m phase4_voice_pillar_b.scripts.flow_smoke_test
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
logging.getLogger().setLevel(logging.CRITICAL)
for n in ("phase6_pillar_b_voice", "voice", "tts_engine", "stt_engine",
          "phase4_voice_pillar_b"):
    logging.getLogger(n).setLevel(logging.CRITICAL)

# Ensure repo root on path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# Disable real TTS / STT for fast testing
os.environ["TTS_DISABLED"] = "1"
os.environ.setdefault("STT_LANGUAGE", "en")

from phase4_voice_pillar_b.voice_agent import VoiceAgent  # noqa: E402


def _box(title: str) -> None:
    print()
    print("═" * 78)
    print(f"  {title}")
    print("═" * 78)


def run_flow(title: str, utterances: list[str], session: dict | None = None) -> VoiceAgent:
    _box(title)
    session = session or {}
    agent = VoiceAgent(session=session)
    greeting, _ = agent.get_greeting()
    print(f"[STATE={agent.state:<14}] AGENT: {greeting[:160]}")
    for utt in utterances:
        print(f"\n  USER:  {utt!r}")
        try:
            response, _ = agent.step(utt)
        except Exception as exc:
            print(f"  💥 EXCEPTION: {type(exc).__name__}: {exc}")
            break
        print(f"[STATE={agent.state:<14}] AGENT: {response[:240]}")
    return agent


def main() -> None:
    # ── 1. Booking happy path ────────────────────────────────────────────────
    run_flow("FLOW 1 — Booking happy path", [
        "Yes, I'd like to book a call",
        "KYC and onboarding",
        "Tomorrow morning",
        "First option please",
        "Yes, confirm",
    ])

    # ── 2. Booking with "8th May" (date in calendar) ─────────────────────────
    run_flow("FLOW 2 — Booking with date '8th May' (filter must hit)", [
        "I want to book an appointment",
        "SIP and mandates",
        "8th May",
        "Option 1",
        "Yes please",
    ])

    # ── 3. Booking with slash date "8/5" (8th May) ───────────────────────────
    run_flow("FLOW 3 — Booking with date '8/5' (DD/MM = 8th May)", [
        "Book a call",
        "Statements and tax",
        "8/5 morning",
        "Option 1",
        "Yes",
    ])

    # ── 4. Booking with bare ordinal "the 15th" ──────────────────────────────
    run_flow("FLOW 4 — Booking with bare ordinal 'the 15th'", [
        "Book me",
        "Withdrawals",
        "the 15th",
        "First slot",
        "Confirm",
    ])

    # ── 5. Reschedule with code-in-utterance ─────────────────────────────────
    run_flow("FLOW 5 — Reschedule (code given upfront)", [
        "I want to reschedule my booking NL-AB23",
        "Tomorrow afternoon",
        "First option",
        "Yes",
    ])

    # ── 6. Reschedule — invalid code retry then valid ────────────────────────
    run_flow("FLOW 6 — Reschedule (invalid code → valid)", [
        "Reschedule please",
        "I think it was XYZ-1234",
        "NL-AB23",
        "Tomorrow morning",
        "Option 1",
        "Yes",
    ])

    # ── 7. Cancel with confirmation ──────────────────────────────────────────
    run_flow("FLOW 7 — Cancel (yes confirm)", [
        "Cancel my appointment NL-AB23",
        "Yes, cancel it",
    ])

    # ── 8. Cancel then "no, keep it" ─────────────────────────────────────────
    run_flow("FLOW 8 — Cancel then keep", [
        "I want to cancel NL-AB23",
        "No, keep it",
    ])

    # ── 9. End-call mid-flow ─────────────────────────────────────────────────
    run_flow("FLOW 9 — End-call mid-flow ('never mind')", [
        "I want to book",
        "KYC",
        "Never mind, bye",
    ])

    # ── 10. Intent switch book → cancel ──────────────────────────────────────
    run_flow("FLOW 10 — Intent switch book → cancel", [
        "Book me",
        "SIP",
        "Actually cancel my booking NL-AB23 instead",
        "Yes confirm",
    ])

    # ── 11. Spoken booking code "N L A B 2 3" ────────────────────────────────
    run_flow("FLOW 11 — Spoken code 'N L A B 2 3'", [
        "Cancel my booking",
        "N L A B 2 3",
        "Yes",
    ])

    print()
    print("═" * 78)
    print("  ALL FLOWS COMPLETED")
    print("═" * 78)


if __name__ == "__main__":
    main()
