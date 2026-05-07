"""
Phase 4 — Gmail email tools.

draft_approval_email   — saves advisor approval email to Gmail Drafts (IMAP APPEND)
send_user_confirmation — sends a confirmation email to the user via SMTP
"""
from __future__ import annotations

import asyncio
import imaplib
import re
import smtplib
import time
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlencode

from phase7_pillar_c_hitl.mcp.config import config
from phase7_pillar_c_hitl.mcp.models import MCPPayload, ToolResult

_IMAP_HOST = "imap.gmail.com"
_IST = timezone(timedelta(hours=5, minutes=30))


# ── Google Calendar URL helper ────────────────────────────────────────────────

def _gcal_url(title: str, date_iso: str, time_str: str, description: str = "",
              duration_min: int = 60, guests: list[str] | None = None) -> str:
    """Build a Google Calendar 'add event' URL from date (YYYY-MM-DD) and time string.

    Pass `guests=["user@example.com"]` to pre-fill the guest list on the
    Google Calendar create-event page (param `add`).  When the advisor
    saves the event Google sends an invite to each guest.
    """
    # Parse time — accept "2:00 PM", "14:00", "10:00 AM IST", etc.
    hour, minute = 9, 0   # sensible default
    t = time_str.strip().upper().replace(" IST", "")
    m = re.search(r"(\d{1,2}):?(\d{2})?\s*(AM|PM)?", t)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        if m.group(3) == "PM" and hour != 12:
            hour += 12
        elif m.group(3) == "AM" and hour == 12:
            hour = 0

    try:
        start_ist = datetime(
            *[int(p) for p in date_iso.split("-")], hour, minute,
            tzinfo=_IST
        )
    except Exception:
        # Fallback: no time encoding — just use date
        return (
            "https://calendar.google.com/calendar/render?"
            + urlencode({"action": "TEMPLATE", "text": title, "dates": date_iso.replace("-", "") + "/" + date_iso.replace("-", "")})
        )

    end_ist   = start_ist + timedelta(minutes=duration_min)
    fmt       = "%Y%m%dT%H%M%S"
    # Google Calendar interprets bare datetime as local time; append timezone offset
    dates_str = start_ist.strftime(fmt) + "/" + end_ist.strftime(fmt)

    params = {
        "action":  "TEMPLATE",
        "text":    title,
        "dates":   dates_str,
        "ctz":     "Asia/Kolkata",
        "details": description,
    }
    if guests:
        # Google Calendar accepts comma-separated emails in `add`
        params["add"] = ",".join(g for g in guests if g)
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


# ── Advisor HTML email (rich, formatted) ─────────────────────────────────────

