# Phase 4 Architecture — Voice Agent (M3)

## What This Phase Does

Phase 4 is the conversational voice agent — the part of the system that can have a spoken (or typed) dialogue with a user and book an appointment with a financial advisor.

What makes this agent different from a generic scheduling bot is that it is **theme-aware**: before it says a single word, it reads this week's `top_theme` from session state (written by Phase 3). If the top customer concern this week is "Nominee Updates", the agent opens with *"I see many users are asking about nominee updates this week — I can help you book a call about that!"* This is a direct, tangible output of the cross-pillar integration. The agent knows what customers care about before the call begins.

The agent follows an **8-state Finite State Machine (FSM)** — a predetermined flow of conversation states where each state has a clear entry condition, a specific action, and a defined exit. This design ensures the conversation is always predictable, testable, and can never get stuck in an undefined state. At the end of a successful booking, the agent generates a unique booking code (like `NL-A742`), queues 4 MCP actions for human approval (calendar_hold, notes_append with M2 context, email_draft, sheet_entry), and provides the user with a secure link to complete their details.

**The voice technology stack:**
- Text-to-Speech: OpenAI `tts-1`, voice=`alloy` (locked — do not change)
- Speech-to-Text: OpenAI `whisper-1` (for microphone input)
- Text input: also supported — users can type instead of speaking
- The agent's audio plays directly in the browser via `st.audio(autoplay=True)`

---

## Dialogue State Machine

```
         ┌─────────┐
  start  │  GREET  │  reads top_theme from session
    ──►  │         │  delivers disclaimer
         │         │  mentions top theme via TTS
         └────┬────┘
              │ user responds
              ▼
         ┌─────────┐     ┌─────────────────────────────────┐
         │ INTENT  │────►│ what_to_prepare / check_avail   │
         │(LLM or  │     │ → scripted answer + END          │
         │ keyword)│     └─────────────────────────────────┘
         └────┬────┘
              │ book_new / reschedule / cancel
              ▼
         ┌─────────┐
         │  TOPIC  │  slot-filling; maps free text → 5 valid topics
         │(confirm)│  "Got it — [Topic]. Is that right?"
         └────┬────┘
              │ user confirms
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
         │ offer 2    │     │ enqueue: waitlist_hold +        │
         │ matched    │     │          waitlist_email_draft   │
         │ slots      │     └─────────────────────────────────┘
         └─────┬──────┘
               │ user picks slot
               ▼
         ┌──────────┐
         │ CONFIRM  │  "Topic: X, Date: Y at Z IST. Confirm?"
         └────┬─────┘
              │ user says yes
              ▼
         ┌──────────┐
         │  BOOKED  │  generate_booking_code() → NL-A742
         │          │  write session["booking_code"]
         │          │  write session["booking_detail"]
         │          │  enqueue: calendar_hold, notes_append,
         │          │           email_draft, sheet_entry → mcp_queue (+4)
         │          │  read booking code + secure URL to user
         └──────────┘
```

---

## Key Interfaces

```python
# pillar_b/voice_agent.py

def generate_booking_code(prefix: str = "NL") -> str:
    """
    Returns e.g. 'NL-A742'.
    Format: {prefix}-[A-Z][0-9]{3}
    Assert: re.match(r"^(NL|WL)-[A-Z]\d{3}$", code)
    """

class VoiceAgent:
    def __init__(self, session: dict, calendar_path: str): ...

    def get_greeting(self) -> tuple[str, bytes]:
        """
        Returns (greeting_text, audio_bytes).
        Reads session["top_theme"] — uses generic greeting if None.
        Always includes disclaimer: 'This is informational, not investment advice.'
        """

    def step(self, utterance: str) -> tuple[str, bytes | None]:
        """
        Advances the FSM by one turn.
        Returns (text_response, audio_bytes_or_None).
        audio_bytes is None if TTS call fails (text-only fallback).
        """

    def safety_refusal(self, utterance: str) -> str | None:
        """
        Returns refusal string if utterance matches an investment advice pattern.
        Returns None if safe.
        Called at the start of every INTENT state processing.
        """
```

