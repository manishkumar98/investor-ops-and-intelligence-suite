import json
import re
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pytz

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


def _send_advisor_email_live(payload: dict) -> None:
    """Send the rich advisor pre-booking email (HTML + plain fallback) via Gmail SMTP."""
    from .mcp.config import config  # noqa: PLC0415
    from .mcp.email_tool import _advisor_html  # noqa: PLC0415

    subject = payload.get("subject", "Advisor Pre-Booking")
    body    = payload.get("body", "")

    msg = MIMEMultipart("alternative")
    msg["From"]    = f"AdvisorBot <{config.gmail_address}>"
    msg["To"]      = config.advisor_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(_advisor_html(payload), "html"))

    with smtplib.SMTP(config.gmail_smtp_host, config.gmail_smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(config.gmail_address, config.gmail_app_password)
        smtp.sendmail(config.gmail_address, config.advisor_email, msg.as_bytes())


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
                _send_advisor_email_live(action["payload"])
            except Exception as exc:
                action["error_msg"] = str(exc)
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
                asyncio.run(create_calendar_hold(mcp_payload))
            except Exception as exc:
                action["error_msg"] = str(exc)
                return MCPResult(success=False, ref_id="", mode="live")

        elif action["type"] == "sheet_entry":
            try:
                from phase7_pillar_c_hitl.mcp.models import MCPPayload
                from phase7_pillar_c_hitl.mcp.sheets_tool import _append_row_sync
                p = action["payload"]
                # slot_start_ist payload may be human-readable; derive ISO from date + slot/time
                _slot_human = p.get("slot_start_ist", "") or p.get("slot", "")
                slot_start_iso, _ = _coerce_slot_iso(
                    p.get("date", "") or _slot_human,
                    _slot_human,
                )
                mcp_payload = MCPPayload(
                    booking_code=p.get("booking_code", ""),
                    call_id=p.get("call_id", ""),
                    topic_key=p.get("topic_key", ""),
                    topic_label=p.get("topic_label", ""),
                    slot_start_iso=slot_start_iso or _slot_human,
                    slot_start_ist=_slot_human or slot_start_iso,
                    slot_end_iso="",
                    advisor_id=p.get("advisor_id", ""),
                    created_at_ist=datetime.now(IST).isoformat(),
                    status=p.get("status", "booked"),
                )
                _append_row_sync(mcp_payload, event_id=None)
            except Exception as exc:
                action["error_msg"] = str(exc)
                return MCPResult(success=False, ref_id="", mode="live")

        return MCPResult(success=True, ref_id=ref_id, mode="live")

    def save_state(self, session: dict) -> None:
        MCP_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        MCP_STATE_PATH.write_text(
            json.dumps(session.get("mcp_queue", []), indent=2)
        )
