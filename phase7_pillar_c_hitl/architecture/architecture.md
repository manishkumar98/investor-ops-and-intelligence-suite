# Phase 7 Architecture — Pillar C: HITL MCP Approval Center (v3.0 As-Built)

## What This Phase Does

Phase 7 is the Human-in-the-Loop (HITL) approval center — the gatekeeper that prevents any AI-generated action from reaching the outside world without explicit human sign-off.

When the M3 voice agent completes a booking, it invokes the **MCP Super-Agent** (`super_agent.py`): Claude receives the full booking context plus M2 market intelligence (`weekly_pulse`, `top_3_themes`, `fee_bullets`) and calls all 4 post-booking tools via **Model Context Protocol tool_use**. Claude constructs every payload — including writing the advisor email with a Market Context section derived from the M2 pulse pipeline. The resulting tool_use blocks land in `session["mcp_queue"]` as **4 pending actions**:

- `calendar_hold` — reserve the advisor's slot
- `notes_append` — log booking to advisor notes (enriched with M2 market context)
- `email_draft` — pre-booking email written by Claude with M2 pulse + fee bullets
- `sheet_entry` — record booking in Google Sheet

> **As-built (v3.0):** Actions are no longer hard-coded in `voice_agent.py`. Claude (`claude-sonnet-4-6`) acts as the super-agent via `tool_choice="any"`, constructing all 4 payloads through MCP tool_use. Each action is tagged `"agent": "claude-sonnet-4-6"` and shown with a 🤖 Claude MCP badge in the HITL panel. A legacy hard-coded fallback runs automatically if the Claude API is unavailable.

Each action sits in `session["mcp_queue"]` waiting for a human to click "Approve" or "Reject". Phase 7 renders this queue as a Streamlit UI panel, executes approved actions through an MCP client, and persists the approval state to `data/mcp_state.json`.

**Why is this phase architecturally critical?** In a financial services context, the company is responsible for every outbound communication. The HITL gate ensures:
1. A human reads the AI-generated content before it leaves the system
2. The booking code, M2 pulse excerpt, and fee context are all present and correct
3. If anything looks wrong, the action can be rejected without consequences

---

## MCP Super-Agent Flow

```
Voice call ends → _complete_booking() in voice_agent.py
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  super_agent.run(booking_detail, session)              │
│                                                        │
│  Calls Claude API (claude-sonnet-4-6):                 │
│    system: "You are a booking super-agent..."          │
│    tools:  [calendar_hold, notes_append,               │
│             email_draft, sheet_entry]                  │
│    tool_choice: {"type": "any"}   ← forces tool use   │
│    user:   booking context + M2 weekly_pulse           │
│             + top_3_themes + fee_bullets               │
│                                                        │
│  Claude returns tool_use blocks:                       │
│    • calendar_hold(title, date, time, booking_code)    │
│    • notes_append(doc_title, entry{+M2 context})       │
│    • email_draft(subject, body WITH market context)    │
│    • sheet_entry(booking_code, topic_key, date...)     │
│                                                        │
│  Each block → action dict with agent="claude-sonnet-4-6"
│  → appended to session["mcp_queue"]                    │
└────────────────────────────────────────────────────────┘
         │
         ▼
session["mcp_queue"]  ← 4 pending Claude-generated actions
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  hitl_panel.py  (Streamlit Tab 3 component)            │
│                                                        │
│  🤖 MCP Super-Agent active banner (if agent actions)   │
│  "Clear N completed" button                            │
│                                                        │
│  Actions grouped: 📋 Booking Actions (m3_voice)        │
│    Each card shows 🤖 Claude MCP badge + model name    │
│                                                        │
│  for action in mcp_queue:                              │
│    render card for action["type"]:                     │
│      calendar_hold  → date/time/topic/code             │
│      notes_append   → connected view (booking+pulse)   │
│      email_draft    → subject + full body preview      │
│      sheet_entry    → booking_code/topic/date/status   │
│    col1: [✓ Approve]  col2: [✗ Reject]                │
│                                                        │
│  On Approve → mcp_client.execute(action) → Google API  │
│  On Reject  → action["status"] = "rejected"            │
│  Both → persist to data/mcp_state.json                 │
└────────────────────────────────────────────────────────┘
```

---

## Email Content (as-built)

