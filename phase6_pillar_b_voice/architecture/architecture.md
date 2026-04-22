# Phase 6 Architecture — Pillar B: Theme-Aware Voice Integration

## Integration Diagram

```
                      session (shared)
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
  Phase 3 Review Pipeline      Phase 4 Voice Agent
  review_pipeline.run()        VoiceAgent.__init__()
              │                         │
              │ writes:                 │ reads:
              │  weekly_pulse           │  top_theme
              │  top_theme     ──────►  │  (from session)
              │  pulse_generated        │
              └────────────────────────┘
                           │
              ┌────────────▼────────────┐
              │  UI Guard (Pillar B tab)│
              │                         │
              │  if not pulse_generated:│
              │    disable Start Call   │
              │    show warning         │
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
              │    greeting = template     │
              │      .format(top_theme)    │
              │  else:                     │
              │    greeting = generic      │
              └────────────┬───────────────┘
                           │
                    [call proceeds — Phase 4 FSM]
                           │
                           ▼
              ┌────────────────────────────┐
              │  On BOOKED state:          │
              │  session["call_completed"] │
              │    = True                  │
              │  mcp_queue appended        │
              │    → Pillar C tab refreshes│
              └────────────────────────────┘
```

## Cross-Pillar State Contract

| Key | Written by | Read by | Required before voice call |
|---|---|---|---|
| `weekly_pulse` | Phase 3 pipeline | Phase 7 email builder | Yes (gate) |
| `top_theme` | Phase 3 clusterer | Phase 4 greeting | Yes (gate) |
| `pulse_generated` | Phase 3 pipeline | Phase 6 UI guard | Yes (gate) |
| `booking_code` | Phase 4 confirm | Phase 7 notes + email | Post-call |
| `booking_detail` | Phase 4 confirm | Phase 7 email builder | Post-call |