---

## Audio Stack

```
User Microphone Input
         │
         ▼
  OpenAI Whisper (whisper-1)
  audio.transcriptions.create()
         │
         ▼
    text utterance
         │
         ▼
   VoiceAgent.step()
         │
         ▼
    text response
         │
         ▼
  OpenAI TTS (tts-1, voice="alloy")
  audio.speech.create()
         │
         ▼
  st.audio(audio_bytes, format="audio/mp3", autoplay=True)
         │
         ▼
  Browser speaker output
```

For text-mode (no microphone): skip Whisper; user types in `st.text_input()` directly.

---

## State Machine Full Specification

| State | Entry Condition | What the Agent Does | LLM Used | Exit To |
|---|---|---|---|---|
| GREET | Call starts | Read `top_theme`; format greeting with disclaimer + theme mention; TTS delivery | None (scripted) | INTENT (after user responds) |
| INTENT | User speaks/types | Keyword check first; LLM fallback if ambiguous; classify into 5 intents | Claude (fallback only) | TOPIC (book/reschedule/cancel) or END (what_to_prepare/check_avail) |
| TOPIC | After booking intent | Extract topic from free text; map to one of 5 valid topics; confirm back to user | Claude | TIMEPREF (after user confirms) |
| TIMEPREF | After topic confirmed | Parse weekday + AM/PM from utterance using regex | None (regex) | OFFERSLOTS |
| OFFERSLOTS | After time preference | Filter `mock_calendar.json`; offer best 2 matching slots | None (lookup) | CONFIRM (user picks) or WAITLIST (no match) |
| CONFIRM | After slot pick | Read back: topic + slot date/time in IST; ask "Is that right?" | None (scripted) | BOOKED (yes) or TIMEPREF (no) |
| BOOKED | After confirmation | Generate code; write session; enqueue 4 MCP actions (calendar_hold, notes_append with M2 context, email_draft, sheet_entry); deliver secure URL via TTS | None (scripted) | END |
| WAITLIST | No slots matched | Generate WL-prefix code; enqueue 2 MCP actions; inform user | None (scripted) | END |

---

## The 5 Valid Topics

These exact strings come from `mock_calendar.json`. The TOPIC state must map any free-text utterance to one of these:

1. KYC / Onboarding
2. SIP / Mandates
3. Statements / Tax Documents
4. Withdrawals & Timelines
5. Account Changes / Nominee

If the user says "I want to talk about changing my nominee", the agent maps this to "Account Changes / Nominee". If the user says something that doesn't map to any of the 5, the agent asks for clarification once, then defaults to the closest match.

---

## TTS and ASR Implementation

```python
# TTS — convert agent text to audio for browser playback
audio_response = openai_client.audio.speech.create(
    model="tts-1",
    voice="alloy",          # LOCKED — do not change this value
    input=agent_text,
    response_format="mp3"
)
st.audio(audio_response.content, format="audio/mp3", autoplay=True)

# ASR — transcribe user microphone input to text
transcript = openai_client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_file_object,  # from st.audio_input() widget
    language="en"
)
utterance = transcript.text
```

---

## Booking Code Generation

```python
import random, string

def generate_booking_code(prefix="NL") -> str:
    letter = random.choice(string.ascii_uppercase)
    digits = ''.join(random.choices(string.digits, k=3))
    code = f"{prefix}-{letter}{digits}"
    assert re.match(r"^(NL|WL)-[A-Z]\d{3}$", code), f"Invalid booking code format: {code}"
    return code

# Normal booking: NL-A742, NL-K319, NL-Z001
# Waitlist:       WL-B391, WL-M740
```

This code is the single thread connecting the calendar hold, the notes entry, and the advisor email. Every downstream action references it.

---

## Prerequisites

