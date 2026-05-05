import json
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

MCP_STATE_PATH = Path("data/mcp_state.json")


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
                from .mcp.docs_tool import append_notes_sync
                append_notes_sync(action["payload"])
            except Exception as exc:
                action["error_msg"] = str(exc)
                return MCPResult(success=False, ref_id="", mode="live")

        elif action["type"] == "calendar_hold":
            try:
                import asyncio
                from .mcp.models import MCPPayload
                from .mcp.calendar_tool import create_calendar_hold
                p = action["payload"]
                mcp_payload = MCPPayload(
                    booking_code=p.get("booking_code", ""),
                    call_id=p.get("call_id", ""),
                    topic_key=p.get("topic", ""),
                    topic_label=p.get("title", ""),
                    slot_start_iso=p.get("time", ""),
                    slot_start_ist=p.get("time", ""),
                    slot_end_iso="",
                    advisor_id="",
                    created_at_ist=p.get("date", ""),
                    status="booked",
                )
                asyncio.run(create_calendar_hold(mcp_payload))
            except Exception as exc:
                action["error_msg"] = str(exc)
                return MCPResult(success=False, ref_id="", mode="live")

        elif action["type"] == "sheet_entry":
            try:
                from .mcp.models import MCPPayload
                from .mcp.sheets_tool import _append_row_sync
                p = action["payload"]
                mcp_payload = MCPPayload(
                    booking_code=p.get("booking_code", ""),
                    call_id=p.get("call_id", ""),
                    topic_key=p.get("topic_key", ""),
                    topic_label=p.get("topic_label", ""),
                    slot_start_iso=p.get("slot_start_ist", ""),
                    slot_start_ist=p.get("slot_start_ist", ""),
                    slot_end_iso="",
                    advisor_id=p.get("advisor_id", ""),
                    created_at_ist=p.get("date", ""),
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
