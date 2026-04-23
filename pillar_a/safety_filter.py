import re

# These 4 patterns are locked — never expand without a compliance review.
BLOCK_PATTERNS = [
    # Advice: block recommendation/selection questions, not factual "what is X of fund Y"
    (r"(which\s+fund|best\s+fund|better\s+fund|top\s+fund|recommend.*fund|fund.*recommend|should\s+i\s+(?:invest|move|switch|buy|sell|put|allocate|exit|redeem|transfer)|which.*invest|best.*invest|good\s+fund|good\s+scheme)", "advice_refusal"),
    (r"(return|profit|earn|gain).*(next|predict|will|expect)", "performance_refusal"),
    (r"(compare|vs|versus|which.*better|better.*than).*(fund|scheme|elss|bluechip|midcap|smallcap|flexicap|sip)", "comparison_refusal"),
    (r"(email|phone|contact|ceo|cxo|address)",                 "pii_refusal"),
]

REFUSAL_MESSAGES = {
    "advice_refusal":      (
        "I can only provide factual information about mutual fund schemes. "
        "For investment advice, please consult a SEBI-registered advisor. "
        "Educational resource: https://www.amfiindia.com"
    ),
    "performance_refusal": (
        "I cannot predict fund performance or returns. "
        "Please refer to the official factsheet for historical data. "
        "Source: https://www.sbimf.com"
    ),
    "comparison_refusal":  (
        "I don't compare or recommend funds. "
        "For scheme comparisons, visit the official AMC or AMFI website. "
        "Source: https://www.amfiindia.com"
    ),
    "pii_refusal":         (
        "I cannot share personal information or contact details. "
        "For official contacts, visit https://www.sbimf.com/en-us/contact-us"
    ),
}


def is_safe(query: str) -> tuple[bool, str | None]:
    """Return (True, None) if safe, or (False, refusal_message) if blocked."""
    lower = query.lower()
    for pattern, refusal_type in BLOCK_PATTERNS:
        if re.search(pattern, lower):
            return False, REFUSAL_MESSAGES[refusal_type]
    return True, None
