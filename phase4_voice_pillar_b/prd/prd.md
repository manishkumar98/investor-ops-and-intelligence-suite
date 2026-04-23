# Phase 4 PRD — Voice Agent (M3)
**Owner:** CPO | **Depends on:** Phase 1 complete (Phase 3 for theme injection in Phase 6)

---

## Goal
Build a compliant voice agent that takes a user from greeting → intent → topic selection → slot offer → booking confirmation, generating a Booking Code and queueing MCP actions at the end.

## Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P4-01 | Greeting delivered on call start; includes mandatory disclaimer | Greeting text contains "informational" and "not investment advice" |
| P4-02 | Five intents handled: `book_new`, `reschedule`, `cancel`, `what_to_prepare`, `check_availability` | Each intent routes to correct handler; unrecognised input asks for clarification |
| P4-03 | Topic slot accepts free-text and maps to one of 5 valid topics | "I want to talk about my SIP" → "SIP / Mandates" |
| P4-04 | Two available slots offered; user selects by number or description | Slot offer script contains "Option 1" and "Option 2" |
| P4-05 | Booking Code generated in format `NL-[A-Z][0-9]{3}` on confirmation | Regex `^NL-[A-Z]\d{3}$` matches generated code |
| P4-06 | Booking Code written to `st.session_state["booking_code"]` | `session["booking_code"]` non-None after BOOKED state |
| P4-07 | Booking detail (date, time, IST, topic, code) written to session state | All 5 fields present in `session["booking_detail"]` |
| P4-08 | If no slot matches preference → WAITLIST state; waitlist code prefix `WL-` | WAITLIST code starts with "WL-" |
| P4-09 | Investment advice question → safety refusal with educational link | Response contains "SEBI" or "advisor" and no fund recommendation |
| P4-10 | No PII collected on call | Transcript text free of phone, email, PAN patterns |
| P4-11 | Calendar hold + Notes append + Email draft enqueued in `mcp_queue` | `mcp_queue` has 3 items with types: `calendar_hold`, `notes_append`, `email_draft` |

## Phase Gate Checklist
- [ ] All 5 intents route correctly
- [ ] Booking Code format matches regex
- [ ] Safety refusal triggers on investment question
- [ ] MCP queue has all 3 action types after booking
- [ ] `pytest phase4_voice_agent/tests/ -v` exits 0
