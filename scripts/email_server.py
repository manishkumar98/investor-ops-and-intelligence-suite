"""Lightweight FastAPI server for the dashboard's Send Email button.

Runs in a background thread on port 8502 (started from app.py).
POST /api/send-email  — sends the weekly pulse email via Brevo → Gmail SMTP fallback.
"""
import json
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from threading import Thread

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

app = FastAPI(title="Investor Ops Email API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


class EmailRequest(BaseModel):
    name: str
    email: EmailStr


def _md_to_html(text: str) -> str:
    """Convert **bold** markdown and strip leading bullet chars to clean HTML."""
    import re
    text = text.lstrip("•–- ").strip()
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return text


def _scenario_title(raw: str) -> str:
    """'exit_load' → 'Exit Load Explainer'."""
    title = raw.replace("_", " ").title()
    if not any(w in title.lower() for w in ("explainer", "fee", "load", "charge")):
        title += " — Fee Explainer"
    return title


def _build_html(pulse: dict, fee: dict, recipient_name: str) -> str:
    quotes = pulse.get("quotes", [])
    themes = pulse.get("top_3_themes", [])
    action_ideas = pulse.get("action_ideas", [])
    note = pulse.get("weekly_note", "")

    quotes_html = "".join(
        f"<p style='font-size:17px;line-height:1.6;color:#333;border-left:3px solid #C9A84C;"
        f"padding-left:16px;margin:20px 0;'>\"{q}\"</p>"
        for q in quotes
    )
    themes_html = "".join(f"<li style='margin-bottom:10px;font-size:15px;'>{t}</li>" for t in themes)
    actions_html = "".join(
        f"<li style='margin-bottom:10px;font-size:15px;color:#444;line-height:1.5;'>{a}</li>"
        for a in action_ideas
    )

    bullets = fee.get("bullets", fee.get("explanation_bullets", []))
    sources = fee.get("sources", fee.get("source_links", []))
    raw_scenario = fee.get("scenario", fee.get("scenario_name", "Fee Explainer"))
    scenario = _scenario_title(raw_scenario)

    fee_html = "".join(
        f"<li style='margin-bottom:10px;font-size:15px;color:#333;line-height:1.6;'>{_md_to_html(b)}</li>"
        for b in bullets
    )
    src_html = "".join(
        f"<a href='{s}' style='display:block;font-size:13px;color:#C9A84C;margin-top:6px;"
        f"word-break:break-all;text-decoration:none;'>"
        f"&#8599; {s.split('//')[-1].split('/')[0]}"
        f"</a>"
        for s in sources
    )

    today = datetime.today().strftime("%B %d, %Y")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
</head>
<body style="font-family:Inter,sans-serif;background:#fff;margin:0;padding:0;">
<div style="max-width:700px;margin:0 auto;padding:40px 24px;">
  <div style="background:#0A0C14;padding:32px;border-radius:12px;text-align:center;margin-bottom:32px;">
    <h1 style="color:#C9A84C;margin:0;font-size:24px;">Investor Ops & Intelligence Suite</h1>
    <p style="color:#F5F0E8;margin:8px 0 0;">Weekly Review Pulse — {today}</p>
  </div>
  <p style="font-size:17px;color:#333;">Hi {recipient_name},</p>
  <p style="font-size:15px;color:#555;">Here is your INDMoney weekly review pulse.</p>

  <h2 style="font-size:18px;color:#0A0C14;border-bottom:2px solid #C9A84C;padding-bottom:8px;">User Quotes</h2>
  {quotes_html}

  <h2 style="font-size:18px;color:#0A0C14;border-bottom:2px solid #C9A84C;padding-bottom:8px;margin-top:32px;">Weekly Note</h2>
  <p style="font-size:16px;line-height:1.7;color:#333;">{note}</p>

  <table width="100%" style="margin-top:32px;">
    <tr>
      <td width="50%" valign="top" style="padding-right:20px;">
        <h2 style="font-size:17px;color:#0A0C14;">Top Themes</h2>
        <ul style="padding-left:18px;">{themes_html}</ul>
      </td>
      <td width="50%" valign="top" style="padding-left:20px;border-left:1px solid #eee;">
        <h2 style="font-size:17px;color:#0A0C14;">Action Ideas</h2>
        <ul style="padding-left:18px;">{actions_html}</ul>
      </td>
    </tr>
  </table>

  <div style="margin-top:32px;border-top:1px solid #eee;padding-top:24px;background:#f9f7f2;
       border-radius:8px;padding:24px;">
    <h2 style="font-size:17px;color:#0A0C14;margin-top:0;">{scenario}</h2>
    <ul style="padding-left:20px;margin:0 0 16px;">{fee_html}</ul>
    <p style="font-size:12px;font-weight:600;color:#666;margin:0 0 4px;text-transform:uppercase;
       letter-spacing:0.5px;">Sources</p>
    {src_html}
  </div>

  <p style="font-size:12px;color:#999;margin-top:40px;text-align:center;">
    Generated by Investor Ops & Intelligence Suite
  </p>
</div>
</body></html>"""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/send-email")
def send_email(req: EmailRequest):
    sender = os.getenv("EMAIL_SENDER")
    password = os.getenv("EMAIL_PASSWORD")
    brevo_key = os.getenv("BREVO_API_KEY")

    pulse = {}
    fee = {}
    try:
        pulse_path = DATA / "pulse_latest.json"
        fee_path = DATA / "fee_latest.json"
        if pulse_path.exists():
            pulse = json.loads(pulse_path.read_text())
        if fee_path.exists():
            fee = json.loads(fee_path.read_text())
    except Exception:
        pass

    today = datetime.today().strftime("%B %d, %Y")
    subject = f"Weekly INDMoney Review Pulse — {today}"
    html_body = _build_html(pulse, fee, req.name)
    plain_body = f"Hi {req.name},\n\nHere is your INDMoney weekly review pulse for {today}.\n\nWeekly Note:\n{pulse.get('weekly_note', '')}"

    try:
        if brevo_key and sender:
            resp = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                headers={"accept": "application/json", "api-key": brevo_key, "content-type": "application/json"},
                json={
                    "sender": {"name": "Investor Ops Suite", "email": sender},
                    "to": [{"email": req.email, "name": req.name}],
                    "subject": subject,
                    "htmlContent": html_body,
                    "textContent": plain_body,
                },
                timeout=15,
            )
            resp.raise_for_status()
        elif sender and password:
            msg = MIMEMultipart("alternative")
            msg["From"] = sender
            msg["To"] = req.email
            msg["Subject"] = subject
            msg.attach(MIMEText(plain_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
                server.starttls()
                server.login(sender, password)
                server.sendmail(sender, req.email, msg.as_string())
        else:
            raise HTTPException(status_code=500, detail="Email credentials not configured.")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"status": "success", "message": f"Email sent to {req.email}"}


_server_started = False


def start_email_server(port: int = 8510) -> None:
    """Start uvicorn in a daemon thread — safe to call multiple times."""
    global _server_started
    if _server_started:
        return
    _server_started = True

    import uvicorn

    def _run():
        try:
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
        except Exception:
            pass  # port already in use from another process

    t = Thread(target=_run, daemon=True)
    t.start()


if __name__ == "__main__":
    import uvicorn
    print("Starting Investor Ops Email Server on port 8510…")
    uvicorn.run(app, host="127.0.0.1", port=8510, log_level="info")