def _advisor_html(payload: dict, event_id: str | None = None) -> str:
    code        = payload.get("booking_code", "—")
    topic       = payload.get("topic_label", payload.get("topic", "—"))
    date        = payload.get("date", "—")
    slot        = payload.get("slot_start_ist", payload.get("time", payload.get("slot", "—")))
    call_id     = payload.get("call_id", "—")
    client_email = payload.get("client_email", "")

    # ── Structured context (preferred) — set explicitly by voice_agent ────────
    top_themes   = payload.get("top_themes", [])
    market_ctx   = payload.get("market_context", "")
    fee_bullets  = payload.get("fee_bullets", [])
    fee_sources  = payload.get("fee_sources", [])

    # ── Fallback: parse from plain-text body if structured fields absent ───────
    if not market_ctx:
        body = payload.get("body", "")
        if body:
            lines      = body.splitlines()
            in_mc      = False
            past_header = False
            mc_lines   = []
            for line in lines:
                stripped = line.strip()
                if "MARKET CONTEXT" in stripped.upper() or "TOP THEMES" in stripped.upper():
                    in_mc = True
                    continue
                if in_mc:
                    if stripped.startswith("─"):
                        if past_header:
                            break   # end of section
                        past_header = True
                        continue    # skip the divider line right after header
                    past_header = True
                    if stripped:
                        mc_lines.append(stripped)
            market_ctx = " ".join(mc_lines)

    # Build Google Calendar link
    gcal_href = _gcal_url(
        title=f"Advisor Q&A — {topic} [{code}]",
        date_iso=date if date != "—" else "2026-01-01",
        time_str=slot,
        description=f"INDMoney Advisor pre-booking.\nBooking code: {code}\nTopic: {topic}",
        guests=[client_email] if client_email else None,
    )

    cal_row = (
        f"<tr><td style='padding:10px 14px;border:1px solid #ddd;font-weight:600'>Calendar Event</td>"
        f"<td style='padding:10px 14px;border:1px solid #ddd'>{event_id}</td></tr>"
        if event_id else ""
    )

    # ── Market context section ─────────────────────────────────────────────────
    mc_section = ""
    if market_ctx or top_themes:
        themes_html = ""
        if top_themes:
            items = "".join(
                f"<li style='margin:4px 0'><strong>#{i+1}</strong> {t}</li>"
                for i, t in enumerate(top_themes[:3])
            )
            themes_html = f"<ul style='margin:8px 0 12px;padding-left:18px;color:#444;font-size:0.9em'>{items}</ul>"

        ctx_html = ""
        if market_ctx:
            ctx_html = (
                f"<p style='margin:0;color:#444;font-size:0.9em;line-height:1.6'>{market_ctx}</p>"
            )

        mc_section = f"""
        <div style="background:#f8f9fa;border-left:4px solid #4285f4;padding:14px 18px;border-radius:0 8px 8px 0;margin:20px 0">
          <p style="margin:0 0 8px;font-weight:700;color:#4285f4;font-size:0.95em">MARKET CONTEXT — This Week's Customer Pulse</p>
          {themes_html}{ctx_html}
        </div>"""

    # ── Fee context section ────────────────────────────────────────────────────
    fee_section = ""
    if fee_bullets:
        items = "".join(f"<li style='margin:4px 0;color:#444;font-size:0.88em'>{b}</li>" for b in fee_bullets)
        src_html = ""
        if fee_sources:
            links = " · ".join(
                f"<a href='{s}' style='color:#1a73e8'>{s.split('/')[2] if '/' in s else s}</a>"
                for s in fee_sources[:3]
            )
            src_html = f"<p style='margin:8px 0 0;font-size:0.8em;color:#888'>Sources: {links}</p>"
        fee_section = f"""
        <div style="background:#fafafa;border-left:4px solid #fbbc04;padding:14px 18px;border-radius:0 8px 8px 0;margin:16px 0">
          <p style="margin:0 0 8px;font-weight:700;color:#b45309;font-size:0.9em">FEE CONTEXT</p>
          <ul style="margin:0;padding-left:18px">{items}</ul>
          {src_html}
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#333;max-width:680px;margin:auto;padding:16px">

<div style="background:linear-gradient(135deg,#1a73e8,#0d47a1);padding:28px 32px;border-radius:12px 12px 0 0">
  <h2 style="color:white;margin:0;font-size:1.4em">&#128197; New Advisor Pre-Booking</h2>
  <p style="color:#bbdefb;margin:6px 0 0;font-size:0.92em">INDMoney Voice Scheduling Agent</p>
</div>

<div style="background:#ffffff;border:1px solid #e8eaed;border-top:none;border-radius:0 0 12px 12px;padding:28px 32px">

  <p style="margin:0 0 16px">Dear <strong>{config.advisor_name}</strong>,</p>
  <p style="margin:0 0 20px;color:#555">A new appointment has been pre-booked via the voice agent. Please review and approve the actions in the <strong>Action Centre</strong>.</p>

  <table style="border-collapse:collapse;width:100%;margin:0 0 20px">
    <tr style="background:#e8f0fe">
      <td style="padding:11px 14px;border:1px solid #c5cae9;font-weight:700;width:38%">Booking Code</td>
      <td style="padding:11px 14px;border:1px solid #c5cae9">
        <span style="background:#e8f0fe;color:#1a73e8;padding:3px 12px;border-radius:6px;font-weight:700;font-size:1.05em;letter-spacing:1px">{code}</span>
      </td>
    </tr>
    <tr>
      <td style="padding:11px 14px;border:1px solid #e0e0e0;font-weight:700">Topic</td>
      <td style="padding:11px 14px;border:1px solid #e0e0e0">{topic}</td>
    </tr>
    <tr style="background:#e8f0fe">
      <td style="padding:11px 14px;border:1px solid #c5cae9;font-weight:700">Date</td>
      <td style="padding:11px 14px;border:1px solid #c5cae9"><strong>{date}</strong></td>
    </tr>
    <tr>
      <td style="padding:11px 14px;border:1px solid #e0e0e0;font-weight:700">Time (IST)</td>
      <td style="padding:11px 14px;border:1px solid #e0e0e0">{slot}</td>
    </tr>
    <tr style="background:#e8f0fe">
      <td style="padding:11px 14px;border:1px solid #c5cae9;font-weight:700">Status</td>
      <td style="padding:11px 14px;border:1px solid #c5cae9">
        <span style="background:#e6f4ea;color:#137333;padding:3px 12px;border-radius:6px;font-weight:700">&#10003; CONFIRMED</span>
      </td>
    </tr>
    {cal_row}
    <tr>
      <td style="padding:11px 14px;border:1px solid #e0e0e0;font-weight:700">Call ID</td>
      <td style="padding:11px 14px;border:1px solid #e0e0e0;color:#888;font-size:0.9em">{call_id}</td>
    </tr>
  </table>

  <a href="{gcal_href}" target="_blank"
     style="display:inline-block;background:#1a73e8;color:white;padding:11px 22px;
            border-radius:8px;text-decoration:none;font-weight:600;font-size:0.95em;margin-bottom:20px">
    &#128197; Add to Google Calendar
  </a>

  {mc_section}

  {fee_section}

  <p style="color:#888;font-size:0.82em;border-top:1px solid #eee;padding-top:14px;margin-top:8px">
    Automated pre-booking notification from INDMoney Advisor Suite. No PII was shared on the voice call.
    No investment advice implied.
  </p>
</div>
</body>
</html>"""


