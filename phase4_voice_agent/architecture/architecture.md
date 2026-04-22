# Phase 4 Architecture — Voice Agent (M3)

## Dialogue State Machine

```
         ┌─────────┐
  start  │  GREET  │  reads top_theme from session (Phase 6 wires this)
    ──►  │         │  delivers disclaimer
         └────┬────┘
              │ user speaks
              ▼
         ┌─────────┐     ┌─────────────────────────────────┐
         │ INTENT  │────►│ what_to_prepare / check_avail   │
         │(LLM     │     │ → answer + END                  │
         │ classif)│     └─────────────────────────────────┘
         └────┬────┘
              │ book_new / reschedule / cancel
              ▼
         ┌─────────┐
         │  TOPIC  │  slot-filling; maps free text → 5 valid topics
         │(confirm)│  "Got it — [Topic]. Is that right?"
         └────┬────┘
              │ confirmed
              ▼
         ┌──────────┐
         │ TIMEPREF │  "What day and time works? (IST)"
         │          │  parse weekday + AM/PM from utterance
         └────┬─────┘
              │
              ▼
         ┌────────────┐     ┌─────────────────────────────────┐
         │ OFFERSLOTS │────►│ no match → WAITLIST             │
         │            │     │ code prefix WL-                 │
         │ offer 2    │     │ enqueue waitlist_hold +         │
         │ matched    │     │ waitlist_email_draft            │
         │ slots      │     └─────────────────────────────────┘
         └─────┬──────┘
               │ user picks slot
               ▼
         ┌──────────┐
         │ CONFIRM  │  "Topic: X, Date: Y at Z IST. Confirm?"
         └────┬─────┘
              │ yes
              ▼
         ┌──────────┐
         │  BOOKED  │  generate_booking_code() → NL-A742
         │          │  write session["booking_code"]
         │          │  write session["booking_detail"]
         │          │  enqueue: calendar_hold, notes_append,
         │          │           email_draft → mcp_queue
         │          │  read booking code + secure URL to user
         └──────────┘
```

## Key Interfaces

```python
# pillar_b/voice_agent.py

def generate_booking_code(prefix: str = "NL") -> str:
    """Returns e.g. 'NL-A742'. Format: {prefix}-[A-Z][0-9]{3}"""

class VoiceAgent:
    def __init__(self, session: dict, calendar_path: str): ...

    def get_greeting(self) -> str:
        """Returns greeting string; injects top_theme if set in session."""

    def detect_intent(self, utterance: str) -> str:
        """Returns one of: book_new|reschedule|cancel|what_to_prepare|check_availability"""

    def fill_topic_slot(self, utterance: str) -> str:
        """Maps free-text to one of 5 valid topics."""

    def offer_slots(self, day_preference: str, period: str) -> list[dict]:
        """Returns up to 2 matching slots from mock calendar."""

    def confirm_booking(self, slot: dict, topic: str) -> dict:
        """
        Generates booking code, writes to session, enqueues MCP actions.
        Returns: {booking_code, slot, topic, secure_url}
        """

    def safety_refusal(self, utterance: str) -> str | None:
        """Returns refusal string if utterance is investment advice, else None."""
```

## Audio Stack (pluggable)

```
Microphone → ASR (Whisper / Deepgram) → text utterance
                                              │
                                         VoiceAgent
                                              │
                                     text response
                                              │
                                     TTS (OpenAI tts-1)
                                              │
                                          Speaker
```
