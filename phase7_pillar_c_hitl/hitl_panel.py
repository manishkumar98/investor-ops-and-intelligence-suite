import json
from pathlib import Path

import streamlit as st

from .mcp_client import MCPClient

MCP_STATE_PATH = Path("data/mcp_state.json")

TYPE_LABELS = {
    "calendar_hold": "📅 Calendar Hold",
    "notes_append":  "📝 Notes / Doc Entry",
    "email_draft":   "✉️ Email Draft",
    "sheet_entry":   "📊 Google Sheet Entry",
}

STATUS_STYLE = {
    "pending":  ("⏳ Pending",  "#E8C96D", "#0A0C14"),
    "approved": ("✓ Approved", "#22C55E", "#0A0C14"),
    "rejected": ("✗ Rejected", "#EF4444", "#FFFFFF"),
    "error":    ("⚠ Error",    "#F97316", "#0A0C14"),
}


def _render_action_card(action: dict) -> None:
    """Render a human-readable card for the action payload."""
    payload = action.get("payload", {})
    atype   = action.get("type", "")

    if atype == "calendar_hold":
        title   = payload.get("title", "—")
        date_v  = payload.get("date", "—")
        time_v  = payload.get("time", "—")
        tz      = payload.get("tz", "IST")
        topic   = payload.get("topic", "—")
        code    = payload.get("booking_code", "—")
        html = f"""
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin:10px 0;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;border-bottom:1px solid var(--border);padding-bottom:10px;">
    <span style="font-size:1.4rem;">📅</span>
    <span style="font-weight:700;color:var(--text-1);font-size:1rem;">{title}</span>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr;gap:8px 16px;font-size:0.875rem;">
    <span style="color:var(--text-3);">Date</span>
    <span style="color:var(--text-1);">{date_v}</span>
    <span style="color:var(--text-3);">Time</span>
    <span style="color:var(--text-1);">{time_v} {tz}</span>
    <span style="color:var(--text-3);">Topic</span>
    <span style="color:#E8C96D;font-weight:600;">{topic}</span>
    <span style="color:var(--text-3);">Booking Code</span>
    <span style="color:var(--text-1);font-family:monospace;letter-spacing:0.05em;">{code}</span>
  </div>
</div>"""
        st.markdown(html, unsafe_allow_html=True)

    elif atype == "notes_append":
        entry      = payload.get("entry", payload)
        doc        = payload.get("doc_title", "Advisor Pre-Bookings")
        date_v     = entry.get("date", "—")
        code       = entry.get("booking_code", "")
        topic      = entry.get("topic", "")
        slot       = entry.get("slot", "")
        status_v   = entry.get("status", "")
        top_themes = entry.get("top_themes") or entry.get("top_3_themes")
        fee_sc     = entry.get("fee_scenario", "")
        pulse      = entry.get("weekly_pulse", "")

        has_booking = bool(code)
        has_pulse   = bool(top_themes or pulse)

        if has_booking and has_pulse:
            # Connected view: M3 booking code + M2 pulse context in one entry
            themes_str = ", ".join(top_themes) if top_themes else "—"
            pulse_snip = (pulse[:250] + "…") if len(pulse) > 250 else (pulse or "—")
            rows_html = (
                f'<span style="color:var(--text-3);">Booking Code</span>'
                f'<span style="color:var(--text-1);font-family:monospace;letter-spacing:0.05em;">{code}</span>'
                f'<span style="color:var(--text-3);">Topic</span>'
                f'<span style="color:#E8C96D;font-weight:600;">{topic or "—"}</span>'
                f'<span style="color:var(--text-3);">Slot</span>'
                f'<span style="color:var(--text-1);">{slot or "—"}</span>'
                f'<span style="color:var(--text-3);">Date</span>'
                f'<span style="color:var(--text-1);">{date_v}</span>'
                f'<span style="color:var(--text-3);">Status</span>'
                f'<span style="color:#22C55E;font-weight:600;">{status_v or "—"}</span>'
                f'<span style="color:var(--text-3);">Top Themes (M2)</span>'
                f'<span style="color:#E8C96D;">{themes_str}</span>'
            )
            if fee_sc:
                rows_html += (
                    f'<span style="color:var(--text-3);">Fee Context</span>'
                    f'<span style="color:var(--text-1);font-size:0.82rem;">{fee_sc}</span>'
                )
            if pulse_snip and pulse_snip != "—":
                rows_html += (
                    f'<span style="color:var(--text-3);align-self:start;">Pulse Snippet</span>'
                    f'<span style="color:var(--text-2);font-size:0.82rem;line-height:1.5;">{pulse_snip}</span>'
                )
        elif has_pulse:
            # Legacy M2-only entry (pulse data, no booking code)
            themes_str = ", ".join(top_themes) if top_themes else "—"
            pulse_snip = (pulse[:250] + "…") if len(pulse) > 250 else (pulse or "—")
            rows_html = (
                f'<span style="color:var(--text-3);">Date</span>'
                f'<span style="color:var(--text-1);">{date_v}</span>'
                f'<span style="color:var(--text-3);">Top Themes</span>'
                f'<span style="color:#E8C96D;font-weight:600;">{themes_str}</span>'
            )
            if fee_sc:
                rows_html += (
                    f'<span style="color:var(--text-3);">Fee Scenario</span>'
                    f'<span style="color:var(--text-1);">{fee_sc}</span>'
                )
            rows_html += (
                f'<span style="color:var(--text-3);align-self:start;">Pulse Summary</span>'
                f'<span style="color:var(--text-2);font-size:0.82rem;line-height:1.5;">{pulse_snip}</span>'
            )
        else:
            # M3 booking entry without pulse context
            rows_html = (
                f'<span style="color:var(--text-3);">Booking Code</span>'
                f'<span style="color:var(--text-1);font-family:monospace;letter-spacing:0.05em;">{code or "—"}</span>'
                f'<span style="color:var(--text-3);">Topic</span>'
                f'<span style="color:#E8C96D;font-weight:600;">{topic or "—"}</span>'
                f'<span style="color:var(--text-3);">Slot</span>'
                f'<span style="color:var(--text-1);">{slot or "—"}</span>'
                f'<span style="color:var(--text-3);">Date</span>'
                f'<span style="color:var(--text-1);">{date_v}</span>'
                f'<span style="color:var(--text-3);">Status</span>'
                f'<span style="color:#22C55E;font-weight:600;">{status_v or "—"}</span>'
            )

        html = (
            '<div style="background:var(--bg-card);border:1px solid var(--border);'
            'border-radius:12px;padding:16px 20px;margin:10px 0;">'
            '<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;'
            'border-bottom:1px solid var(--border);padding-bottom:10px;">'
            '<span style="font-size:1.4rem;">📝</span>'
            f'<span style="font-weight:700;color:var(--text-1);font-size:1rem;">Notes Entry — {doc}</span>'
            '</div>'
            '<div style="display:grid;grid-template-columns:130px 1fr;gap:8px 16px;font-size:0.875rem;">'
            + rows_html +
            '</div></div>'
        )
        st.markdown(html, unsafe_allow_html=True)

    elif atype == "email_draft":
        subject = payload.get("subject", "—")
        body    = payload.get("body", "")
        code    = payload.get("booking_code", "")
        topic   = payload.get("topic_label", "")
        slot    = payload.get("slot_start_ist", "")
        meta_html = ""
        if code:
            meta_html += f'<span style="color:var(--text-3);">Code</span><span style="color:var(--text-1);font-family:monospace;">{code}</span>'
        if topic:
            meta_html += f'<span style="color:var(--text-3);">Topic</span><span style="color:#E8C96D;font-weight:600;">{topic}</span>'
        if slot:
            meta_html += f'<span style="color:var(--text-3);">Slot</span><span style="color:var(--text-1);">{slot}</span>'
        meta_block = f'<div style="display:grid;grid-template-columns:80px 1fr;gap:6px 16px;font-size:0.85rem;margin-bottom:12px;">{meta_html}</div>' if meta_html else ""

        html = f"""
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin:10px 0;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;border-bottom:1px solid var(--border);padding-bottom:10px;">
    <span style="font-size:1.4rem;">✉️</span>
    <span style="font-weight:700;color:var(--text-1);font-size:1rem;">Email Draft</span>
  </div>
  <div style="margin-bottom:12px;">
    <div style="color:var(--text-3);font-size:0.8rem;margin-bottom:4px;">Subject</div>
    <div style="color:var(--text-1);font-weight:600;font-size:0.9rem;">{subject}</div>
  </div>
  {meta_block}
  <div>
    <div style="color:var(--text-3);font-size:0.8rem;margin-bottom:6px;">Body Preview</div>
    <pre style="color:var(--text-2);font-size:0.8rem;line-height:1.65;
                background:var(--bg-base);border:1px solid var(--border);border-radius:8px;
                padding:12px;max-height:200px;overflow-y:auto;
                white-space:pre-wrap;word-wrap:break-word;margin:0;font-family:inherit;">{body}</pre>
  </div>
</div>"""
        st.markdown(html, unsafe_allow_html=True)

    elif atype == "sheet_entry":
        code     = payload.get("booking_code", "—")
        topic_v  = payload.get("topic_label",  "—")
        slot_v   = payload.get("slot_start_ist","—")
        date_v   = payload.get("date",          "—")
        status_v = payload.get("status",        "—")
        call_v   = payload.get("call_id",       "—")
        html = f"""
<div style="background:var(--bg-card);border:1px solid var(--border);border-radius:12px;padding:16px 20px;margin:10px 0;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;border-bottom:1px solid var(--border);padding-bottom:10px;">
    <span style="font-size:1.4rem;">📊</span>
    <span style="font-weight:700;color:var(--text-1);font-size:1rem;">Google Sheet Entry — Advisor Pre-Bookings</span>
  </div>
  <div style="display:grid;grid-template-columns:130px 1fr;gap:8px 16px;font-size:0.875rem;">
    <span style="color:var(--text-3);">Booking Code</span>
    <span style="color:var(--text-1);font-family:monospace;letter-spacing:0.05em;">{code}</span>
    <span style="color:var(--text-3);">Topic</span>
    <span style="color:#E8C96D;font-weight:600;">{topic_v}</span>
    <span style="color:var(--text-3);">Date</span>
    <span style="color:var(--text-1);">{date_v}</span>
    <span style="color:var(--text-3);">Time Slot</span>
    <span style="color:var(--text-1);">{slot_v} IST</span>
    <span style="color:var(--text-3);">Status</span>
    <span style="color:#22C55E;font-weight:600;">{status_v}</span>
    <span style="color:var(--text-3);">Call ID</span>
    <span style="color:var(--text-1);font-family:monospace;font-size:0.8rem;">{call_v}</span>
  </div>
</div>"""
        st.markdown(html, unsafe_allow_html=True)

    else:
        st.json(payload)