# ── Advisor Cancellation HTML email ──────────────────────────────────────────

def _advisor_cancellation_html(payload: dict) -> str:
    """Red-themed advisor email for booking cancellations."""
    code         = payload.get("booking_code", "—")
    topic        = payload.get("topic_label", payload.get("topic", "—"))
    date         = payload.get("date", "—")
    slot         = payload.get("slot_start_ist", payload.get("time", payload.get("slot", "—")))

    from phase7_pillar_c_hitl.mcp.config import config  # noqa: PLC0415

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#333;max-width:680px;margin:auto;padding:16px">

<div style="background:linear-gradient(135deg,#dc2626,#991b1b);padding:28px 32px;border-radius:12px 12px 0 0">
  <h2 style="color:white;margin:0;font-size:1.4em">&#128683; Booking Cancelled</h2>
  <p style="color:#fecaca;margin:6px 0 0;font-size:0.92em">INDMoney Voice Scheduling Agent</p>
</div>

<div style="background:#ffffff;border:1px solid #fecaca;border-top:none;border-radius:0 0 12px 12px;padding:28px 32px">

  <p style="margin:0 0 16px">Dear <strong>{config.advisor_name}</strong>,</p>
  <p style="margin:0 0 20px;color:#555">The following appointment has been <strong style="color:#dc2626">cancelled</strong> by the investor via the voice agent.</p>

  <table style="border-collapse:collapse;width:100%;margin:0 0 20px">
    <tr style="background:#fee2e2">
      <td style="padding:11px 14px;border:1px solid #fca5a5;font-weight:700;width:38%">Booking Code</td>
      <td style="padding:11px 14px;border:1px solid #fca5a5">
        <span style="background:#fee2e2;color:#dc2626;padding:3px 12px;border-radius:6px;font-weight:700;font-size:1.05em;letter-spacing:1px">{code}</span>
      </td>
    </tr>
    <tr>
      <td style="padding:11px 14px;border:1px solid #fecaca;font-weight:700">Topic</td>
      <td style="padding:11px 14px;border:1px solid #fecaca">{topic}</td>
    </tr>
    <tr style="background:#fee2e2">
      <td style="padding:11px 14px;border:1px solid #fca5a5;font-weight:700">Date</td>
      <td style="padding:11px 14px;border:1px solid #fca5a5"><strong>{date}</strong></td>
    </tr>
    <tr>
      <td style="padding:11px 14px;border:1px solid #fecaca;font-weight:700">Time (IST)</td>
      <td style="padding:11px 14px;border:1px solid #fecaca">{slot}</td>
    </tr>
    <tr style="background:#fee2e2">
      <td style="padding:11px 14px;border:1px solid #fca5a5;font-weight:700">Status</td>
      <td style="padding:11px 14px;border:1px solid #fca5a5">
        <span style="background:#fee2e2;color:#dc2626;padding:3px 12px;border-radius:6px;font-weight:700">&#10007; CANCELLED</span>
      </td>
    </tr>
  </table>

  <div style="background:#fff7ed;border-left:4px solid #f97316;padding:14px 18px;border-radius:0 8px 8px 0;margin:20px 0">
    <p style="margin:0;font-weight:700;color:#c2410c;font-size:0.95em">Action Required</p>
    <p style="margin:8px 0 0;color:#555;font-size:0.9em">
      Please free up this slot in the shared calendar and notify any waitlisted users.
      The Action Centre has been updated automatically.
    </p>
  </div>

  <p style="color:#888;font-size:0.82em;border-top:1px solid #fecaca;padding-top:14px;margin-top:8px">
    Automated cancellation notification from INDMoney Advisor Suite.
    No investment advice implied.
  </p>