- Phase 1 complete: `config.py`, `session_init.py` working
- Phase 3 complete: `session["top_theme"]` is populated (voice agent reads it at GREET)
- `data/mock_calendar.json` exists with at least 8 advisor slots
- `OPENAI_API_KEY` valid (for TTS + ASR)
- `ANTHROPIC_API_KEY` valid (for intent classification and topic slot-filling)

---

## Credentials Required

| Env Var | Required? | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Yes | TTS: `audio.speech.create(model="tts-1", voice="alloy")` + ASR: `audio.transcriptions.create(model="whisper-1")` |
| `ANTHROPIC_API_KEY` | Yes | Intent classification + topic slot-filling via `claude-sonnet-4-6` |
| `SECURE_BASE_URL` | No | Appended to booking code in BOOKED script: `{SECURE_BASE_URL}/complete/{code}` |

---

## Tools & Libraries

| Package | Version | Purpose | Notes |
|---|---|---|---|
| `openai` | >=1.50.0 | TTS (`audio.speech.create`) + ASR (`audio.transcriptions.create`) | Already in `requirements.txt` |
| `anthropic` | >=0.40.0 | Intent + slot-filling via `claude-sonnet-4-6` | Already in `requirements.txt` |
| `streamlit` | >=1.40.0 | `st.audio(bytes, format="audio/mp3", autoplay=True)` — browser audio playback | Already in `requirements.txt` |
| `json` | stdlib | Load `data/mock_calendar.json` slot list | No install |
| `random`, `string` | stdlib | `generate_booking_code()` implementation | No install |
| `uuid` | stdlib | `action_id` field in MCP queue entries | No install |
| `datetime` | stdlib | `booking_detail["date"]`, MCP `created_at` field | No install |
| `re` | stdlib | Safety refusal pattern check, booking code format assertion | No install |

---

## Inputs

| Input | Where It Comes From |
|---|---|
| `session["top_theme"]` | Written by Phase 3 `theme_clusterer.py` |
| `data/mock_calendar.json` | Static file in repo — 8 pre-defined advisor slots |
| User utterance | Text from `st.text_input()` OR transcription from `st.audio_input()` via Whisper |

---

## Step-by-Step Build Order

**1. `pillar_b/intent_classifier.py`**
Function: `classify(utterance: str) -> str`
- Keyword-based first (no API call):
  ```python
  if "book" in utt or "schedule" in utt:   return "book_new"
  if "reschedule" in utt or "move" in utt: return "reschedule"
  if "cancel" in utt:                       return "cancel"
  if "prepare" in utt or "bring" in utt:   return "what_to_prepare"
  if "available" in utt or "when" in utt:  return "check_availability"
  ```
- LLM fallback if no keyword matches:
  ```python
  # Send to claude-sonnet-4-6 with 1-shot prompt
  # "Classify this utterance into one of: book_new | reschedule | cancel | what_to_prepare | check_availability"
  ```
- Returns one of the 5 intent strings

**2. `pillar_b/slot_filler.py`**
Function: `extract_topic(utterance: str) -> str`
- Send utterance to `claude-sonnet-4-6`:
  ```
  Map this text to one of these topics:
  KYC / Onboarding | SIP / Mandates | Statements / Tax Documents |
  Withdrawals & Timelines | Account Changes / Nominee
  Reply with the exact topic string only.
  ```
- Return the matched topic string

Function: `extract_time_pref(utterance: str) -> dict`
- Regex-based: extract weekday name (Monday–Sunday) and period (AM/PM/morning/afternoon)
  ```python
  WEEKDAYS = r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
  PERIODS  = r"(morning|afternoon|am|pm)"
  ```
- Return `{"day": str | None, "period": str | None}`

**3. `pillar_b/booking_engine.py`**
Function: `generate_booking_code(prefix="NL") -> str`
- As defined above; asserts format before returning

Function: `match_slots(calendar: list[dict], day_pref: str | None, period: str | None) -> list[dict]`
- Load `mock_calendar.json` if not already loaded
- Filter slots where `slot["day"].lower() == day_pref` and `slot["period"].lower() == period`
- Return up to 2 matching slots; return `[]` if no match (triggers WAITLIST)

