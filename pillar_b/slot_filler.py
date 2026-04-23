import os
import re
import anthropic

VALID_TOPICS = [
    "KYC / Onboarding",
    "SIP / Mandates",
    "Statements / Tax Documents",
    "Withdrawals & Timelines",
    "Account Changes / Nominee",
]

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
PERIODS  = ["morning", "afternoon", "evening", "am", "pm"]

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


def extract_topic(utterance: str) -> str:
    """Map free text to one of 5 valid topics using LLM."""
    prompt = (
        f"Map this user request to the closest topic from the list:\n"
        f"{VALID_TOPICS}\n\n"
        f"User said: {utterance}\n\n"
        f"Reply with the EXACT topic string from the list, nothing else."
    )
    msg = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=30,
        messages=[{"role": "user", "content": prompt}],
    )
    result = msg.content[0].text.strip()

    for topic in VALID_TOPICS:
        if topic.lower() in result.lower() or result.lower() in topic.lower():
            return topic

    # Keyword fallback
    lower = utterance.lower()
    if any(kw in lower for kw in ["kyc", "onboard", "verify"]):
        return "KYC / Onboarding"
    if any(kw in lower for kw in ["sip", "mandate", "systematic"]):
        return "SIP / Mandates"
    if any(kw in lower for kw in ["statement", "tax", "capital gain"]):
        return "Statements / Tax Documents"
    if any(kw in lower for kw in ["withdraw", "redeem", "timeline"]):
        return "Withdrawals & Timelines"
    if any(kw in lower for kw in ["nominee", "account change", "update"]):
        return "Account Changes / Nominee"

    return VALID_TOPICS[0]


def extract_time_pref(utterance: str) -> dict:
    """Extract day and period preference from utterance using regex."""
    lower = utterance.lower()

    day = next((d for d in WEEKDAYS if d in lower), None)
    period = next((p for p in PERIODS if p in lower), None)

    # Map am/pm to morning/afternoon
    if period == "am":
        period = "morning"
    elif period == "pm":
        period = "afternoon"

    return {"day": day, "period": period}
