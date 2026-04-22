# Phase 6 Architecture — Pillar B: Theme-Aware Voice Integration

## What This Phase Does

Phase 6 is the integration layer that wires Phase 3 (the review pipeline) to Phase 4 (the voice agent) through the UI. It does not build any new AI functionality — it is about ensuring the two phases work together correctly inside the Streamlit app, with proper guards and user-visible feedback.

The core integration question is: **how does the voice agent know about this week's top customer theme?** The answer is session state. Phase 3 writes `top_theme` to `st.session_state`. Phase 4's `VoiceAgent` reads `top_theme` from session at the start of every call. Phase 6 is the glue code that ensures the data is there before the call starts, and that the UI makes this relationship visible to the user.

**The UI guard is the most important element here.** The "Start Call" button must be disabled until the weekly pulse has been generated (i.e., until `pulse_generated == True` in session). If the button is always enabled, a developer can click it before uploading a CSV, the voice agent would have no `top_theme`, and the demo's key integration would be silently broken. The guard prevents this.

**What Phase 6 actually builds:**
1. The UI guard logic in Tab 2 that enables/disables the "Start Call" button
2. The voice call loop in Tab 2 that runs the VoiceAgent FSM turn by turn
3. A theme badge that shows the current `top_theme` so users can verify the integration

---

## Integration Diagram

```
                      session (shared)
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
  Phase 3 Review Pipeline      Phase 4 Voice Agent
  pipeline_orchestrator.run()  VoiceAgent.__init__()
              │                         │
              │ writes:                 │ reads at GREET:
              │  weekly_pulse           │  top_theme
              │  top_theme     ──────►  │  (from session)
              │  pulse_generated        │
              └────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │  UI Guard (Tab 2)       │
              │                         │
              │  if not pulse_generated:│
              │    disable Start Call   │
              │    show warning banner  │
              │  else:                  │
              │    show theme badge     │
              │    enable Start Call    │
              └────────────┬────────────┘
                           │ user clicks Start Call
                           ▼
              ┌────────────────────────────┐
              │  VoiceAgent.get_greeting() │
              │                            │
              │  top_theme = session.get(  │
              │    "top_theme", None)      │
              │                            │
              │  if top_theme:             │
              │    greeting includes theme │
              │  else:                     │
              │    generic greeting        │
              └────────────┬───────────────┘
                           │
                    [Phase 4 FSM runs — turn by turn]
                           │
                           ▼
              ┌────────────────────────────┐
              │  On BOOKED state:          │
              │  session["call_completed"] │
              │    = True                  │
              │  mcp_queue now has 5 items │
              │    (2 from M2 + 3 from M3) │
              │  Tab 3 shows all 5         │
              └────────────────────────────┘
```

---

## Cross-Pillar State Contract

This table defines the exact session state contract between Phase 3, Phase 4, and Phase 6.

| Key | Written By | Read By | Required Before Voice Call? | Risk if Absent |
|---|---|---|---|---|
| `weekly_pulse` | `pipeline_orchestrator.py` | Phase 7 email builder | Yes (gate) | Email body has no market context |
| `top_theme` | `theme_clusterer.py` | `voice_agent.py` GREET state | Yes (gate) | Generic greeting — fails UX eval |
| `pulse_generated` | `pipeline_orchestrator.py` | Phase 6 UI guard | Yes (gate) | "Start Call" button always enabled; broken demo |
| `booking_code` | `booking_engine.py` | Phase 7 notes + email | Post-call | Notes entry missing code |
| `booking_detail` | `booking_engine.py` | Phase 7 email builder | Post-call | Email has no booking summary |

---

## UI Guard Implementation

The guard is implemented directly in `app.py` Tab 2. It reads two keys from session state before deciding whether the "Start Call" button should appear.

```python
# In app.py — Tab 2
pulse_ready = st.session_state.get("pulse_generated", False)
top_theme   = st.session_state.get("top_theme", "")

if pulse_ready:
    st.success(f"✓ Pulse generated. Top theme this week: **{top_theme}**")
    start_call = st.button("▶ Start Call", key="start_call_btn")
else:
    st.warning("⚠ Generate a Weekly Pulse first. Upload a reviews CSV above.")
    start_call = False   # button is never rendered when pulse not ready
```

The `st.warning` shows exactly what the user needs to do next, so the gate never feels like a broken state — it's an instructive error.

---

## Voice Call UI Loop

Once "Start Call" is clicked, the app instantiates `VoiceAgent` and runs it turn by turn. Each turn: the agent produces a text+audio response, the audio plays automatically, and the user types (or speaks) their next input.

```python
# In app.py — Tab 2, inside the "if start_call:" block
if "voice_agent" not in st.session_state:
    st.session_state["voice_agent"] = VoiceAgent(
        session=st.session_state,
        calendar_path="data/mock_calendar.json"
    )
    greeting_text, greeting_audio = st.session_state["voice_agent"].get_greeting()
    st.markdown(f"**Agent:** {greeting_text}")
    if greeting_audio:
        st.audio(greeting_audio, format="audio/mp3", autoplay=True)

agent = st.session_state["voice_agent"]

# Track turn number to give each input widget a unique key
if "voice_turn" not in st.session_state:
    st.session_state["voice_turn"] = 0

user_input = st.text_input(
    "Your response:",
    key=f"voice_input_{st.session_state['voice_turn']}"
)

if user_input:
    response_text, response_audio = agent.step(user_input)
    st.markdown(f"**Agent:** {response_text}")
    if response_audio:
        st.audio(response_audio, format="audio/mp3", autoplay=True)
    st.session_state["voice_turn"] += 1

    if agent.state == "BOOKED":
        st.success(f"✓ Appointment booked! Code: **{st.session_state['booking_code']}**")
        st.info("Check the Approval Center tab to review and approve the calendar, notes, and email.")
```

