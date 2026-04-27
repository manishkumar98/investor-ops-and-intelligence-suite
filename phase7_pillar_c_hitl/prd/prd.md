# Phase 7 PRD — Pillar C: HITL MCP Approval Center (v2.0 As-Built)
**Owner:** CPO | **Depends on:** Phase 3 (pulse, fee context) + Phase 4 (booking code, booking detail)

---

## Goal
All system-generated actions (calendar hold, notes append, email draft, Google Sheet entry) are displayed in a single Approval Center UI. Nothing executes until a human explicitly clicks Approve. All 4 actions are produced exclusively by the M3 voice agent at booking time — M2 pipeline enqueues nothing. The notes entry embeds M2 market context to prove cross-pillar integration.

## Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| PC-1.1 | Approval Center lists ALL pending items from `mcp_queue` | Every action with `status=="pending"` shown |
| PC-1.2 | Each action item shows: type, summary, expandable payload preview | Expand reveals full payload JSON |
| PC-1.3 | Approve button sets `status = "approved"` then calls `mcp_client.execute()` | Status changes before execute called; no auto-execute on load |
| PC-1.4 | Reject button sets `status = "rejected"`; `execute()` NOT called | Rejected item stays in list with ✗ badge |
| PC-1.5 | `sheet_entry` action type supported as 4th action type | `mcp_queue` shows sheet entry card with booking_code, topic, date, slot, status, call_id |
| PC-1.6 | `mcp_client.execute()` in mock mode stores to in-process dict; no HTTP call | `httpx.post` not called in mock mode |
| PC-1.7 | Notes append payload includes `booking_code` AND M2 market context (top_3_themes, weekly_pulse, fee_scenario) | `payload["booking_code"]` equals `session["booking_code"]`; `payload["top_3_themes"]` is list |
| PC-1.8 | Email draft body includes `weekly_pulse` excerpt (first 100 words) | Pulse text present in email body |
| PC-1.9 | Email draft body includes `fee_bullets` formatted as list | Fee bullets present in email body |
| PC-1.10 | Email has salutation "Dear Advisor," and compliance footer | Greeting + "No investment advice implied" present |
| PC-1.11 | Email draft subject format: `"Advisor Pre-Booking: {topic} — {date}"` | Subject matches format |
| PC-1.12 | `enqueue_action()` deduplicates: supersedes existing PENDING action of same type+source | Calling enqueue twice for same type+source leaves exactly 1 pending item |
| PC-1.13 | "Clear N completed" button removes all approved/rejected items from queue | Queue has only pending items after click |
| PC-1.14 | Actions grouped by source: `📋 Booking Actions` for M3 voice | Group header visible; M3 actions shown under it |
| PC-1.15 | Notes card renderer shows "connected view" when both booking_code AND pulse context present | Notes card displays booking code + M2 context block together |
| PC-1.16 | `mcp_state.json` written to `data/` after any approve/reject | File exists and reflects current queue state |
| PC-2.1 | Live mode email: SMTP-sends the advisor email via Gmail | `smtplib` sends `msg.as_bytes()` to `config.advisor_email` |
| PC-2.2 | Live mode notes: calls `append_notes_sync()` from `mcp/docs_tool.py` | Google Docs append executed |
| PC-2.3 | Live mode sheet_entry: calls `_append_row_sync()` from `mcp/sheets_tool.py` | Google Sheets row appended |
| PC-2.4 | Live mode calendar_hold: acknowledged only (background dispatch handled it at booking time) | No duplicate calendar event created |

## Phase Gate Checklist
- [ ] All 4 action types render correctly in UI (calendar_hold, notes_append, email_draft, sheet_entry)
- [ ] No auto-execute; all actions start as pending
- [ ] Email body contains `weekly_pulse` snippet AND fee bullets AND "Dear Advisor," greeting
- [ ] Notes payload contains `booking_code` AND M2 context fields
- [ ] Deduplication: second enqueue of same type+source supersedes first
- [ ] "Clear N completed" button works
- [ ] Mock mode makes zero HTTP calls
- [ ] `pytest phase7_pillar_c_hitl/tests/ -v` exits 0
