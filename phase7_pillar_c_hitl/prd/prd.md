# Phase 7 PRD — Pillar C: HITL MCP Approval Center
**Owner:** CPO | **Depends on:** Phase 3 (pulse, fee context) + Phase 4 (booking code, booking detail)

---

## Goal
All system-generated actions (calendar hold, notes append, email draft) are displayed in a single Approval Center UI. Nothing executes until a human explicitly clicks Approve. The advisor email body must include `weekly_pulse` context from M2.

## Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P7-01 | Approval Center lists ALL pending items from `mcp_queue` | Every action with `status=="pending"` shown |
| P7-02 | Each action item shows: type, summary, expandable payload preview | Expand reveals full payload JSON |
| P7-03 | Approve button sets `status = "approved"` then calls `mcp_client.execute()` | Status changes before execute called; no auto-execute on load |
| P7-04 | Reject button sets `status = "rejected"`; `execute()` NOT called | Rejected item stays in list with ✗ badge |
| P7-05 | `mcp_client.execute()` in mock mode stores to in-process dict; no HTTP call | `httpx.post` not called in mock mode |
| P7-06 | Notes append payload includes `booking_code` from session | `payload["entry"]["code"]` equals `session["booking_code"]` |
| P7-07 | Email draft body includes `weekly_pulse` snippet (first 100 words) | Pulse text present in email body |
| P7-08 | Email draft body includes `fee_bullets` formatted as list | Fee bullets present in email body |
| P7-09 | Email draft subject format: `"Advisor Pre-Booking: {topic} — {date}"` | Subject matches format |
| P7-10 | Email has compliance footer: "No investment advice implied" | Footer text present |
| P7-11 | `mcp_state.json` written to `data/` after any approve/reject as persistence fallback | File exists after action taken |

## Phase Gate Checklist
- [ ] No auto-execute; all actions start as pending
- [ ] Email body contains `weekly_pulse` snippet
- [ ] Notes payload contains `booking_code`
- [ ] Mock mode makes zero HTTP calls
- [ ] `pytest phase7_pillar_c_hitl/tests/ -v` exits 0
