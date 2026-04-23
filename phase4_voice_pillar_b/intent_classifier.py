"""Adapted from M3 phase2/src/dialogue/intent_router.py — Claude replaces Groq."""
import json
import logging
import os
import re

import anthropic

logger = logging.getLogger(__name__)

# ── Topic taxonomy (from M3 states.py) ──────────────────────────────────────
VALID_TOPICS = {
    "kyc_onboarding":  "KYC and Onboarding",
    "sip_mandates":    "SIP and Mandates",
    "statements_tax":  "Statements and Tax Documents",
    "withdrawals":     "Withdrawals and Timelines",
    "account_changes": "Account Changes and Nominee",
}

VALID_INTENTS = {
    "book_new", "reschedule", "cancel", "what_to_prepare",
    "check_availability", "refuse_advice", "refuse_pii",
    "timezone_query", "out_of_scope", "end_call",
}

# Keyword → topic mapping (from M3 intent_router._TOPIC_KEYWORDS)
_TOPIC_KEYWORDS: dict[str, list[str]] = {
    "kyc_onboarding":  ["kyc", "onboard", "know your customer", "verification",
                        "transfer fund", "fund transfer", "open account", "new account"],
    "sip_mandates":    ["sip", "mandate", "systematic", "monthly investment",
                        "auto-debit", "auto debit"],
    "statements_tax":  ["statement", "tax", "document", "form", "download",
                        "capital gain", "26as", "elss", "80c", "visa letter",
                        "investment summary"],
    "withdrawals":     ["withdraw", "redemption", "redeem", "payout", "money out",
                        "pension", "close account", "exit"],
    "account_changes": ["nominee", "account change", "update", "address", "bank",
                        "joint account", "beneficiary", "abroad", "mobile update"],
}

_WEEKDAY_NAMES = [
    "monday", "tuesday", "wednesday", "thursday", "friday",
    "saturday", "sunday", "mon", "tue", "wed", "thu", "fri", "sat", "sun",
]

_MONTH_PATTERN = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
_DATE_REGEX = re.compile(
    rf"({_MONTH_PATTERN}\s*\d{{1,2}}(?:st|nd|rd|th)?|"
    rf"\d{{1,2}}(?:st|nd|rd|th)?\s*{_MONTH_PATTERN}|"
    rf"\d{{1,2}}[/-]\d{{1,2}}(?:[/-]\d{{2,4}})?)",
    re.IGNORECASE,
)
_ORDINAL_REGEX = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.IGNORECASE)
_SPECIFIC_TIME_REGEX = re.compile(
    r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b|\b([01]?\d|2[0-3]):([0-5]\d)\b",
    re.IGNORECASE,
)

_SAFE_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

_LLM_SYSTEM = """You are an intent-extraction engine for a voice-based advisor appointment scheduler.
Classify the user's intent and extract slot values. NEVER give investment advice.

VALID INTENTS: book_new, reschedule, cancel, what_to_prepare, check_availability,
  refuse_advice, refuse_pii, timezone_query, out_of_scope, end_call

VALID TOPICS: kyc_onboarding, sip_mandates, statements_tax, withdrawals, account_changes

SLOTS: topic, day_preference, time_preference, existing_booking_code

Respond ONLY with valid JSON:
{
  "intent": "<intent>",
  "slots": {"topic": "<or omit>", "day_preference": "<or omit>",
            "time_preference": "<or omit>", "existing_booking_code": "<or omit>"},
  "speech": "<one short acknowledgement>",
  "compliance_flag": null
}
Set compliance_flag to "refuse_advice"/"refuse_pii"/"out_of_scope" when applicable."""

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


# ── Speech → booking code extractor (handles Whisper output variations) ──────
def _extract_booking_code(text: str) -> str | None:
    """From M3 intent_router._extract_booking_code — handles Whisper transcription noise."""
    upper = text.upper()
    m = re.search(r'\bNL[\s\-]*([A-Z0-9]\s*[A-Z0-9]\s*[A-Z0-9]\s*[A-Z0-9])\b', upper)
    if m:
        code = re.sub(r'\s+', '', m.group(1))
        if len(code) == 4:
            return f"NL-{code}"
    m = re.search(r'\bEN\s+EL[\s\-]*([A-Z0-9]\s*[A-Z0-9]\s*[A-Z0-9]\s*[A-Z0-9])\b', upper)
    if m:
        code = re.sub(r'\s+', '', m.group(1))
        if len(code) == 4:
            return f"NL-{code}"
    m = re.search(r'\bN\s+L[\s\-]*([A-Z0-9])\s+([A-Z0-9])\s+([A-Z0-9])\s+([A-Z0-9])\b', upper)
    if m:
        return f"NL-{m.group(1)}{m.group(2)}{m.group(3)}{m.group(4)}"
    return None


def _extract_day_preference(low: str) -> str | None:
    """From M3 intent_router._extract_day_preference."""
    for phrase in ("next week", "this week", "next month", "weekend"):
        if phrase in low:
            return phrase
    if "today" in low:
        return "today"
    if "day after tomorrow" in low:
        return "day after tomorrow"
    if "tomorrow" in low:
        return "tomorrow"
    for day in _WEEKDAY_NAMES:
        if f"next {day}" in low:
            return f"next {day}"
    m = _DATE_REGEX.search(low)
    if m:
        return m.group(0).strip()
    m = _ORDINAL_REGEX.search(low)
    if m:
        return m.group(0)
    for day in _WEEKDAY_NAMES:
        if re.search(rf"\b{day}\b", low):
            return day
    return None


