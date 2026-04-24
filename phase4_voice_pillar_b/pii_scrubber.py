"""Two-pass PII scrubber — ported from M3 phase1/src/booking/pii_scrubber.py.

Runs on user input BEFORE it reaches the LLM.
Pass 1 — contextual: "my phone is 9876543210" → "my phone is [REDACTED]"
Pass 2 — standalone: catches bare PAN / Aadhaar / phone without intent phrase.
"""
import re
from dataclasses import dataclass, field

_REDACT = "[REDACTED]"

# ── Pass 1: contextual patterns ───────────────────────────────────────────────
_CONTEXTUAL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("phone", re.compile(
        r"(?:my\s+(?:phone|mobile|cell|contact|whatsapp)(?:\s+(?:number|no\.?))?|"
        r"(?:call|reach|contact|ping|whatsapp)\s+(?:me\s+)?(?:on|at|via)?|my\s+number)"
        r"\s*(?:is|:|-|=)?\s*([+\d][\d\s\-]{4,14})",
        re.IGNORECASE,
    )),
    ("aadhaar", re.compile(
        r"(?:my\s+(?:aadhaar|aadhar|adhaar|uid)(?:\s+(?:number|no\.?|card))?|"
        r"(?:aadhaar|aadhar|adhaar)\s+(?:number\s+)?(?:is|:)?)"
        r"\s*(?:is|:|-|=)?\s*([\d][\d\s\-]{2,17})",
        re.IGNORECASE,
    )),
    ("pan", re.compile(
        r"(?:my\s+pan(?:\s+(?:number|no\.?|card))?|pan\s+(?:number\s+)?(?:is|:)?)"
        r"\s*(?:is|:|-|=)?\s*([A-Z0-9]{5,12})",
        re.IGNORECASE,
    )),
    ("email", re.compile(
        r"(?:my\s+(?:email|e-mail|mail|gmail|yahoo)(?:\s+(?:id|address|is))?|"
        r"(?:email|mail|send)\s+(?:me\s+)?(?:at|to)?|"
        r"(?:reach|contact)\s+me\s+(?:at|via|on)\s+(?:email)?)"
        r"\s*(?:is|:|-|=)?\s*(\S+@\S+)",
        re.IGNORECASE,
    )),
    ("account_number", re.compile(
        r"(?:my\s+(?:account|card|debit|credit|bank)(?:\s+(?:number|no\.?))?|"
        r"(?:account|card)\s+(?:number\s+)?(?:is|:)?)"
        r"\s*(?:is|:|-|=)?\s*([\d][\d\s\-]{3,22})",
        re.IGNORECASE,
    )),
]

# ── Pass 2: standalone patterns ───────────────────────────────────────────────
_STANDALONE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("account_number", re.compile(r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)")),
    ("aadhaar",        re.compile(r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)")),
    ("pan",            re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)),
    ("phone",          re.compile(r"(?<!\d)(?:\+91[\s\-]?|91[\s\-]?|0)?[6-9]\d{8,9}(?!\d)", re.IGNORECASE)),
    ("email",          re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)),
]


@dataclass
class PIIScrubResult:
    cleaned_text: str
    pii_found: bool
    categories: list[str] = field(default_factory=list)
    context_detected: list[str] = field(default_factory=list)
    pattern_detected: list[str] = field(default_factory=list)

    def detection_summary(self) -> str:
        if not self.pii_found:
            return "No PII detected."
        parts = []
        if self.context_detected:
            parts.append(f"contextual ({', '.join(self.context_detected)})")
        if self.pattern_detected:
            parts.append(f"pattern ({', '.join(self.pattern_detected)})")
        return "PII detected via: " + " + ".join(parts)


def scrub_pii(text: str) -> PIIScrubResult:
    """Two-pass PII scrubber. Returns cleaned text + detection metadata."""
    if not text:
        return PIIScrubResult(cleaned_text=text, pii_found=False)

    cleaned = text
    context_cats: list[str] = []
    pattern_cats: list[str] = []

    # Pass 1: contextual
    for category, pattern in _CONTEXTUAL_PATTERNS:
        def _redact_value(m: re.Match, _cat: str = category) -> str:
            full_match = m.group(0)
            return full_match[: m.start(1) - m.start()] + _REDACT
        new_text, count = pattern.subn(_redact_value, cleaned)
        if count > 0:
            cleaned = new_text
            if category not in context_cats:
                context_cats.append(category)

    # Pass 2: standalone
    for category, pattern in _STANDALONE_PATTERNS:
        new_text, count = pattern.subn(_REDACT, cleaned)
        if count > 0:
            cleaned = new_text
            if category not in pattern_cats:
                pattern_cats.append(category)

    all_cats = list(dict.fromkeys(context_cats + pattern_cats))
    return PIIScrubResult(
        cleaned_text=cleaned,
        pii_found=len(all_cats) > 0,
        categories=all_cats,
        context_detected=context_cats,
        pattern_detected=pattern_cats,
    )


def contains_pii(text: str) -> bool:
    return scrub_pii(text).pii_found