</div>
</body>
</html>"""


# ── Advisor Reschedule HTML email ─────────────────────────────────────────────

def _advisor_reschedule_html(payload: dict) -> str:
    """Orange-themed advisor email for booking reschedules."""
    code         = payload.get("booking_code", "—")
    topic        = payload.get("topic_label", payload.get("topic", "—"))
    date         = payload.get("date", "—")
    slot         = payload.get("slot_start_ist", payload.get("time", payload.get("slot", "—")))

    from phase7_pillar_c_hitl.mcp.config import config  # noqa: PLC0415

    gcal_href = _gcal_url(
        title=f"Advisor Q&A — {topic} [{code}]",
        date_iso=date if date != "—" else "2026-01-01",
        time_str=slot,
        description=f"INDMoney Advisor pre-booking (rescheduled).\\nBooking code: {code}\\nTopic: {topic}",
    )

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#333;max-width:680px;margin:auto;padding:16px">

<div style="background:linear-gradient(135deg,#d97706,#b45309);padding:28px 32px;border-radius:12px 12px 0 0">
  <h2 style="color:white;margin:0;font-size:1.4em">&#128260; Booking Rescheduled</h2>
  <p style="color:#fef3c7;margin:6px 0 0;font-size:0.92em">INDMoney Voice Scheduling Agent</p>
</div>

<div style="background:#ffffff;border:1px solid #fde68a;border-top:none;border-radius:0 0 12px 12px;padding:28px 32px">

  <p style="margin:0 0 16px">Dear <strong>{config.advisor_name}</strong>,</p>
  <p style="margin:0 0 20px;color:#555">The following appointment has been <strong style="color:#d97706">rescheduled</strong> by the investor via the voice agent.</p>

  <table style="border-collapse:collapse;width:100%;margin:0 0 20px">
    <tr style="background:#fef3c7">
      <td style="padding:11px 14px;border:1px solid #fde68a;font-weight:700;width:38%">Booking Code</td>
      <td style="padding:11px 14px;border:1px solid #fde68a">
        <span style="background:#fef3c7;color:#d97706;padding:3px 12px;border-radius:6px;font-weight:700;font-size:1.05em;letter-spacing:1px">{code}</span>
      </td>
    </tr>
    <tr>
      <td style="padding:11px 14px;border:1px solid #fde68a;font-weight:700">Topic</td>
      <td style="padding:11px 14px;border:1px solid #fde68a">{topic}</td>
    </tr>
    <tr style="background:#fef3c7">
      <td style="padding:11px 14px;border:1px solid #fde68a;font-weight:700">New Date</td>
      <td style="padding:11px 14px;border:1px solid #fde68a"><strong>{date}</strong></td>
    </tr>
    <tr>
      <td style="padding:11px 14px;border:1px solid #fde68a;font-weight:700">New Time (IST)</td>
      <td style="padding:11px 14px;border:1px solid #fde68a">{slot}</td>
    </tr>
    <tr style="background:#fef3c7">
      <td style="padding:11px 14px;border:1px solid #fde68a;font-weight:700">Status</td>
      <td style="padding:11px 14px;border:1px solid #fde68a">
        <span style="background:#fef3c7;color:#d97706;padding:3px 12px;border-radius:6px;font-weight:700">&#8635; RESCHEDULED</span>
      </td>
    </tr>
  </table>

  <a href="{gcal_href}" target="_blank"
     style="display:inline-block;background:#d97706;color:white;padding:11px 22px;
            border-radius:8px;text-decoration:none;font-weight:600;font-size:0.95em;margin-bottom:20px">
    &#128197; Update Google Calendar
  </a>

  <p style="color:#888;font-size:0.82em;border-top:1px solid #fde68a;padding-top:14px;margin-top:8px">
    Automated reschedule notification from INDMoney Advisor Suite.
    No investment advice implied.
  </p>
</div>
</body>
</html>"""


# ── User Cancellation Confirmation HTML email ─────────────────────────────────

def _user_cancellation_html(name: str, booking_code: str, topic_label: str) -> str:
    """Red-themed cancellation confirmation email for the investor."""
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;padding:16px">

<div style="background:linear-gradient(135deg,#dc2626,#991b1b);padding:28px 32px;border-radius:12px 12px 0 0">
  <h2 style="color:white;margin:0">&#128683; Appointment Cancelled</h2>
  <p style="color:#fecaca;margin:6px 0 0;font-size:0.92em">INDMoney Advisor Scheduling</p>
</div>

<div style="background:#ffffff;border:1px solid #fecaca;border-top:none;border-radius:0 0 12px 12px;padding:28px 32px">

  <p style="margin:0 0 16px">Dear <strong>{name}</strong>,</p>
  <p style="margin:0 0 20px;color:#555">Your advisor appointment has been successfully cancelled. Here are the details:</p>

  <table style="border-collapse:collapse;width:100%;margin:0 0 20px">
    <tr style="background:#fee2e2">
      <td style="padding:10px 14px;border:1px solid #fecaca;font-weight:600">Booking Code</td>
      <td style="padding:10px 14px;border:1px solid #fecaca">
        <span style="background:#fee2e2;color:#dc2626;padding:3px 12px;border-radius:6px;font-weight:700;font-size:1.05em;letter-spacing:1px">{booking_code}</span>
      </td>
    </tr>
    <tr>
      <td style="padding:10px 14px;border:1px solid #fecaca;font-weight:600">Topic</td>
      <td style="padding:10px 14px;border:1px solid #fecaca">{topic_label}</td>
    </tr>
    <tr style="background:#fee2e2">
      <td style="padding:10px 14px;border:1px solid #fecaca;font-weight:600">Status</td>
      <td style="padding:10px 14px;border:1px solid #fecaca">
        <span style="background:#fee2e2;color:#dc2626;padding:3px 12px;border-radius:6px;font-weight:700">&#10007; Cancelled</span>
      </td>
    </tr>
  </table>

  <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px 16px;font-size:0.9em;margin-top:4px">
    &#8505;&#65039; If you'd like to rebook, simply call us again and we'll find you a new slot.
  </div>

  <p style="color:#6b7280;font-size:0.82em;margin-top:20px;border-top:1px solid #fecaca;padding-top:14px">
    If you did not request this cancellation, please contact us immediately.<br>
    Quote your booking code: <strong>{booking_code}</strong>
  </p>
