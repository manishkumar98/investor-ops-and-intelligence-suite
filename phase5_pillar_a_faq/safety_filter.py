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

# Keyword → (display name, official SBI MF URL)
_FUND_LINKS: list[tuple[str, str, str]] = [
    (r"large\s*cap|bluechip|blue\s*chip",
     "SBI Large Cap Fund",
     "https://www.sbimf.com/sbimf-scheme-details/sbi-large-cap-fund-(formerly-known-as-sbi-bluechip-fund)-43"),
    (r"mid\s*cap|midcap",
     "SBI Midcap Fund",
     "https://www.sbimf.com/sbimf-scheme-details/SBI-Midcap-Fund-34"),
    (r"small\s*cap|smallcap",
     "SBI Small Cap Fund",
     "https://www.sbimf.com/sbimf-scheme-details/SBI-Small-Cap-Fund-329"),
    (r"elss|tax\s*saver|long\s*term\s*equity",
     "SBI ELSS Tax Saver Fund",
     "https://www.sbimf.com/sbimf-scheme-details/SBI-ELSS-Tax-Saver-Fund-(formerly-known-as-SBI-Long-Term-Equity-Fund)-3"),
    (r"flexi\s*cap|flexicap",
     "SBI Flexicap Fund",
     "https://www.sbimf.com/sbimf-scheme-details/SBI-Flexicap-Fund-39"),
    (r"focused\s*equity|focused",
     "SBI Focused Equity Fund",
     "https://www.sbimf.com/sbimf-scheme-details/SBI-Focused-Equity-Fund-37"),
    (r"liquid",
     "SBI Liquid Fund",
     "https://www.sbimf.com/sbimf-scheme-details/SBI-Liquid-Fund-1"),
    (r"contra",
     "SBI Contra Fund",
     "https://www.sbimf.com/sbimf-scheme-details/SBI-Contra-Fund-51"),
]


def _fund_links_for_query(query: str) -> list[str]:
    """Return list of 'Name — URL' strings for each SBI fund mentioned in the query."""
    lower = query.lower()
    links = []
    for pattern, name, url in _FUND_LINKS:
        if re.search(pattern, lower):
            links.append(f"{name} — {url}")
    return links


def is_safe(query: str) -> tuple[bool, str | None]:
    """Return (True, None) if safe, or (False, refusal_message) if blocked."""
    lower = query.lower()
    for pattern, refusal_type in BLOCK_PATTERNS:
        if re.search(pattern, lower):
            msg = REFUSAL_MESSAGES[refusal_type]
            if refusal_type == "comparison_refusal":
                links = _fund_links_for_query(query)
                if links:
                    msg += "\n\nView individual fund pages:\n" + "\n".join(f"• {l}" for l in links)
            return False, msg
    return True, None