Function: `book(slot: dict, topic: str, session: dict) -> dict`
- Generate booking code
- Write to session: `booking_code`, `booking_detail`
- Call `enqueue_action()` x4: calendar_hold, notes_append (with M2 context: top_3_themes, weekly_pulse[:300], fee_scenario), email_draft, sheet_entry
- Return `{"booking_code": str, "slot": dict, "topic": str, "secure_url": str}`

**4. `pillar_b/voice_agent.py`**
Class: `VoiceAgent`
- `__init__(session, calendar_path)`: load calendar, init state to "GREET", init openai client
- `get_greeting() -> tuple[str, bytes]`: read `top_theme`; format greeting; TTS call; return (text, audio)
- `step(utterance) -> tuple[str, bytes | None]`: FSM dispatch; call appropriate handler for current state; advance state; TTS call on response; return (text, audio or None)
- Internal state handlers: `_handle_greet()`, `_handle_intent()`, `_handle_topic()`, `_handle_timepref()`, `_handle_offerslots()`, `_handle_confirm()`, `_handle_booked()`, `_handle_waitlist()`

---

## Outputs & Downstream Dependencies

| Session Key Written | Value | Consumed By | Risk if Missing |
|---|---|---|---|
| `session["booking_code"]` | `NL-A742` format string | Phase 7 notes payload + email subject + secure link | Notes entry incomplete; email subject has no code |
| `session["booking_detail"]` | `{topic, slot, date, time, IST}` dict | Phase 7 email builder | Email has no booking summary section |
| `session["call_completed"]` | `True` | Phase 9 Tab 2 UI (shows confirmation) | Confirmation banner not shown after booking |
| `session["mcp_queue"]` | +4 pending actions added (calendar_hold, notes_append, email_draft, sheet_entry) | Phase 7 HITL panel | Approval center shows 4 fewer items |

---

## Error Cases

**`top_theme` is None at GREET:**
Use a fallback generic greeting: *"Hello! I'm the INDMoney appointment assistant. I can help you book a call with a financial advisor."* Do not crash. The greeting just won't mention a theme — this fails the UX eval "theme mention" check, but the booking flow itself still works.

**OpenAI TTS fails (rate limit or network error):**
Retry once after 1 second. If it fails again, return the text response with `audio=None`. The UI should still display the text. Log: `WARNING: TTS call failed — returning text-only response.`

**No calendar slots match user's time preference:**
Transition to WAITLIST state. Generate a `WL-` prefix code. Enqueue 2 actions (waitlist_hold + waitlist_email). Tell the user: *"No slots are currently available for that time. I've added you to the waitlist with code {code}."*

**User says investment advice query during call:**
`safety_refusal()` checks every utterance at the start of INTENT state processing. If triggered, deliver the refusal text via TTS, then return to INTENT state (not END). The booking flow can continue after a refusal.

**Booking code format fails assertion:**
```python
assert re.match(r"^(NL|WL)-[A-Z]\d{3}$", code), f"Invalid format: {code}"
```
This should never happen in normal operation (the generation logic is deterministic), but the assertion catches any edge case before a malformed code enters session state.

---

## Phase Gate

```bash
pytest phase4_voice_agent/tests/test_voice_agent.py -v
# Expected: all tests pass
# Tests: booking code format, GREET reads top_theme,
#        fallback generic greeting when top_theme=None,
#        WAITLIST triggered on no slot match,
#        safety_refusal returns string on advice query,
#        4 MCP actions queued on BOOKED (calendar_hold, notes_append, email_draft, sheet_entry)

python phase4_voice_pillar_b/evals/eval_voice.py
# Expected:
#   Booking code format (NL-[A-Z]\d{3}): ✓
#   MCP actions queued on BOOKED: 4       ✓  (calendar_hold, notes_append, email_draft, sheet_entry)
#   Top theme appears in greeting: ✓
#   Notes payload contains M2 context (top_3_themes, weekly_pulse): ✓
```