</div>
</body>
</html>"""


def send_user_cancellation_email(
    to_name: str,
    to_email: str,
    booking_code: str,
    topic_label: str,
) -> dict:
    """Send a cancellation confirmation email to the investor.

    Uses Brevo HTTPS API when BREVO_API_KEY is set, otherwise falls back to SMTP.
    """
    import os as _os
    import requests as _requests

    subject = f"Appointment Cancelled — {booking_code} | {topic_label}"
    plain = (
        f"Dear {to_name},\n\n"
        f"Your advisor appointment has been cancelled.\n\n"
        f"Booking Code : {booking_code}\n"
        f"Topic        : {topic_label}\n\n"
        f"If you'd like to rebook, please call us again.\n"
        f"If you did not request this cancellation, please contact us.\n"
    )
    html = _user_cancellation_html(to_name, booking_code, topic_label)

    brevo_key = _os.environ.get("BREVO_API_KEY", "").strip()
    if brevo_key:
        resp = _requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": brevo_key,
                "content-type": "application/json",
            },
            json={
                "sender":      {"name": "AdvisorBot", "email": config.gmail_address},
                "to":          [{"email": to_email, "name": to_name or to_email}],
                "subject":     subject,
                "htmlContent": html,
                "textContent": plain,
            },
            timeout=20,
        )
        if not resp.ok:
            raise RuntimeError(f"brevo API {resp.status_code}: {resp.text[:200]}")
        return {"to": to_email, "booking_code": booking_code, "provider": "brevo"}

    if not config.gmail_app_password:
        raise RuntimeError(
            "Neither BREVO_API_KEY nor GMAIL_APP_PASSWORD is set."
        )
    msg = MIMEMultipart("alternative")
    msg["From"]    = f"AdvisorBot <{config.gmail_address}>"
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP(config.gmail_smtp_host, config.gmail_smtp_port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(config.gmail_address, config.gmail_app_password)
        smtp.sendmail(config.gmail_address, to_email, msg.as_bytes())
    return {"to": to_email, "booking_code": booking_code, "provider": "smtp"}




def _user_confirmation_html(name: str, booking_code: str, topic_label: str, slot_ist: str, date_str: str = "") -> str:
    # Parse date and time for Google Calendar button
    # slot_ist may be like "Tuesday, 2026-05-06 at 2:00 PM IST" or "2026-05-06 at 2:00 PM IST"
    gcal_date = date_str
    gcal_time = slot_ist
    if not gcal_date:
        dm = re.search(r"(\d{4}-\d{2}-\d{2})", slot_ist)
        if dm:
            gcal_date = dm.group(1)
    tm = re.search(r"at\s+([\d:]+\s*(?:AM|PM|am|pm)?)", slot_ist, re.IGNORECASE)
    if tm:
        gcal_time = tm.group(1).strip()

    gcal_href = _gcal_url(
        title=f"Advisor Appointment — {topic_label} [{booking_code}]",
        date_iso=gcal_date or "2026-01-01",
        time_str=gcal_time,
        description=f"INDMoney Advisor Q&A Session.\nTopic: {topic_label}\nBooking code: {booking_code}",
    ) if gcal_date else "#"

    # Display date row only if we have a date
    date_row = ""
    if gcal_date:
        date_row = f"""
    <tr style="background:#f5f3ff">
      <td style="padding:10px 14px;border:1px solid #ede9fe;font-weight:600">Date</td>
      <td style="padding:10px 14px;border:1px solid #ede9fe"><strong>{gcal_date}</strong></td>
    </tr>"""

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;padding:16px">

<div style="background:linear-gradient(135deg,#8b5cf6,#6d28d9);padding:28px 32px;border-radius:12px 12px 0 0">
  <h2 style="color:white;margin:0">&#128197; Appointment Confirmed</h2>
  <p style="color:#ede9fe;margin:6px 0 0;font-size:0.92em">INDMoney Advisor Scheduling</p>
</div>

<div style="background:#ffffff;border:1px solid #ede9fe;border-top:none;border-radius:0 0 12px 12px;padding:28px 32px">

  <p style="margin:0 0 16px">Dear <strong>{name}</strong>,</p>
  <p style="margin:0 0 20px;color:#555">Your advisor appointment has been confirmed. Here are your booking details:</p>

  <table style="border-collapse:collapse;width:100%;margin:0 0 20px">
    <tr style="background:#f5f3ff">
      <td style="padding:10px 14px;border:1px solid #ede9fe;font-weight:600">Booking Code</td>
      <td style="padding:10px 14px;border:1px solid #ede9fe">
        <span style="background:#ede9fe;color:#6d28d9;padding:3px 12px;border-radius:6px;font-weight:700;font-size:1.05em;letter-spacing:1px">{booking_code}</span>
      </td>
    </tr>
    <tr>
      <td style="padding:10px 14px;border:1px solid #ede9fe;font-weight:600">Topic</td>
      <td style="padding:10px 14px;border:1px solid #ede9fe">{topic_label}</td>
    </tr>
    {date_row}
    <tr>
      <td style="padding:10px 14px;border:1px solid #ede9fe;font-weight:600">Time (IST)</td>
      <td style="padding:10px 14px;border:1px solid #ede9fe">{slot_ist}</td>
    </tr>
    <tr style="background:#f5f3ff">
      <td style="padding:10px 14px;border:1px solid #ede9fe;font-weight:600">Status</td>
      <td style="padding:10px 14px;border:1px solid #ede9fe">
        <span style="background:#e6f4ea;color:#137333;padding:3px 12px;border-radius:6px;font-weight:700">&#10003; Confirmed</span>
      </td>
    </tr>
  </table>

  <a href="{gcal_href}" target="_blank"
     style="display:inline-block;background:#8b5cf6;color:white;padding:12px 24px;
            border-radius:8px;text-decoration:none;font-weight:600;font-size:0.95em;margin-bottom:20px">
    &#128197; Add to Google Calendar
  </a>

  <div style="background:#fef9c3;border:1px solid #fde68a;border-radius:8px;padding:12px 16px;font-size:0.9em;margin-top:4px">
    &#8505;&#65039; This is an <strong>informational consultation</strong> only — not investment advice.
    Your advisor will confirm the meeting details closer to the date.
  </div>

  <p style="color:#6b7280;font-size:0.82em;margin-top:20px;border-top:1px solid #f3e8ff;padding-top:14px">
    If you did not request this booking, please ignore this email.<br>
    To reschedule or cancel, call us and quote your booking code: <strong>{booking_code}</strong>
  </p>
</div>
</body>
</html>"""


