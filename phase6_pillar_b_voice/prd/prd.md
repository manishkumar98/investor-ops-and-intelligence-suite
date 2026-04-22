# Phase 6 PRD — Pillar B: Theme-Aware Voice Integration
**Owner:** CPO | **Depends on:** Phase 3 (pulse generated) + Phase 4 (voice agent built)

---

## Goal
Wire `top_theme` from the M2 Review Pipeline into the M3 Voice Agent greeting. The voice agent must not be startable unless a Weekly Pulse has been generated in the current session.

## Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P6-01 | "Start Call" button disabled if `session["pulse_generated"] == False` | Button disabled; tooltip: "Generate a Weekly Pulse first" |
| P6-02 | On call start, agent reads `session["top_theme"]` before composing greeting | Greeting string contains `top_theme` value |
| P6-03 | If `top_theme` is None (pulse ran but top_theme blank), fall back to generic greeting | No KeyError; generic greeting delivered |
| P6-04 | `top_theme` displayed as a badge in the Voice Agent section before call starts | Badge shows "Current Top Theme: {theme}" |
| P6-05 | After call ends, `session["call_completed"]` = True | `session["call_completed"]` is `True` |
| P6-06 | After call ends, Pillar C tab shows pending MCP actions immediately | `mcp_queue` non-empty; Pillar C badge updates |
| P6-07 | State written by Phase 3 pipeline (`weekly_pulse`, `top_theme`) is readable by Phase 4 voice agent in the same session | Both values accessible from shared `session` dict |

## Phase Gate Checklist
- [ ] Start Call blocked when no pulse in session
- [ ] Greeting contains `top_theme` value after pulse generated
- [ ] `session["call_completed"]` is True after booking
- [ ] MCP queue has 3 items after call ends
- [ ] `pytest phase6_pillar_b_voice/tests/ -v` exits 0