**Why `voice_turn` as the input key suffix?** Streamlit raises an error if two widgets share the same key. Since the user submits multiple turns within a single session, each `st.text_input()` needs a unique key. Incrementing `voice_turn` after each submission creates keys like `voice_input_0`, `voice_input_1`, etc.

---

## Prerequisites

- Phase 3 complete: `run_pipeline()` works and writes `weekly_pulse`, `top_theme`, `pulse_generated` to session
- Phase 4 complete: `VoiceAgent` class is implemented and importable
- Phase 1 complete: Streamlit session state initialised

---

## Credentials Required

None additional for this phase. All credentials are already loaded by the modules from Phase 3 and Phase 4. Phase 6 is purely UI wiring — it calls functions, it doesn't call APIs directly.

---

## Tools & Libraries

| Package | Version | Purpose |
|---|---|---|
| `streamlit` | >=1.40.0 | `st.session_state`, `st.button()`, `st.warning()`, `st.success()`, `st.audio()`, `st.text_input()` |
| No new packages | — | This phase wires existing Phase 3 + Phase 4 code together |

---

## Inputs

| Input | Source |
|---|---|
| `session["pulse_generated"]` | Written by Phase 3 after pipeline completes |
| `session["top_theme"]` | Written by Phase 3 theme clusterer |
| `data/mock_calendar.json` | Static file — passed to `VoiceAgent.__init__()` |
| User text input or audio | Tab 2 UI interactions |

---

## Step-by-Step Build Order

This phase is primarily changes to `app.py`, not new standalone files.

**1. Add UI guard to `app.py` Tab 2**
As shown in the "UI Guard Implementation" section above. This is 10 lines of code. Add it above the "Start Call" button placement.

**2. Add voice call loop to `app.py` Tab 2**
As shown in the "Voice Call UI Loop" section above. Add it inside the `if start_call:` block.

**3. Add theme badge to sidebar**
In the sidebar status panel, show the current top theme with its badge color:
```python
if st.session_state["pulse_generated"]:
    st.info(f"📊 Top theme: **{st.session_state['top_theme']}**")
else:
    st.warning("📊 No pulse generated yet")
```

**4. Phase 6 tests: `phase6_pillar_b_voice/tests/test_voice_integration.py`**
Write tests that verify:
- Guard is active when `pulse_generated = False`
- Guard deactivates when `pulse_generated = True`
- `VoiceAgent.get_greeting()` returns a string containing `top_theme` text
- `VoiceAgent.get_greeting()` returns generic greeting when `top_theme = None`

---

## Outputs & Downstream Dependencies

| Output | Consumed By |
|---|---|
| `session["call_completed"] = True` | Phase 9 Tab 2 — shows booking confirmation banner |
| `session["mcp_queue"]` grows to 3–5 items | Phase 7 HITL panel renders all pending actions |
| Tab 2 renders correctly | Demo scene 2 (voice call sequence) |
| Theme badge in Tab 2 | Demonstrates the M2→M3 integration visually |

---

## Error Cases

**`top_theme` is None after pulse is generated:**
The `VoiceAgent` falls back to a generic greeting (Phase 4 handles this). The UI badge should show: `st.warning("⚠ Top theme not detected. Voice agent will use generic greeting.")`. This should not happen in normal operation but is testable.

**User clicks Start Call before pulse:**
The UI guard prevents this entirely — the button is not rendered. No defensive coding needed in the VoiceAgent for this case; the UI prevents it from happening.

**Voice call abandoned mid-flow (user navigates away or reloads):**
`call_completed` stays `False`. `mcp_queue` may have partial entries (e.g., 2 from M2 pipeline only). Phase 7 HITL panel will still show those 2 as pending — that is correct behaviour. The voice agent object in `session["voice_agent"]` is stale but harmless on reload (session state is cleared on full page reload in Streamlit by default).

**TTS audio fails for one turn:**
Phase 4's `VoiceAgent.step()` returns `audio=None` on TTS failure. The UI loop checks `if response_audio:` before calling `st.audio()`. The text response is still displayed — users can continue the conversation in text mode.

---

## Phase Gate

```bash
pytest phase6_pillar_b_voice/tests/test_voice_integration.py -v
# Expected: all tests pass
# Tests: UI guard enabled when pulse_generated=False,
#        UI guard disabled when pulse_generated=True,
#        theme in greeting, fallback generic greeting on None

python phase6_pillar_b_voice/evals/eval_integration.py
# Expected:
#   Top theme appears in VoiceAgent greeting: ✓
#   UI guard blocks call before pulse:         ✓
#   Post-call: call_completed = True:          ✓
#   Post-call: mcp_queue has ≥3 items:         ✓
```