# ── Legacy advisor HTML (used by draft_approval_email / MCP tool) ─────────────

def _html_body(payload: MCPPayload, event_id: str | None) -> str:
    """Build advisor HTML email from MCPPayload (used by draft_approval_email)."""
    gcal_href = _gcal_url(
        title=f"Advisor Q&A — {payload.topic_label} [{payload.booking_code}]",
        date_iso=payload.created_at_ist or "2026-01-01",
        time_str=payload.slot_start_ist,
        description=f"INDMoney Advisor pre-booking.\nBooking code: {payload.booking_code}",
    )
    cal_row = (
        f"<tr><td style='padding:10px 14px;border:1px solid #ddd;font-weight:700'>Calendar Event</td>"
        f"<td style='padding:10px 14px;border:1px solid #ddd'>{event_id}</td></tr>"
        if event_id else ""
    )
    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#333;max-width:680px;margin:auto;padding:16px">
<div style="background:linear-gradient(135deg,#1a73e8,#0d47a1);padding:28px 32px;border-radius:12px 12px 0 0">
  <h2 style="color:white;margin:0">&#128197; New Advisor Pre-Booking</h2>
  <p style="color:#bbdefb;margin:6px 0 0;font-size:0.92em">INDMoney Voice Scheduling Agent</p>
