"""Adapted from M3 phase2/src/dialogue/intent_router.py slot extraction functions."""
from .intent_classifier import (
    _TOPIC_KEYWORDS,
    _extract_day_preference,
    _extract_time_preference,
)

# Human-readable topic labels for display
TOPIC_LABELS = {
    "kyc_onboarding":  "KYC and Onboarding",
    "sip_mandates":    "SIP and Mandates",
    "statements_tax":  "Statements and Tax Documents",
    "withdrawals":     "Withdrawals and Timelines",
    "account_changes": "Account Changes and Nominee",
}


def extract_topic(utterance: str) -> str | None:
    """Return a topic key from utterance using keyword matching.
    Returns None if no topic is detected.
    Adapted from M3 _TOPIC_KEYWORDS matching in intent_router.py.
    """
    low = utterance.lower()
    for topic_key, keywords in _TOPIC_KEYWORDS.items():
        if any(k in low for k in keywords):
            return topic_key
    return None


def extract_time_pref(utterance: str) -> dict:
    """Extract day_preference and time_preference from utterance.
    Adapted from M3 _extract_day_preference + _extract_time_preference.
    Returns: {"day": str|None, "period": str|None}
    """
    low = utterance.lower()
    return {
        "day":    _extract_day_preference(low),
        "period": _extract_time_preference(low),
    }


def topic_label(topic_key: str) -> str:
    """Return human-readable label for a topic key."""
    return TOPIC_LABELS.get(topic_key, topic_key.replace("_", " ").title())