def _extract_time_preference(low: str) -> str | None:
    """From M3 intent_router._extract_time_preference."""
    if any(w in low for w in ("any time", "anytime", "any slot", "flexible", "any")):
        return "any"
    m = _SPECIFIC_TIME_REGEX.search(low)
    if m:
        return m.group(0).strip()
    for band in ("late afternoon", "early morning", "afternoon", "morning", "evening", "noon", "midday"):
        if band in low:
            return band
    return None


def _rule_based(utterance: str) -> dict:
    """Rule-based fallback. From M3 _rule_based_parse, adapted for capstone."""
    low = utterance.lower()

    advice_words = ["invest", "stock", "return", "nifty", "sensex", "mutual fund",
                    "portfolio", "buy", "sell", "recommend", "crypto", "market crash",
                    "market prediction", "gold"]
    if any(w in low for w in advice_words):
        return {"intent": "refuse_advice", "slots": {}, "compliance_flag": "refuse_advice",
                "speech": "I can't provide investment advice."}

    end_words = ["leave", "bye", "goodbye", "don't want to book", "not interested",
                 "no thanks", "no thank you", "forget it", "never mind", "i'm done",
                 "don't want to proceed", "don't want to continue"]
    if any(w in low for w in end_words):
        return {"intent": "end_call", "slots": {}, "compliance_flag": None,
                "speech": "Thank you for calling. Happy to help whenever you're ready!"}

    intent = "book_new"
    if any(w in low for w in ["reschedule", "change my appointment", "move my booking"]):
        intent = "reschedule"
    elif any(w in low for w in ["cancel", "delete my booking", "abort"]):
        intent = "cancel"
    elif any(w in low for w in ["what to bring", "what to prepare", "documents needed",
                                  "what should i bring", "checklist"]):
        intent = "what_to_prepare"
    elif any(w in low for w in ["available", "availability", "when can i", "free slot"]):
        intent = "check_availability"

    slots: dict = {}
    for topic_key, keywords in _TOPIC_KEYWORDS.items():
        if any(k in low for k in keywords):
            slots["topic"] = topic_key
            break

    day = _extract_day_preference(low)
    if day:
        slots["day_preference"] = day
    time_pref = _extract_time_preference(low)
    if time_pref:
        slots["time_preference"] = time_pref
    code = _extract_booking_code(utterance)
    if code:
        slots["existing_booking_code"] = code

    return {"intent": intent, "slots": slots, "compliance_flag": None,
            "speech": "Got it, let me help you with that."}


def _parse_llm_json(raw: str) -> dict:
    text = re.sub(r"```(?:json)?", "", raw).strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("No JSON in LLM output")
    data = json.loads(m.group(0))

    intent = data.get("intent", "book_new")
    if intent not in VALID_INTENTS:
        intent = "book_new"

    raw_slots = data.get("slots", {})
    slots: dict = {}
    if raw_slots.get("topic") in VALID_TOPICS:
        slots["topic"] = raw_slots["topic"]
    for key in ("day_preference", "time_preference"):
        if raw_slots.get(key):
            slots[key] = raw_slots[key]
    if raw_slots.get("existing_booking_code"):
        code = _extract_booking_code(raw_slots["existing_booking_code"]) or raw_slots["existing_booking_code"].strip().upper()
        slots["existing_booking_code"] = code

    flag = data.get("compliance_flag")
    if flag not in (None, "refuse_advice", "refuse_pii", "out_of_scope"):
        flag = None

    return {"intent": intent, "slots": slots,
            "compliance_flag": flag, "speech": data.get("speech", "Got it.")}


def classify(utterance: str, context: dict | None = None) -> dict:
    """Return dict with intent, slots, compliance_flag, speech.
    Rule-based first (fast), LLM fallback for ambiguous inputs.
    Adapted from M3 IntentRouter.route().
    """
    low = utterance.lower()

    # Rule-based for clear compliance / end-call signals (always fast)
    advice_words = ["invest", "stock", "return", "nifty", "sensex", "portfolio",
                    "buy", "sell", "recommend", "crypto", "market crash", "market prediction"]
    if any(w in low for w in advice_words):
        return _rule_based(utterance)

    end_words = ["bye", "goodbye", "leave", "not interested", "no thanks", "forget it",
                 "never mind", "i'm done", "don't want to proceed"]
    if any(w in low for w in end_words):
        return _rule_based(utterance)

    # Try LLM for rich intent + slot extraction
    if os.getenv("ANTHROPIC_API_KEY"):
        context_str = ""
        if context:
            filled = {k: v for k, v in context.items() if v and k in
                      ("topic", "day_preference", "time_preference", "intent")}
            if filled:
                context_str = f"\n[Context already collected]: {json.dumps(filled)}"
        try:
            msg = _get_client().messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=256,
                system=_LLM_SYSTEM,
                messages=[{"role": "user", "content": f"{utterance}{context_str}"}],
            )
            return _parse_llm_json(msg.content[0].text)
        except Exception as exc:
            logger.warning("LLM intent classification failed: %s — using rule-based", exc)

    return _rule_based(utterance)
