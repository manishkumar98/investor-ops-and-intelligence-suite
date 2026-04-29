"""
Phase 7 — MCP Super-Agent

Claude acts as the orchestrating agent: given booking context + M2 market data,
it uses tool_use (Model Context Protocol) to decide which tools to call and
constructs all payloads — including writing the advisor email with weekly pulse.

The resulting tool_use blocks are queued in session["mcp_queue"] for HITL
approval before any Google API is touched.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import anthropic

# ── MCP Tool Definitions (Claude tool_use schemas) ─────────────────────────

TOOLS: list[dict] = [
    {
        "name": "calendar_hold",
        "description": (
            "Create a tentative calendar hold for the advisor slot. "
            "Call this to block the advisor's calendar for the booked meeting."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title":        {"type": "string", "description": "Calendar event title including topic and booking code"},
                "date":         {"type": "string", "description": "Date of the meeting"},
                "time":         {"type": "string", "description": "Time slot in IST"},
                "tz":           {"type": "string", "description": "Timezone, always IST"},
                "topic":        {"type": "string", "description": "Topic key"},
                "booking_code": {"type": "string", "description": "Unique booking code e.g. NL-A742"},
            },
            "required": ["title", "date", "time", "booking_code"],
        },
    },
    {
        "name": "notes_append",
        "description": (
            "Append a structured booking entry to the Advisor Pre-Bookings Google Doc. "
            "Include the M2 market context (weekly_pulse, top_3_themes, fee_scenario) so "
            "the advisor understands current customer sentiment before the meeting. "
            "This cross-pillar link (M2 → advisor notes) is mandatory."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "doc_title": {"type": "string", "description": "Google Doc title"},
                "entry": {
                    "type": "object",
                    "properties": {
                        "date":         {"type": "string"},
                        "topic":        {"type": "string"},
                        "slot":         {"type": "string"},
                        "booking_code": {"type": "string"},
                        "status":       {"type": "string"},
                        "top_3_themes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Top 3 customer complaint themes from M2 review pipeline",
                        },
                        "weekly_pulse": {
                            "type": "string",
                            "description": "Weekly pulse excerpt (≤300 chars) from M2 pipeline",
                        },
                        "fee_scenario": {
                            "type": "string",
                            "description": "Top fee context bullet from M2 fee explainer",
                        },
                    },
                    "required": ["date", "topic", "booking_code", "status"],
                },
            },
            "required": ["doc_title", "entry"],
        },
    },
    {
        "name": "email_draft",
        "description": (
            "Draft the pre-booking alert email to the advisor. "
            "The email MUST include a dedicated 'Market Context' section containing "
            "the weekly pulse summary and top customer themes from M2. "
            "This is the key cross-pillar integration: M2 customer intelligence → advisor preparation. "
            "Also include meeting details, fee context, and a no-investment-advice disclaimer. "
            "Use 'Dear Advisor,' as the salutation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "Email subject, e.g. 'Pre-Booking Alert: KYC / Onboarding — 2026-05-05 @ 10:00 AM IST'",
                },
                "booking_code":   {"type": "string"},
                "topic_label":    {"type": "string", "description": "Human-readable topic name"},
                "slot_start_ist": {"type": "string", "description": "Slot time in IST"},
                "body": {
                    "type": "string",
                    "description": (
                        "Full plain-text email body. Must contain sections: "
                        "MEETING DETAILS, MARKET CONTEXT (with top themes + weekly pulse), "
                        "FEE CONTEXT, and a disclaimer. Salutation: 'Dear Advisor,'"
                    ),
                },
            },
            "required": ["subject", "booking_code", "body"],
        },
    },
    {
        "name": "sheet_entry",
        "description": "Log the confirmed booking in Google Sheets for tracking and audit.",
        "input_schema": {
            "type": "object",
            "properties": {
                "booking_code":   {"type": "string"},
                "topic_key":      {"type": "string"},
                "topic_label":    {"type": "string"},
                "slot_start_ist": {"type": "string"},
                "date":           {"type": "string"},
                "status":         {"type": "string"},
                "call_id":        {"type": "string"},
            },
            "required": ["booking_code", "topic_key", "date", "status"],
        },
    },
]


def run(booking_detail: dict, session: dict) -> list[dict]:
    """
    Invoke Claude as the MCP super-agent.

    Claude receives booking context + M2 weekly pulse, then calls all 4 tools
    via tool_use to generate the HITL action queue. Returns a list of action
    dicts (with agent="claude-sonnet-4-6") ready for session["mcp_queue"].

    Falls back to an empty list on failure so voice_agent uses legacy path.
    """
    pulse       = session.get("weekly_pulse", "")
    top_3       = session.get("top_3_themes", [])
    fee_bullets = session.get("fee_bullets", [])
    fee_sources = session.get("fee_sources", [])
    top_theme   = session.get("top_theme", "")

    market_ctx  = " ".join(pulse.split()[:150]) if pulse else "No pulse data available this week."
    themes_line = " | ".join(f"#{i+1} {t}" for i, t in enumerate(top_3[:3])) if top_3 else "Not available"
    fee_ctx     = fee_bullets[0] if fee_bullets else "Fee information not available."
    fee_src     = ", ".join(fee_sources[:2]) if fee_sources else ""

    booking_code = booking_detail.get("booking_code", "")
    topic_label  = booking_detail.get("topic_label", booking_detail.get("topic", ""))
    date_str     = booking_detail.get("date", "")
    slot_str     = booking_detail.get("slot", booking_detail.get("time", ""))
    call_id      = booking_detail.get("call_id", "N/A")

    system_prompt = (
        "You are a booking completion super-agent for INDMoney's advisor scheduling system. "
        "A voice call has just ended with a confirmed appointment booking. "
        "Your job is to call ALL FOUR tools to complete the post-booking workflow:\n"
        "1. calendar_hold — block the advisor's calendar for the slot\n"
        "2. notes_append — write booking entry + M2 market context to the advisor doc\n"
        "3. email_draft — draft the pre-booking alert email WITH a Market Context section\n"
        "4. sheet_entry — log the booking in Google Sheets\n\n"
        "CRITICAL REQUIREMENT: The email body MUST include a 'MARKET CONTEXT' section "
        "that contains the top customer themes and weekly pulse excerpt. "
        "This is the cross-pillar M2→M3 integration that lets advisors understand "
        "what customers are complaining about before the meeting.\n\n"
        "Rules: No investment advice. Use plain business English. "
        "Salutation must be 'Dear Advisor,'. All 4 tools must be called."
    )

    user_message = (
        f"Booking confirmed — please execute all 4 post-booking MCP actions.\n\n"
        f"── BOOKING DETAILS ──────────────────────────────\n"
        f"  Booking Code : {booking_code}\n"
        f"  Topic        : {topic_label}\n"
        f"  Date         : {date_str}\n"
        f"  Time Slot    : {slot_str} IST\n"
        f"  Status       : CONFIRMED\n"
        f"  Call ID      : {call_id}\n\n"
        f"── M2 MARKET CONTEXT (from this week's review pulse) ──\n"
        f"  Top Theme    : {top_theme}\n"
        f"  All Themes   : {themes_line}\n"
        f"  Weekly Pulse : {market_ctx}\n\n"
        f"── FEE CONTEXT ──────────────────────────────────\n"
        f"  {fee_ctx}\n"
        + (f"  Sources: {fee_src}\n" if fee_src else "")
    )

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=TOOLS,
            tool_choice={"type": "any"},
            messages=[{"role": "user", "content": user_message}],
        )

        actions: list[dict] = []
        for block in response.content:
            if block.type == "tool_use":
                actions.append({
                    "action_id":  str(uuid.uuid4()),
                    "type":       block.name,
                    "status":     "pending",
                    "created_at": datetime.utcnow().isoformat(),
                    "source":     "m3_voice",
                    "agent":      "claude-sonnet-4-6",
                    "payload":    block.input,
                })

        if actions:
            print(f"MCP super-agent: Claude generated {len(actions)} tool calls for booking {booking_code}")
            return actions

        print("WARNING: MCP super-agent returned no tool calls. Falling back to legacy.")

    except Exception as exc:
        print(f"WARNING: MCP super-agent failed ({exc}). Falling back to legacy enqueue.")

    return []