</div>
<div style="background:#ffffff;border:1px solid #e8eaed;border-top:none;border-radius:0 0 12px 12px;padding:28px 32px">
  <p>Dear <strong>{config.advisor_name}</strong>,</p>
  <p style="color:#555">A new appointment has been pre-booked. Please review and approve the actions in the Action Centre.</p>
  <table style="border-collapse:collapse;width:100%;margin:0 0 20px">
    <tr style="background:#e8f0fe">
      <td style="padding:11px 14px;border:1px solid #c5cae9;font-weight:700;width:38%">Booking Code</td>
      <td style="padding:11px 14px;border:1px solid #c5cae9">
        <span style="background:#e8f0fe;color:#1a73e8;padding:3px 12px;border-radius:6px;font-weight:700">{payload.booking_code}</span>
      </td>
    </tr>
    <tr>
      <td style="padding:11px 14px;border:1px solid #e0e0e0;font-weight:700">Topic</td>
      <td style="padding:11px 14px;border:1px solid #e0e0e0">{payload.topic_label}</td>
    </tr>
    <tr style="background:#e8f0fe">
      <td style="padding:11px 14px;border:1px solid #c5cae9;font-weight:700">Date</td>
      <td style="padding:11px 14px;border:1px solid #c5cae9"><strong>{payload.created_at_ist}</strong></td>
    </tr>
    <tr>
      <td style="padding:11px 14px;border:1px solid #e0e0e0;font-weight:700">Time (IST)</td>
      <td style="padding:11px 14px;border:1px solid #e0e0e0">{payload.slot_start_ist}</td>
    </tr>
    <tr style="background:#e8f0fe">
      <td style="padding:11px 14px;border:1px solid #c5cae9;font-weight:700">Status</td>
      <td style="padding:11px 14px;border:1px solid #c5cae9">
        <span style="background:#e6f4ea;color:#137333;padding:3px 12px;border-radius:6px;font-weight:700">&#10003; CONFIRMED</span>
      </td>
    </tr>
    {cal_row}
    <tr>
      <td style="padding:11px 14px;border:1px solid #e0e0e0;font-weight:700">Call ID</td>
      <td style="padding:11px 14px;border:1px solid #e0e0e0;color:#888;font-size:0.9em">{payload.call_id}</td>
    </tr>
  </table>
  <a href="{gcal_href}" target="_blank"
     style="display:inline-block;background:#1a73e8;color:white;padding:11px 22px;
            border-radius:8px;text-decoration:none;font-weight:600;font-size:0.95em;margin-bottom:20px">
    &#128197; Add to Google Calendar
  </a>
  <p style="color:#888;font-size:0.82em;border-top:1px solid #eee;padding-top:14px;margin-top:8px">
    Automated pre-booking notification from INDMoney Advisor Suite. No PII was shared on the voice call.
    No investment advice implied.
  </p>
