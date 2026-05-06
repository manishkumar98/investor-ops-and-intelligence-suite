import json
import os
import re
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pytz
import requests

MCP_STATE_PATH = Path(__file__).resolve().parents[1] / "data" / "mcp_state.json"
IST = pytz.timezone("Asia/Kolkata")


def _coerce_slot_iso(date_str: str, time_str: str) -> tuple[str, str]:
    """
    Build (slot_start_iso, slot_end_iso) from voice-agent payload fields.

    Inputs may be:
      date_str  : "2026-05-08"  or  "Friday, 2026-05-08 at 10:00 AM IST"  or  ""
      time_str  : "10:00"  or  "10:00 AM IST"  or  "10:00 AM"  or  ""

    Returns ISO 8601 strings parseable by datetime.fromisoformat(),
    e.g. ("2026-05-08T10:00:00+05:30", "2026-05-08T10:30:00+05:30").

    Returns ("", "") if no usable date+time can be derived.
    """
    # Pull a YYYY-MM-DD anywhere in date_str
    iso_date_match = re.search(r"(\d{4}-\d{2}-\d{2})", date_str or "")
    if not iso_date_match:
        # Fall back to today's date if only a time is given
        iso_date = datetime.now(IST).strftime("%Y-%m-%d")
    else:
        iso_date = iso_date_match.group(1)

    # Parse the time part — accept "10:00", "10:00 AM", "10:00 AM IST",
    # "2 PM", or extract from "Friday, 2026-05-08 at 10:00 AM IST"
    sources = [time_str or "", date_str or ""]
    hour: int | None = None
    minute: int = 0
    for src in sources:
        raw = src.upper().replace("IST", "")
        m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(AM|PM)\b", raw)
        if not m:
            m = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", raw)
            if m:
                hour = int(m.group(1))
                minute = int(m.group(2))
                break
            continue
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)
        if ampm == "PM" and hour < 12:
            hour += 12
        elif ampm == "AM" and hour == 12:
            hour = 0
        break
    if hour is None:
        return "", ""

    try:
        naive = datetime.fromisoformat(f"{iso_date}T{hour:02d}:{minute:02d}:00")
    except ValueError:
        return "", ""
    start_aware = IST.localize(naive)
    end_aware   = start_aware + timedelta(minutes=30)
    return start_aware.isoformat(), end_aware.isoformat()


def _send_via_brevo(sender: str, sender_name: str, to_email: str, to_name: str,
                    subject: str, html_body: str, plain_body: str) -> str:
    """
    Send an email via Brevo's HTTPS REST API.

    Cloud platforms like Railway block outbound SMTP (port 587/465) on most
    plans, which surfaces as 'Network is unreachable'.  Brevo uses HTTPS
    (port 443) so it goes through.  Requires BREVO_API_KEY env var.

    Returns 'delivered via brevo to <addr>' on success.
    """
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BREVO_API_KEY not set")
    resp = requests.post(
        "https://api.brevo.com/v3/smtp/email",
        headers={
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json",
        },
        json={
            "sender":      {"name": sender_name, "email": sender},
            "to":          [{"email": to_email, "name": to_name or to_email}],
            "subject":     subject,
            "htmlContent": html_body,
            "textContent": plain_body,
        },
        timeout=20,
    )
    if not resp.ok:
        raise RuntimeError(f"brevo API {resp.status_code}: {resp.text[:200]}")
    return f"delivered via brevo to {to_email}"


def _send_via_smtp(sender: str, password: str, smtp_host: str, smtp_port: int,
                   to_email: str, msg_bytes: bytes) -> str:
    """SMTP send. Used as a fallback when Brevo is unavailable."""
    with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(sender, password)
        refused = smtp.sendmail(sender, [to_email], msg_bytes)
    if refused:
        raise RuntimeError(f"recipient(s) refused by SMTP: {refused}")
    return f"delivered via smtp to {to_email}"