```
Subject:  "Advisor Pre-Booking: {topic} — {date}"
Body:
  Dear Advisor,
  ─────────────────────────────────────────
  Booking Summary:
    Booking Code: NL-A742
    Topic: SIP / Mandates
    Slot: Thursday 11:00 AM IST
    Date: 2026-04-24
  ─────────────────────────────────────────
  📊 Market Context (first 100 words of pulse):
    "[This week, users are most concerned about...]"
  ─────────────────────────────────────────
  📋 Fee Context:
    • Exit load for SBI ELSS is 1% if redeemed before 1 year
    • After 1 year, no exit load applies
    Source: https://www.sbimf.com/fees
  ─────────────────────────────────────────
  ⚠ No investment advice implied.
  Complete your booking: {SECURE_BASE_URL}/complete/NL-A742

  Best regards,
  INDMoney Advisor Suite
  Auto-generated — do not reply
```

---

## Key Interfaces

```python
# phase7_pillar_c_hitl/super_agent.py  ← NEW: MCP super-agent

TOOLS: list[dict]   # 4 Claude tool_use schemas: calendar_hold, notes_append,
                    # email_draft, sheet_entry

def run(booking_detail: dict, session: dict) -> list[dict]:
    """
    Invokes claude-sonnet-4-6 with tool_choice="any" and the 4 MCP tool schemas.
    Claude receives booking context + M2 weekly_pulse/top_3_themes/fee_bullets
    and constructs all payloads via tool_use (Model Context Protocol).

    Returns list of action dicts tagged with agent="claude-sonnet-4-6",
    ready for session["mcp_queue"]. Returns [] on failure (triggers legacy fallback).
    """

# phase7_pillar_c_hitl/mcp_client.py

def enqueue_action(session: dict, type: str, payload: dict, source: str) -> str:
    """
    Legacy helper — still used by the waitlist path and as the super-agent fallback.
    Supersedes any existing PENDING action of same type+source (deduplication).
    type: "calendar_hold" | "notes_append" | "email_draft" | "sheet_entry"
    """

# action dict schema (as stored in mcp_queue):
{
    "action_id":  str,   # UUID
    "type":       str,   # calendar_hold | notes_append | email_draft | sheet_entry
    "status":     str,   # pending | approved | rejected | error
    "created_at": str,   # UTC ISO timestamp
    "source":     str,   # m3_voice
    "agent":      str,   # "claude-sonnet-4-6" if MCP super-agent generated it (else absent)
    "payload":    dict,  # tool-specific fields
}
```

---

## MCP Action Types & Payloads (4 types)

| Type | Payload Fields | Who Enqueues It |
|---|---|---|
| `calendar_hold` | `{title, date, time, tz: "IST", topic, booking_code}` | `voice_agent.py` on BOOKED |
| `notes_append` | `{doc_title, booking_code, topic_label, slot, date, top_3_themes, weekly_pulse, fee_scenario}` | `voice_agent.py` on BOOKED |
| `email_draft` | `{subject, body}` (assembled inline in `voice_agent.py`) | `voice_agent.py` on BOOKED |
| `sheet_entry` | `{booking_code, topic_key, topic_label, slot_start_ist, date, status, call_id}` | `voice_agent.py` on BOOKED |

**Calendar hold title format:**
```
"Advisor Q&A — {topic} — {booking_code}"
```

**Notes entry payload (connected view — includes M2 context):**
```json
{
  "doc_title":    "Advisor Pre-Bookings",
  "booking_code": "NL-A742",
  "topic_label":  "SIP / Mandates",
  "slot":         "Thursday 11:00 AM IST",
  "date":         "2026-04-24",
  "top_3_themes": ["Nominee Updates", "SIP Failures", "Fee Transparency"],
  "weekly_pulse": "This week users raised concerns about...",
  "fee_scenario": "Exit load: 1% if redeemed within 1 year"
}
```

---

## Key Interfaces

```python
# phase7_pillar_c_hitl/mcp_client.py

from dataclasses import dataclass

@dataclass
class MCPResult:
    success: bool
    ref_id:  str    # mock: UUID string; live: server-returned reference ID
    mode:    str    # "mock" | "live"

class MCPClient:
    def __init__(self, mode: str = "mock"):
        self.mode = mode
        self._mock_store = {}

    def execute(self, action: dict) -> MCPResult:
        """
        mock mode: writes to self._mock_store, returns mock MCPResult (no HTTP calls)
        live mode:
          email_draft    → SMTP via Gmail (smtplib, mcp/config.py credentials)
          notes_append   → Google Docs (mcp/docs_tool.append_notes_sync)
          sheet_entry    → Google Sheets (_append_row_sync from mcp/sheets_tool.py)
          calendar_hold  → acknowledged only (background dispatch handled it at booking time)
        """

# phase7_pillar_c_hitl/hitl_panel.py

def render(session: dict, mcp_client: MCPClient) -> None:
    """
    Renders the full HITL approval panel.
    - Shows "Clear N completed" button at top when N > 0
    - Groups actions under "📋 Booking Actions" (source: m3_voice)
    - Renders type-specific cards for each action
    - Notes card: shows connected view (booking + M2 context) when both present
    - Persists queue to data/mcp_state.json on every approve/reject
    """
```

