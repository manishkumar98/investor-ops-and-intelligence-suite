# Phase 7 Architecture — Pillar C: HITL MCP Approval Center

## What This Phase Does

Phase 7 is the Human-in-the-Loop (HITL) approval center — the gatekeeper that prevents any AI-generated action from reaching the outside world without explicit human sign-off.

By the time the user reaches Tab 3, the system has already:
- Run the review pipeline (Phase 3), which queued a notes entry and an email draft
- Completed a voice booking (Phase 4), which queued a calendar hold, another notes entry, and the final advisor email

That's up to 5 pending actions sitting in `session["mcp_queue"]`, each waiting for a human to click "Approve" or "Reject". Phase 7 renders this queue as a Streamlit UI panel, executes approved actions through an MCP client, and persists the approval state to `data/mcp_state.json` so it survives page reloads.

**Why is this phase architecturally critical?**

In a financial services context, the company is responsible for every outbound communication. An AI that automatically sends emails or creates calendar events is a compliance liability. The HITL gate ensures:
1. A human reads the AI-generated content before it leaves the system
2. The booking code, pulse excerpt, and fee context are all present and correct
3. If anything looks wrong, the action can be rejected without consequences

**Mock vs Live MCP:** In the demo (`MCP_MODE=mock`), approving an action writes to an in-memory Python dict and saves `mcp_state.json` — no HTTP calls, no external accounts needed. Setting `MCP_MODE=live` switches to real HTTP POSTs to a running MCP server (e.g., a Google Workspace MCP server). The interface is identical in both modes.

---

## Approval Flow

```
session["mcp_queue"]  ← list of pending actions
  (populated by Phase 3 and Phase 4)
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  hitl_panel.py  (Streamlit Tab 3 component)            │
│                                                        │
│  for action in mcp_queue:                              │
│    if action["status"] == "pending":                   │
│      st.expander(f"{action['type']} — {summary}")     │
│        show payload preview (JSON, formatted)          │
│        col1, col2 = st.columns(2)                     │
│        col1: [✓ Approve]  col2: [✗ Reject]            │
│                                                        │
│  On Approve click:                                     │
│    action["status"] = "approved"                       │
│    result = mcp_client.execute(action)                 │
│    show ✓ badge + result.ref_id                        │
│    persist queue to data/mcp_state.json                │
│                                                        │
│  On Reject click:                                      │
│    action["status"] = "rejected"                       │
│    show ✗ badge                                        │
│    persist queue to data/mcp_state.json                │
└────────────────────┬───────────────────────────────────┘
                     │ On Approve
                     ▼
┌────────────────────────────────────────────────────────┐
│  MCPClient.execute(action)                             │
│                                                        │
│  mode = "mock"                    mode = "live"        │
│       │                                │               │
│       ▼                                ▼               │
│  _mock_store dict              POST MCP_SERVER_URL     │
│  write action to dict          /calendar/hold          │
│  no HTTP calls made            /docs/append            │
│  returns mock ref_id           /gmail/draft            │
│                                                        │
│  Both return MCPResult:                                │
│  {success: bool, ref_id: str, mode: str}               │
└────────────────────────────────────────────────────────┘
```

---

## Email Builder Composition

The advisor email is assembled from multiple session keys. All 5 keys must be present — if any is `None`, `build_email()` raises a `ValueError` rather than silently building an incomplete email.

```
Required session inputs:
  booking_detail  → subject line + booking summary block
  booking_code    → secure link suffix + subject line
  weekly_pulse    → first 100 words as "Market Context"
  fee_bullets     → formatted as a bullet list
  fee_sources     → source URLs listed after bullets

Email structure:
  Subject:  "Advisor Pre-Booking: {topic} — {date}"
  Body:
    Hi [Advisor Name],
    ─────────────────────────────────────────
    Booking Summary:
      Code: NL-A742
      Topic: SIP / Mandates
      Slot: Thursday 11:00 AM IST
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
```

---

## The `enqueue_action()` Helper

This function is the ONLY way to add items to `mcp_queue`. It is defined once in `pillar_c/mcp_client.py` and imported by both `pipeline_orchestrator.py` (Phase 3) and `voice_agent.py` (Phase 4). No module should ever construct an action dict inline.

```python
# pillar_c/mcp_client.py
def enqueue_action(session: dict, type: str, payload: dict, source: str) -> str:
    """
    Appends a standardised pending action to session["mcp_queue"].
    Returns the unique action_id for reference.

    type:   "calendar_hold" | "notes_append" | "email_draft"
    source: "m2_pipeline" | "m3_voice"
    """
    action = {
        "action_id":  str(uuid.uuid4()),
        "type":       type,
        "status":     "pending",           # pending → approved | rejected
        "created_at": datetime.utcnow().isoformat(),
        "source":     source,
        "payload":    payload,
    }
    session["mcp_queue"].append(action)
    return action["action_id"]
```