def _send_advisor_email_live(payload: dict) -> str:
    """Send the rich advisor pre-booking email (HTML + plain fallback).

    Tries Brevo HTTPS API first (works on Railway / cloud platforms that
    block outbound SMTP), then falls back to Gmail SMTP for local dev.

    Returns a short status string ("delivered via <provider> to <addr>").
    Raises with a clear message on any misconfiguration so the HITL UI
    surfaces it instead of silently showing 'Approved' with no email.
    """
    from .mcp.config import config  # noqa: PLC0415
    from .mcp.email_tool import _advisor_html  # noqa: PLC0415

    if not config.gmail_address:
        raise RuntimeError("GMAIL_ADDRESS env var not set")
    if not config.advisor_email:
        raise RuntimeError("ADVISOR_EMAIL env var not set (and GMAIL_ADDRESS empty)")

    subject = payload.get("subject", "Advisor Pre-Booking")
    body    = payload.get("body", "")
    html    = _advisor_html(payload)

    # ── Path 1: Brevo HTTPS (preferred on Railway) ─────────────────────────
    if os.environ.get("BREVO_API_KEY", "").strip():
        return _send_via_brevo(
            sender=config.gmail_address,
            sender_name="AdvisorBot",
            to_email=config.advisor_email,
            to_name=config.advisor_email,
            subject=subject,
            html_body=html,
            plain_body=body,
        )

    # ── Path 2: SMTP fallback (works locally, blocked on Railway) ──────────
    if not config.gmail_app_password:
        raise RuntimeError(
            "Neither BREVO_API_KEY nor GMAIL_APP_PASSWORD is set. "
            "On Railway, set BREVO_API_KEY (SMTP is blocked)."
        )
    msg = MIMEMultipart("alternative")
    msg["From"]    = f"AdvisorBot <{config.gmail_address}>"
    msg["To"]      = config.advisor_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(html, "html"))
    return _send_via_smtp(
        sender=config.gmail_address,
        password=config.gmail_app_password,
        smtp_host=config.gmail_smtp_host,
        smtp_port=config.gmail_smtp_port,
        to_email=config.advisor_email,
        msg_bytes=msg.as_bytes(),
    )


@dataclass
class MCPResult:
    success: bool
    ref_id:  str
    mode:    str


def enqueue_action(session: dict, type: str, payload: dict, source: str) -> str:
    """Append a standardised pending action to session["mcp_queue"].

    This is the ONLY way to add items to the queue — never construct action
    dicts inline elsewhere in the codebase.
    """
    if "mcp_queue" not in session:
        session["mcp_queue"] = []

    # Supersede any existing PENDING action of the same type+source so there is
    # never more than one pending copy of the same action type per source.
    session["mcp_queue"] = [
        a for a in session["mcp_queue"]
        if not (a["status"] == "pending" and a["type"] == type and a["source"] == source)
    ]

    action = {
        "action_id":  str(uuid.uuid4()),
        "type":       type,       # calendar_hold | notes_append | email_draft | sheet_entry
        "status":     "pending",
        "created_at": datetime.utcnow().isoformat(),
        "source":     source,     # m2_pipeline | m3_voice
        "payload":    payload,
    }
    session["mcp_queue"].append(action)
    return action["action_id"]