def render(session: dict, mcp_client: MCPClient) -> None:
    """Render the full HITL approval panel inside Streamlit Tab 3."""
    queue = session.get("mcp_queue", [])

    if not queue:
        st.info(
            "No pending actions. "
            "Complete a Voice Booking call to generate actions for approval."
        )
        return

    pending_count   = sum(1 for a in queue if a["status"] == "pending")
    completed_count = sum(1 for a in queue if a["status"] in ("approved", "rejected", "error"))

    col_warn, col_metric, col_clear = st.columns([2.5, 1.5, 1], vertical_alignment="center")
    with col_warn:
        if pending_count > 0:
            st.warning(f"⚠ {pending_count} action(s) awaiting your approval")
        else:
            st.success("✓ All actions processed")
    with col_metric:
        st.metric("Pending Approvals", pending_count)
    with col_clear:
        if completed_count > 0:
            if st.button(f"🗑️ Clear {completed_count} completed", use_container_width=True):
                session["mcp_queue"] = [a for a in queue if a["status"] == "pending"]
                _persist(session)
                st.rerun()

    # Show MCP super-agent banner if any actions were Claude-generated
    _claude_actions = [a for a in queue if a.get("agent")]
    if _claude_actions:
        st.markdown(
            '<div style="background:#1E1B4B;border:1px solid #312E81;border-radius:10px;'
            'padding:10px 16px;margin-bottom:14px;display:flex;align-items:center;gap:10px;">'
            '<span style="font-size:1.1rem;">🤖</span>'
            '<span style="color:#A5B4FC;font-size:0.85rem;font-weight:600;">'
            'MCP Super-Agent active — actions below were generated by Claude via tool_use '
            '(Model Context Protocol). Review each before approving.'
            '</span></div>',
            unsafe_allow_html=True,
        )

    _SOURCE_GROUPS = [
        ("m3_voice", "📋 Booking Actions", "4 actions generated per booking: Email · Notes · Calendar · Google Sheet"),
    ]
    # Normalise legacy source values to canonical group keys
    _SOURCE_ALIASES = {
        "m2_pipeline":             "other",
        "review_pulse_dashboard":  "other",
        "m2":                      "other",
        "m3_voice":                "m3_voice",
        "m3":                      "m3_voice",
    }
    _grouped: dict[str, list] = {"m3_voice": [], "other": []}
    for _a in queue:
        _canon = _SOURCE_ALIASES.get(_a.get("source", ""), "other")
        _grouped[_canon].append(_a)

    for _group_key, _group_label, _group_desc in _SOURCE_GROUPS:
        _items = _grouped.get(_group_key, [])
        if not _items:
            continue
        st.markdown(
            f'<div style="display:flex;align-items:baseline;gap:12px;margin:18px 0 6px;">'
            f'<span style="font-size:1rem;font-weight:700;color:var(--text-1,#F5F0E8);">{_group_label}</span>'
            f'<span style="font-size:0.78rem;color:var(--text-3,#6B6358);">{_group_desc}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        for action in _items:
            _render_single_action(action, session, mcp_client)

    for action in _grouped.get("other", []):
        _render_single_action(action, session, mcp_client)


def _render_single_action(action: dict, session: dict, mcp_client: MCPClient) -> None:
    """Render one action card with approve/reject controls."""
    label  = TYPE_LABELS.get(action["type"], action["type"])
    status = action["status"]
    source = action.get("source", "")

    badge_text, badge_bg, badge_fg = STATUS_STYLE.get(status, ("—", "#6B6358", "#F5F0E8"))
    agent       = action.get("agent", "")
    agent_badge = (
        '<span style="background:#312E81;color:#A5B4FC;font-size:0.7rem;font-weight:700;'
        'padding:2px 8px;border-radius:100px;margin-left:4px;">🤖 Claude MCP</span>'
        if agent else ""
    )
    header_html = (
        f'<div style="display:flex;align-items:center;gap:12px;padding:4px 0;">'
        f'<span style="font-size:0.95rem;font-weight:600;color:var(--text-1);">{label}</span>'
        f'<span style="background:{badge_bg};color:{badge_fg};font-size:0.75rem;font-weight:700;'
        f'padding:2px 10px;border-radius:100px;">{badge_text}</span>'
        f'{agent_badge}'
        f'<span style="color:var(--text-3);font-size:0.8rem;">{source}</span>'
        f'</div>'
    )
    with st.expander(label + f" [{status.upper()}]", expanded=(status == "pending")):
        st.markdown(header_html, unsafe_allow_html=True)
        _agent_str = f"   ·   🤖 {action['agent']}" if action.get("agent") else ""
        st.caption(f"ID: {action['action_id'][:8]}…   ·   {action['created_at'][:19]}{_agent_str}")

        _render_action_card(action)

        if status == "pending":
            key_base = action["action_id"][:8]

            client_name  = ""
            client_email = ""
            client_phone = ""

            if action["type"] == "email_draft" and action.get("source") == "m3_voice":
                st.markdown("---")
                st.markdown("**Send Confirmation Email to Client**")
                st.caption("Name and Email are required. Phone is optional.")

                c1, c2 = st.columns(2)
                with c1:
                    client_name  = st.text_input("Client Name *", key=f"name_{key_base}",
                                                  placeholder="e.g. Rahul Sharma")
                    client_email = st.text_input("Client Email *", key=f"email_{key_base}",
                                                  placeholder="e.g. rahul@example.com")
                with c2:
                    client_phone = st.text_input("Phone (optional)", key=f"phone_{key_base}",
                                                  placeholder="e.g. +91 98765 43210")

            col1, col2 = st.columns([3, 1])
            with col1:
                can_send  = (action["type"] == "email_draft"
                             and bool(client_email.strip())
                             and bool(client_name.strip()))
                btn_label = "✓ Approve & Send Email" if can_send else "✓ Approve"
                if st.button(btn_label, key=f"approve_{key_base}", type="primary"):
                    action["status"] = "approved"
                    result = mcp_client.execute(action)
                    if result.success:
                        action["ref_id"] = result.ref_id
                        st.success(f"✓ Executed — ref: {result.ref_id} (mode: {result.mode})")
                        if can_send:
                            _send_client_email(action, client_name, client_email, client_phone)
                    else:
                        action["status"] = "error"
                        st.error(f"Execution failed: {action.get('error_msg', 'unknown error')}")
                    _persist(session)
                    st.rerun()

            with col2:
                if st.button("✗ Reject", key=f"reject_{key_base}", type="secondary"):
                    action["status"] = "rejected"
                    _persist(session)
                    st.rerun()

        elif status == "approved":
            ref = action.get("ref_id", "")
            st.success(f"✓ Approved — ref: {ref}")

        elif status == "rejected":
            st.error("✗ Rejected")

        elif status == "error":
            st.error(f"⚠ Error: {action.get('error_msg', 'unknown')}")


def _send_client_email(action: dict, name: str, email: str, phone: str) -> None:
    """Send a confirmation email to the client and show inline status."""
    payload      = action.get("payload", {})
    booking_code = payload.get("booking_code") or session_booking_code(action)
    topic_label  = payload.get("topic_label", "Advisor Appointment")
    slot_ist     = payload.get("slot_start_ist", "TBD")

    phone_line = f"\nPhone: {phone.strip()}" if phone.strip() else ""

    try:
        from .mcp.email_tool import send_user_confirmation
        send_user_confirmation(
            to_name      = name.strip(),
            to_email     = email.strip(),
            booking_code = booking_code,
            topic_label  = topic_label,
            slot_ist     = slot_ist + phone_line,
        )
        st.success(f"📧 Confirmation email sent to {email.strip()}!")
        if phone.strip():
            st.caption(f"Phone {phone.strip()} noted in the email.")
    except Exception as exc:
        st.error(f"Failed to send client email: {exc}")


def session_booking_code(action: dict) -> str:
    """Extract booking code from action payload body as last resort."""
    body = action.get("payload", {}).get("body", "")
    import re
    m = re.search(r"NL-[A-Z0-9]{4}", body)
    return m.group(0) if m else "UNKNOWN"


def _persist(session: dict) -> None:
    MCP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MCP_STATE_PATH.write_text(
        json.dumps(session.get("mcp_queue", []), indent=2)
    )