---

## MCP Action Types & Payloads

Three action types are used. Each has a specific payload schema.

| Type | Payload Fields | Who Enqueues It |
|---|---|---|
| `calendar_hold` | `{title, date, time, tz: "IST", topic, booking_code}` | `voice_agent.py` on BOOKED |
| `notes_append` | `{doc_title: "Advisor Pre-Bookings", entry: {date, topic, slot, booking_code}}` | `pipeline_orchestrator.py` and `voice_agent.py` |
| `email_draft` | `{subject, body}` (assembled by `email_builder.py`) | `pipeline_orchestrator.py` and `voice_agent.py` |

**Calendar hold title format:**
```
"Advisor Q&A — {topic} — {booking_code}"
# Example: "Advisor Q&A — SIP / Mandates — NL-A742"
```

**Notes entry format:**
```json
{
  "doc_title": "Advisor Pre-Bookings",
  "entry": {
    "date":         "2026-04-24",
    "topic":        "SIP / Mandates",
    "slot":         "Thursday 11:00 AM IST",
    "booking_code": "NL-A742"
  }
}
```

---

## Key Interfaces

```python
# pillar_c/mcp_client.py

from dataclasses import dataclass

@dataclass
class MCPResult:
    success: bool
    ref_id:  str    # mock: UUID string; live: server-returned reference ID
    mode:    str    # "mock" | "live"

class MCPClient:
    def __init__(self, mode: str = "mock"):
        self.mode = mode
        self._mock_store = {}   # in-memory store for mock mode

    def execute(self, action: dict) -> MCPResult:
        """
        Executes an approved action.
        mock mode: writes to self._mock_store, returns mock MCPResult
        live mode: POST to MCP_SERVER_URL/{action_type_endpoint}
        """

# pillar_c/email_builder.py

def build_email(session: dict) -> dict:
    """
    Assembles the advisor email from session state.
    Returns: {"subject": str, "body": str}
    Raises: ValueError if any of the 5 required keys is None
    """

# pillar_c/hitl_panel.py

def render(session: dict, mcp_client: MCPClient) -> None:
    """
    Renders the full HITL approval panel as a Streamlit component.
    Called inside app.py Tab 3.
    Writes approved/rejected status back to session["mcp_queue"].
    Persists to data/mcp_state.json on every approve/reject.
    """
```

---

## State Persistence

`mcp_state.json` ensures that approval decisions survive a Streamlit page reload or app restart.

**On every approve or reject:**
```python
state_file = Path("data/mcp_state.json")
state_file.write_text(json.dumps(session["mcp_queue"], indent=2))
```

**On app startup (in `app.py`, after `init_session_state`):**
```python
if not st.session_state["mcp_queue"]:
    state_file = Path("data/mcp_state.json")
    if state_file.exists():
        try:
            st.session_state["mcp_queue"] = json.loads(state_file.read_text())
        except json.JSONDecodeError:
            pass  # start with empty queue; log warning
```

This means if a user approves 3 actions and reloads the page, those 3 will still show as "approved" in Tab 3.

---

## Prerequisites

- Phase 1 complete: `config.py`, session state, `MCP_MODE` and `MCP_SERVER_URL` available
- Phase 3 complete: `weekly_pulse`, `fee_bullets`, `fee_sources` in session (needed by email builder)
- Phase 4 complete: `booking_code`, `booking_detail` in session (needed by email builder + notes)
- `session["mcp_queue"]` must have items from Phase 3 and/or Phase 4 for the panel to show anything

---

## Credentials Required

| Env Var | Required? | Purpose |
|---|---|---|
| `MCP_MODE` | No | `mock` (default, no HTTP calls) or `live` (HTTP POSTs to real MCP server) |
| `MCP_SERVER_URL` | Only if `MCP_MODE=live` | Base URL: `http://localhost:3000` or hosted server URL |

**For demo: `MCP_MODE=mock`** — zero external dependencies. Everything executes in-memory.

---

## Tools & Libraries

| Package | Version | Purpose | Notes |
|---|---|---|---|
| `httpx` | >=0.27.0 | `httpx.post(url, json=payload)` for live MCP calls | Only used if `MCP_MODE=live` |
| `uuid` | stdlib | `str(uuid.uuid4())` for `action_id` generation | No install |
| `json` | stdlib | `mcp_state.json` read/write | No install |
| `datetime` | stdlib | `created_at` in action dict | No install |
| `streamlit` | >=1.40.0 | `st.expander()`, `st.columns()`, `st.button()`, `st.success()`, `st.error()` | Already in `requirements.txt` |
| `pathlib` | stdlib | `Path("data/mcp_state.json")` — platform-safe path | No install |

---

## Inputs

