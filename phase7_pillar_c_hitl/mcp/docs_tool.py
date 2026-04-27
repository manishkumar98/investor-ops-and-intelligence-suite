"""
MCP — Google Docs tool.
Appends a formatted notes entry to the shared Advisor Pre-Bookings Google Doc.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime

from google.oauth2 import service_account
from googleapiclient.discovery import build

from .config import config

_SCOPES = ["https://www.googleapis.com/auth/documents"]


def _build_service():
    creds = service_account.Credentials.from_service_account_info(
        config.service_account, scopes=_SCOPES
    )
    return build("docs", "v1", credentials=creds)


def _format_entry(action_payload: dict) -> str:
    """Convert a notes_append payload dict into a human-readable block."""
    doc_title = action_payload.get("doc_title", "Notes")
    entry     = action_payload.get("entry", action_payload)

    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "\n" + "─" * 60,
        f"📝  {doc_title}",
        f"Appended: {now}",
    ]

    # M3 voice booking fields
    for key, label in [
        ("booking_code", "Booking Code"),
        ("topic",        "Topic"),
        ("slot",         "Slot"),
        ("date",         "Date"),
        ("status",       "Status"),
    ]:
        val = entry.get(key)
        if val and val != "—":
            lines.append(f"{label}: {val}")

    # M2 pipeline fields
    top_themes = entry.get("top_themes") or entry.get("top_3_themes")
    if top_themes:
        lines.append(f"Top Themes: {', '.join(top_themes)}")

    fee_scenario = entry.get("fee_scenario")
    if fee_scenario:
        lines.append(f"Fee Scenario: {fee_scenario}")

    weekly_pulse = entry.get("weekly_pulse", "")
    if weekly_pulse:
        snippet = weekly_pulse[:300] + ("…" if len(weekly_pulse) > 300 else "")
        lines.append(f"Pulse Summary: {snippet}")

    lines.append("─" * 60 + "\n")
    return "\n".join(lines)


def _append_to_doc_sync(doc_id: str, text: str) -> dict:
    service = _build_service()
    # Find end index of document body
    doc = service.documents().get(documentId=doc_id).execute()
    body_content = doc.get("body", {}).get("content", [])
    end_index = body_content[-1].get("endIndex", 1) - 1 if body_content else 1

    requests = [
        {
            "insertText": {
                "location": {"index": end_index},
                "text": text,
            }
        }
    ]
    result = service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": requests},
    ).execute()

    return {
        "doc_id":    doc_id,
        "doc_title": doc.get("title", ""),
        "replies":   result.get("replies", []),
    }


def append_notes_sync(payload: dict) -> dict:
    """Synchronous wrapper — formats payload and appends to the configured Google Doc."""
    doc_id = config.doc_id
    if not doc_id:
        raise RuntimeError("GOOGLE_DOC_ID is not set in environment")
    text = _format_entry(payload)
    return _append_to_doc_sync(doc_id, text)


async def append_notes(payload: dict) -> dict:
    """Async wrapper for append_notes_sync."""
    t0 = time.monotonic()
    try:
        data = await asyncio.get_event_loop().run_in_executor(
            None, append_notes_sync, payload
        )
        return {"success": True, "data": data, "duration_ms": (time.monotonic() - t0) * 1000}
    except Exception as exc:
        return {"success": False, "error": str(exc), "duration_ms": (time.monotonic() - t0) * 1000}