---

## MCPClient Live Mode (as-built)

In live mode, each action type routes to a specific external service:

```python
# email_draft → Gmail SMTP
from mcp.config import config   # GMAIL_ADDRESS, GMAIL_APP_PASSWORD, ADVISOR_EMAIL
msg = MIMEMultipart("alternative")
msg["From"] = f"AdvisorBot <{config.gmail_address}>"
msg["To"] = config.advisor_email
with smtplib.SMTP(config.gmail_smtp_host, config.gmail_smtp_port) as smtp:
    smtp.ehlo(); smtp.starttls()
    smtp.login(config.gmail_address, config.gmail_app_password)
    smtp.sendmail(config.gmail_address, config.advisor_email, msg.as_bytes())

# notes_append → Google Docs
from mcp.docs_tool import append_notes_sync
append_notes_sync(action["payload"])

# sheet_entry → Google Sheets
from mcp.sheets_tool import _append_row_sync
from mcp.models import MCPPayload
mcp_payload = MCPPayload(booking_code=..., topic_label=..., slot_start_ist=..., ...)
_append_row_sync(mcp_payload, event_id=None)

# calendar_hold → acknowledged (background thread at booking time already created the event)
```

---

## State Persistence

`mcp_state.json` ensures that approval decisions survive a Streamlit page reload.

**On every approve or reject:**
```python
def save_state(session: dict) -> None:
    MCP_STATE_PATH.write_text(json.dumps(session.get("mcp_queue", []), indent=2))
```

**On app startup:** If `session["mcp_queue"]` is empty, reload from `data/mcp_state.json`.

**"Clear N completed" button:**
```python
session["mcp_queue"] = [a for a in queue if a["status"] == "pending"]
_persist(session)
st.rerun()
```

---

## Prerequisites

- Phase 1 complete: `config.py`, session state, `MCP_MODE` available
- Phase 3 complete: `weekly_pulse`, `fee_bullets`, `fee_sources` in session
- Phase 4 complete: `booking_code`, `booking_detail` in session; 4 actions in `mcp_queue`
- Live mode only: `mcp/config.py` with GMAIL_ADDRESS, GMAIL_APP_PASSWORD, ADVISOR_EMAIL, Google API credentials

---

## Credentials Required

| Env Var | Required? | Purpose |
|---|---|---|
| `MCP_MODE` | No | `mock` (default) or `live` |
| `MCP_SERVER_URL` | No | Legacy; live mode now uses direct service calls (SMTP, Google APIs) |
| `GMAIL_ADDRESS` | live only | From address for advisor email |
| `GMAIL_APP_PASSWORD` | live only | Gmail app password for SMTP auth |
| `ADVISOR_EMAIL` | live only | Recipient advisor email address |
| Google OAuth credentials | live only | For Docs + Sheets API calls via `mcp/config.py` |

**For demo: `MCP_MODE=mock`** — zero external dependencies.

---

## Tools & Libraries

| Package | Purpose |
|---|---|
| `smtplib` | Gmail SMTP for live email_draft |
| `email.mime` | Build MIME email message |
| `uuid` | `action_id` generation |
| `json` | `mcp_state.json` read/write |
| `datetime` | `created_at` in action dict |
| `streamlit` | UI panel rendering |
| `pathlib` | `Path("data/mcp_state.json")` |
| `gspread` | Google Sheets in live mode (via `mcp/sheets_tool.py`) |

---

## Phase Gate

```bash
pytest phase7_pillar_c_hitl/tests/ -v
# Tests: enqueue_action() creates correct dict,
#        deduplication supersedes pending action of same type+source,
#        build_email() has "Dear Advisor," greeting,
#        MCPClient mock execute() returns MCPResult,
#        approve sets status="approved",
#        reject sets status="rejected",
#        sheet_entry renders correctly,
#        mcp_state.json written correctly
```