| Input | Source |
|---|---|
| `session["mcp_queue"]` | Populated by `enqueue_action()` calls from Phase 3 and Phase 4 |
| `session["booking_detail"]` | Written by Phase 4 `booking_engine.py` |
| `session["booking_code"]` | Written by Phase 4 `booking_engine.py` |
| `session["weekly_pulse"]` | Written by Phase 3 `pulse_writer.py` |
| `session["fee_bullets"]` + `fee_sources` | Written by Phase 3 `fee_explainer.py` |
| `data/mcp_state.json` | Loaded on app startup to restore previous approval state |

---

## Step-by-Step Build Order

**1. `pillar_c/mcp_client.py`**
- Define `MCPResult` dataclass
- Define `enqueue_action(session, type, payload, source) -> str` as a module-level function
- Implement `MCPClient` class:
  - `__init__(mode="mock")`: store mode, init `_mock_store = {}`
  - `execute(action)`:
    - mock mode: `self._mock_store[action["action_id"]] = action`; return `MCPResult(success=True, ref_id=str(uuid.uuid4()), mode="mock")`
    - live mode: `httpx.post(f"{MCP_SERVER_URL}/{endpoint}", json=action["payload"], timeout=10)`; return based on response

**2. `pillar_c/email_builder.py`**
Function: `build_email(session: dict) -> dict`
- Validate all 5 required keys are non-None:
  ```python
  required = ["booking_detail", "booking_code", "weekly_pulse", "fee_bullets", "fee_sources"]
  for key in required:
      if not session.get(key):
          raise ValueError(f"build_email: missing required session key: '{key}'")
  ```
- Build subject: `f"Advisor Pre-Booking: {topic} — {today}"`
- Build body as a multi-line string with all sections
- Return `{"subject": subject, "body": body}`

**3. `pillar_c/hitl_panel.py`**
Function: `render(session: dict, mcp_client: MCPClient) -> None`
- If `mcp_queue` is empty: `st.info("No pending actions. Run the Review Pipeline or complete a Voice Call first.")`
- For each action in queue:
  - Display with `st.expander(f"[{action['status'].upper()}] {action['type']} — {action['source']}")`
  - Inside expander: show formatted payload preview with `st.json(action["payload"])`
  - If `status == "pending"`: show Approve/Reject buttons in two columns
  - On Approve click: set `status = "approved"`, call `mcp_client.execute(action)`, show `st.success(f"✓ Executed — ref: {result.ref_id}")`
  - On Reject click: set `status = "rejected"`, show `st.error("✗ Action rejected")`
  - After any click: write to `mcp_state.json`

---

## Outputs & Downstream Dependencies

| Output | Consumed By | Purpose |
|---|---|---|
| `data/mcp_state.json` | `app.py` startup reload | Persist approval state across page reloads |
| Approved entries in `_mock_store` | Demo show-off | Demonstrates mock "execution" with ref IDs |
| `hitl_panel.render()` | Phase 9 `app.py` Tab 3 | The actual UI component shown to the user |
| `build_email()` | Called from `pipeline_orchestrator.py` to build the `email_draft` payload | Produces the email body that appears in the approval panel |

---

## Error Cases

**`build_email()` called with missing session keys:**
Raise `ValueError("build_email: missing required session key: '{key}'")`
Never silently produce a partial email. A corrupt email reaching the approval panel would pass the HITL check and could be sent to an advisor with missing sections.

**`httpx.post` fails in live mode (network error, server down):**
```python
try:
    response = httpx.post(url, json=payload, timeout=10)
    response.raise_for_status()
except httpx.RequestError as e:
    action["status"] = "error"
    action["error_msg"] = str(e)
    return MCPResult(success=False, ref_id="", mode="live")
```
Show `st.error(f"MCP call failed: {action['error_msg']}")` in the panel. Do not crash the UI.

**`data/mcp_state.json` is corrupted or malformed:**
```python
try:
    queue = json.loads(state_file.read_text())
except json.JSONDecodeError:
    warnings.warn("mcp_state.json is corrupted. Starting with empty queue.")
    queue = []
```
Start with an empty queue rather than crashing on startup.

**Duplicate approve click (Streamlit reruns on every interaction):**
Check `if action["status"] != "pending": return` at the start of the Approve handler. Idempotent — clicking Approve twice does not execute the action twice.

---

## Phase Gate

```bash
pytest phase7_pillar_c_hitl/tests/test_hitl.py -v
# Expected: all tests pass
# Tests: enqueue_action() creates correct dict structure,
#        build_email() raises ValueError on missing keys,
#        MCPClient mock execute() returns MCPResult,
#        approve sets status="approved",
#        reject sets status="rejected",
#        mcp_state.json written correctly

python phase7_pillar_c_hitl/evals/eval_hitl.py
# Expected:
#   booking_code appears in notes_append payload: ✓
#   weekly_pulse excerpt appears in email body:    ✓
#   mock execute() returns success=True:           ✓
#   mcp_state.json reflects approval:              ✓
```