class MCPClient:
    def __init__(self, mode: str = "mock"):
        self.mode = mode
        self._mock_store: dict = {}
        # booking_code → calendar_event_id, populated by calendar_hold success,
        # consumed by sheet_entry so the sheet row stores the real event id.
        self._event_ids: dict[str, str] = {}

    def execute(self, action: dict) -> MCPResult:
        """Execute an approved action.

        mock mode  — records in memory, no external calls.
        live mode  — all 4 action types execute on approval:
                     calendar_hold: creates Google Calendar event.
                     notes_append:  appends to Google Doc.
                     sheet_entry:   appends row to Google Sheet.
                     email_draft:   SMTP-sends advisor email with Market Context.
        """
        ref_id = str(uuid.uuid4())

        if self.mode == "mock":
            self._mock_store[action["action_id"]] = {**action, "ref_id": ref_id}
            return MCPResult(success=True, ref_id=ref_id, mode="mock")

        # Live mode
        if action["type"] == "email_draft":
            try:
                # Propagate the captured client_email onto the payload so the
                # advisor email's "Add to Google Calendar" link pre-adds the
                # user as a guest (Google sends invite on save).
                _payload_for_send = dict(action["payload"])
                if action.get("client_email"):
                    _payload_for_send["client_email"] = action["client_email"]
                smtp_result = _send_advisor_email_live(_payload_for_send)
                # Surface the SMTP server's response to the UI so the user can
                # tell at a glance whether the message was actually accepted.
                action["smtp_status"] = smtp_result or "accepted"
            except Exception as exc:
                action["error_msg"] = f"SMTP send failed: {exc}"
                return MCPResult(success=False, ref_id="", mode="live")

        elif action["type"] == "notes_append":
            try:
                from phase7_pillar_c_hitl.mcp.docs_tool import append_notes_sync
                append_notes_sync(action["payload"])
            except Exception as exc:
                action["error_msg"] = str(exc)
                return MCPResult(success=False, ref_id="", mode="live")

        elif action["type"] == "calendar_hold":
            try:
                import asyncio
                from phase7_pillar_c_hitl.mcp.models import MCPPayload
                from phase7_pillar_c_hitl.mcp.calendar_tool import create_calendar_hold
                p = action["payload"]
                slot_start_iso, slot_end_iso = _coerce_slot_iso(
                    p.get("date", ""), p.get("time", "")
                )
                if not slot_start_iso:
                    raise ValueError(
                        f"calendar_hold: could not parse slot from "
                        f"date={p.get('date')!r} time={p.get('time')!r}"
                    )
                mcp_payload = MCPPayload(
                    booking_code=p.get("booking_code", ""),
                    call_id=p.get("call_id", ""),
                    topic_key=p.get("topic", ""),
                    topic_label=p.get("title", ""),
                    slot_start_iso=slot_start_iso,
                    slot_start_ist=slot_start_iso,
                    slot_end_iso=slot_end_iso,
                    advisor_id="",
                    created_at_ist=datetime.now(IST).isoformat(),
                    status="booked",
                )
                cal_result = asyncio.run(create_calendar_hold(mcp_payload))
                # Capture the calendar event_id so a later sheet_entry execution
                # for the same booking_code can persist it.
                event_id = ""
                if getattr(cal_result, "data", None):
                    event_id = cal_result.data.get("event_id", "") or ""
                if event_id and mcp_payload.booking_code:
                    self._event_ids[mcp_payload.booking_code] = event_id
                    action["event_id"] = event_id
                # If a sheet row already exists for this booking, back-fill the
                # event_id column now (sheet_entry may have run first).
                if event_id and mcp_payload.booking_code:
                    try:
                        from phase7_pillar_c_hitl.mcp.sheets_tool import (
                            _get_booking_row_sync,
                        )
                        import gspread  # noqa: F401  (lazy import for Sheets API)
                        row_idx, existing_evt = _get_booking_row_sync(
                            mcp_payload.booking_code
                        )
                        if row_idx and not existing_evt:
                            from phase7_pillar_c_hitl.mcp.sheets_tool import _build_client
                            from phase7_pillar_c_hitl.mcp.config import config
                            client = _build_client()
                            ws = client.open_by_key(config.sheet_id).worksheet(
                                config.sheet_tab
                            )
                            # calendar_event_id is the 8th column (index 8 → col 8)
                            ws.update_cell(row_idx, 8, event_id)
                    except Exception:
                        pass  # back-fill is best-effort
            except Exception as exc:
                action["error_msg"] = str(exc)
                return MCPResult(success=False, ref_id="", mode="live")

        elif action["type"] == "sheet_entry":
            try:
                from phase7_pillar_c_hitl.mcp.models import MCPPayload
                from phase7_pillar_c_hitl.mcp.sheets_tool import _append_row_sync
                p = action["payload"]
                booking_code = p.get("booking_code", "")
                # slot_start_ist from Claude may be just "2:00 PM IST" — derive
                # full ISO from any date/slot field we can find, then pass the
                # ISO form as slot_start_ist so the sheet column is unambiguous.
                _slot_human = p.get("slot_start_ist", "") or p.get("slot", "")
                slot_start_iso, _ = _coerce_slot_iso(
                    p.get("date", "") or _slot_human,
                    _slot_human,
                )
                # If we got a clean ISO, use it for the sheet column too — it
                # contains date+time and sorts correctly. Fall back to the
                # human string only if parsing failed.
                slot_for_sheet = slot_start_iso or _slot_human
                event_id = self._event_ids.get(booking_code, "") or p.get("event_id", "")
                mcp_payload = MCPPayload(
                    booking_code=booking_code,
                    call_id=p.get("call_id", ""),
                    topic_key=p.get("topic_key", ""),
                    topic_label=p.get("topic_label", ""),
                    slot_start_iso=slot_start_iso or _slot_human,
                    slot_start_ist=slot_for_sheet,
                    slot_end_iso="",
                    advisor_id=p.get("advisor_id", ""),
                    created_at_ist=datetime.now(IST).isoformat(),
                    status=p.get("status", "booked"),
                )
                _append_row_sync(mcp_payload, event_id=event_id or None)
            except Exception as exc:
                action["error_msg"] = str(exc)
                return MCPResult(success=False, ref_id="", mode="live")

        return MCPResult(success=True, ref_id=ref_id, mode="live")

    def save_state(self, session: dict) -> None:
        MCP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        MCP_STATE_PATH.write_text(
            json.dumps(session.get("mcp_queue", []), indent=2)
        )