</div>
</body>
</html>"""


def _create_draft_sync(payload: MCPPayload, event_id: str | None) -> dict:
    msg = MIMEMultipart("alternative")
    msg["From"]    = config.gmail_address
    msg["To"]      = config.advisor_email
    msg["Subject"] = (
        f"[Pre-Booking] {payload.topic_label} — "
        f"{payload.booking_code} — {payload.slot_start_ist}"
    )
    msg["X-BookingCode"] = payload.booking_code
    msg["X-CallID"]      = payload.call_id

    plain = (
        f"Pre-Booking: {payload.topic_label}\n"
        f"Booking Code: {payload.booking_code}\n"
        f"Date:         {payload.created_at_ist}\n"
        f"Slot:         {payload.slot_start_ist}\n"
        f"Advisor:      {payload.advisor_id}\n"
        f"Call ID:      {payload.call_id}\n"
    )
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(_html_body(payload, event_id), "html"))

    with imaplib.IMAP4_SSL(_IMAP_HOST) as imap:
        imap.login(config.gmail_address, config.gmail_app_password)
        status, data = imap.append(
            '"[Gmail]/Drafts"',
            "\\Draft",
            imaplib.Time2Internaldate(time.time()),
            msg.as_bytes(),
        )
        if status != "OK":
            raise RuntimeError(f"IMAP APPEND failed: {status} — {data}")
        draft_uid = data[0].decode("utf-8") if data and data[0] else "unknown"

    return {"draft_id": draft_uid, "to": config.advisor_email}


def send_user_confirmation(
    to_name: str,
    to_email: str,
    booking_code: str,
    topic_label: str,
    slot_ist: str,
    date_str: str = "",
) -> dict:
    """Send an appointment confirmation email to the user.

    Uses Brevo HTTPS API when BREVO_API_KEY is set (Railway-friendly),
    otherwise falls back to Gmail SMTP for local dev.
    """
    import os as _os
    import requests as _requests

    subject = f"Appointment Confirmed — {booking_code} | {topic_label}"
    plain = (
        f"Dear {to_name},\n\n"
        f"Your advisor appointment is confirmed.\n\n"
        f"Booking Code : {booking_code}\n"
        f"Topic        : {topic_label}\n"
        + (f"Date         : {date_str}\n" if date_str else "")
        + f"Time (IST)   : {slot_ist}\n\n"
        f"An advisor will confirm the meeting details closer to the date.\n"
        f"This is an informational consultation only — not investment advice.\n\n"
        f"To reschedule or cancel, call us and quote your booking code.\n"
    )
    html = _user_confirmation_html(to_name, booking_code, topic_label, slot_ist, date_str)

    # ── Path 1: Brevo HTTPS (Railway-friendly) ─────────────────────────────
    brevo_key = _os.environ.get("BREVO_API_KEY", "").strip()
    if brevo_key:
        resp = _requests.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "accept": "application/json",
                "api-key": brevo_key,
                "content-type": "application/json",
            },
            json={
                "sender":      {"name": "AdvisorBot", "email": config.gmail_address},
                "to":          [{"email": to_email, "name": to_name or to_email}],
                "subject":     subject,
                "htmlContent": html,
                "textContent": plain,
            },
            timeout=20,
        )
        if not resp.ok:
            raise RuntimeError(f"brevo API {resp.status_code}: {resp.text[:200]}")
        return {"to": to_email, "booking_code": booking_code, "provider": "brevo"}

    # ── Path 2: SMTP fallback (works locally, blocked on Railway) ──────────
    if not config.gmail_app_password:
        raise RuntimeError(
            "Neither BREVO_API_KEY nor GMAIL_APP_PASSWORD is set. "
            "On Railway, set BREVO_API_KEY (SMTP is blocked)."
        )
    msg = MIMEMultipart("alternative")
    msg["From"]    = f"AdvisorBot <{config.gmail_address}>"
    msg["To"]      = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))
    with smtplib.SMTP(config.gmail_smtp_host, config.gmail_smtp_port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(config.gmail_address, config.gmail_app_password)
        smtp.sendmail(config.gmail_address, to_email, msg.as_bytes())

    return {"to": to_email, "booking_code": booking_code, "provider": "smtp"}


def send_waitlist_notification(
    to_name: str,
    to_email: str,
    waitlist_code: str,
    topic_label: str,
    slot_ist: str,
) -> dict:
    """Send a slot-opened notification to a waitlisted user."""
    html = f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;color:#333;max-width:600px;margin:auto;padding:16px">
<div style="background:linear-gradient(135deg,#16a34a,#15803d);padding:28px 32px;border-radius:12px 12px 0 0">
  <h2 style="color:white;margin:0">&#127881; Good News — Your Slot is Available!</h2>
  <p style="color:#dcfce7;margin:6px 0 0;font-size:0.92em">INDMoney Advisor Scheduling — Waitlist Update</p>
</div>
<div style="background:#ffffff;border:1px solid #dcfce7;border-top:none;border-radius:0 0 12px 12px;padding:28px 32px">
  <p>Dear <strong>{to_name}</strong>,</p>
  <p style="color:#555">A slot has opened up matching your preference. Please call us back to confirm your booking.</p>
  <table style="border-collapse:collapse;width:100%;margin:0 0 20px">
    <tr style="background:#f0fdf4">
      <td style="padding:10px 14px;border:1px solid #dcfce7;font-weight:600">Waitlist Code</td>
      <td style="padding:10px 14px;border:1px solid #dcfce7">
        <span style="background:#dcfce7;color:#15803d;padding:3px 12px;border-radius:6px;font-weight:700">{waitlist_code}</span>
      </td>
    </tr>
    <tr>
      <td style="padding:10px 14px;border:1px solid #dcfce7;font-weight:600">Topic</td>
      <td style="padding:10px 14px;border:1px solid #dcfce7">{topic_label}</td>
    </tr>
    <tr style="background:#f0fdf4">
      <td style="padding:10px 14px;border:1px solid #dcfce7;font-weight:600">Available Slot</td>
      <td style="padding:10px 14px;border:1px solid #dcfce7">{slot_ist} <span style="color:#15803d;font-size:0.88em">(IST)</span></td>
    </tr>
  </table>
  <p style="background:#fef9c3;border:1px solid #fde68a;border-radius:8px;padding:12px 16px;font-size:0.9em">
    &#8505;&#65039; This slot is being held for you. Please call us back to confirm before the hold expires.
    Quote your waitlist code: <strong>{waitlist_code}</strong>
  </p>
  <p style="color:#6b7280;font-size:0.82em;margin-top:20px;border-top:1px solid #dcfce7;padding-top:14px">
    If you no longer need this appointment, no action is required.
  </p>
</div>
</body>
</html>"""

    plain = (
        f"Dear {to_name},\n\n"
        f"A slot has opened up matching your waitlist preference.\n\n"
        f"Waitlist Code : {waitlist_code}\n"
        f"Topic         : {topic_label}\n"
        f"Available Slot: {slot_ist} (IST)\n\n"
        f"Please call us back to confirm your booking. Quote your waitlist code: {waitlist_code}\n"
    )

    msg = MIMEMultipart("alternative")
    msg["From"]    = f"AdvisorBot <{config.gmail_address}>"
    msg["To"]      = to_email
    msg["Subject"] = f"Slot Available — {waitlist_code} | {topic_label}"

    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(config.gmail_smtp_host, config.gmail_smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(config.gmail_address, config.gmail_app_password)
        smtp.sendmail(config.gmail_address, to_email, msg.as_bytes())

    return {"to": to_email, "waitlist_code": waitlist_code}


async def draft_approval_email(payload: MCPPayload, event_id: str | None = None) -> ToolResult:
    t0 = time.monotonic()
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, _create_draft_sync, payload, event_id
        )
        return ToolResult(success=True, data=data, duration_ms=(time.monotonic() - t0) * 1000)
    except Exception as exc:
        return ToolResult(success=False, error=str(exc), duration_ms=(time.monotonic() - t0) * 1000)
