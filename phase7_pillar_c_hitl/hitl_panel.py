import json
from pathlib import Path

import streamlit as st

from .mcp_client import MCPClient

MCP_STATE_PATH = Path("data/mcp_state.json")

TYPE_LABELS = {
    "calendar_hold": "📅 Calendar Hold",
    "notes_append":  "📝 Notes / Doc Entry",
    "email_draft":   "✉️ Email Draft",
}


def render(session: dict, mcp_client: MCPClient) -> None:
    """Render the full HITL approval panel inside Streamlit Tab 3."""
    queue = session.get("mcp_queue", [])

    if not queue:
        st.info(
            "No pending actions. "
            "Run the Review Pipeline or complete a Voice Call first."
        )
        return

    pending_count = sum(1 for a in queue if a["status"] == "pending")
    if pending_count > 0:
        st.warning(f"⚠ {pending_count} action(s) awaiting your approval")

    for action in queue:
        label = TYPE_LABELS.get(action["type"], action["type"])
        status = action["status"].upper()
        source = action.get("source", "")

        header = f"[{status}] {label} — {source}"
        with st.expander(header, expanded=(action["status"] == "pending")):
            st.caption(f"Action ID: {action['action_id']}   |   Created: {action['created_at']}")
            st.json(action["payload"])

            if action["status"] == "pending":
                col1, col2 = st.columns(2)
                key_base = action["action_id"][:8]

                with col1:
                    if st.button("✓ Approve", key=f"approve_{key_base}"):
                        action["status"] = "approved"
                        result = mcp_client.execute(action)
                        if result.success:
                            action["ref_id"] = result.ref_id
                            st.success(f"✓ Executed — ref: {result.ref_id} (mode: {result.mode})")
                        else:
                            action["status"] = "error"
                            st.error(f"Execution failed: {action.get('error_msg', 'unknown error')}")
                        _persist(session)
                        st.rerun()

                with col2:
                    if st.button("✗ Reject", key=f"reject_{key_base}"):
                        action["status"] = "rejected"
                        _persist(session)
                        st.rerun()

            elif action["status"] == "approved":
                ref = action.get("ref_id", "")
                st.success(f"✓ Approved — ref: {ref}")

            elif action["status"] == "rejected":
                st.error("✗ Rejected")

            elif action["status"] == "error":
                st.error(f"⚠ Error: {action.get('error_msg', 'unknown')}")


def _persist(session: dict) -> None:
    MCP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MCP_STATE_PATH.write_text(
        json.dumps(session.get("mcp_queue", []), indent=2)
    )
