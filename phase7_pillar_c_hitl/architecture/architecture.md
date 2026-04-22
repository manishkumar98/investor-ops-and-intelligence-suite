# Phase 7 Architecture — Pillar C: HITL MCP Approval Center

## Approval Flow

```
session["mcp_queue"]
  list of pending actions
         │
         ▼
┌────────────────────────────────────────────────────────┐
│  hitl_panel.py  (Streamlit component)                  │
│                                                        │
│  for action in mcp_queue:                              │
│    if action["status"] == "pending":                   │
│      st.expander(f"{action['type']} — {summary}")     │
│        show payload preview (JSON)                     │
│        col1, col2 = st.columns(2)                     │
│        col1: [✓ Approve]  col2: [✗ Reject]            │
│                                                        │
│  On Approve click:                                     │
│    action["status"] = "approved"                       │
│    result = mcp_client.execute(action)                 │
│    show ✓ badge + result.ref_id                        │
│    persist to data/mcp_state.json                      │
│                                                        │
│  On Reject click:                                      │
│    action["status"] = "rejected"                       │
│    show ✗ badge                                        │
│    persist to data/mcp_state.json                      │
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
│  no HTTP calls                 /calendar/hold          │
│                                /docs/append            │
│                                /gmail/draft            │
│                                                        │
│  Returns MCPResult:                                    │
│  {success: bool, ref_id: str, mode: str}               │
└────────────────────────────────────────────────────────┘
```

## Email Builder Composition

```
session inputs:
  booking_detail  → subject, booking summary block
  weekly_pulse    → first 100 words as "Market Context"
  fee_bullets     → formatted as bullet list
  fee_sources     → source URLs
  booking_code    → secure link suffix

Email structure:
  Subject: "Advisor Pre-Booking: {topic} — {date}"
  Body:
    Greeting
    Booking Summary (code, topic, slot, IST)
    ─────────────────────────────────────────
    📊 Market Context (weekly_pulse[:100 words])
    ─────────────────────────────────────────
    📋 Fee Context (fee_bullets)
       Sources: fee_sources
    ─────────────────────────────────────────
    ⚠ No investment advice implied.
    Complete booking: {secure_url}/complete/{code}
```

## Key Interfaces

```python
# pillar_c/mcp_client.py
class MCPResult:
    success: bool
    ref_id:  str
    mode:    str   # "mock" | "live"

class MCPClient:
    def __init__(self, mode: str = "mock"): ...
    def execute(self, action: dict) -> MCPResult: ...

# pillar_c/email_builder.py
def build_email(session: dict) -> dict:
    """
    Returns: {subject: str, body: str}
    Requires: booking_detail, weekly_pulse, fee_bullets, fee_sources
    """

# pillar_c/hitl_panel.py
def render(session: dict, mcp_client: MCPClient) -> None:
    """Renders the Streamlit HITL approval panel."""
```
