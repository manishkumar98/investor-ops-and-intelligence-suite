"""Two-pass PII scrubber adapted from M3 phase1/src/booking/pii_scrubber.py.

Pass 1 — Contextual: intent phrases ("my phone is 9876543210") → redact only value.
Pass 2 — Standalone: patterns without intent phrases (bare numbers, emails).
Keeps scrub() compatibility for pipeline_orchestrator.
"""

import re
from dataclasses import dataclass, field

_REDACT = "[REDACTED]"

# ── Pass 1: contextual patterns (intent phrase + value) ─────────────────────

_CONTEXTUAL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("phone", re.compile(
        r"(?:my\s+(?:phone|mobile|cell|contact|whatsapp)(?:\s+(?:number|no\.?))?"
        r"|(?:call|reach|contact|ping|whatsapp)\s+(?:me\s+)?(?:on|at|via)?"
        r"|my\s+number)"
        r"\s*(?:is|:|-|=)?\s*([+\d][\d\s\-]{4,14})",
        re.IGNORECASE,
    )),
    ("aadhaar", re.compile(
        r"(?:my\s+(?:aadhaar|aadhar|adhaar|uid)(?:\s+(?:number|no\.?|card))?"
        r"|(?:aadhaar|aadhar|adhaar)\s+(?:number\s+)?(?:is|:)?)"
        r"\s*(?:is|:|-|=)?\s*([\d][\d\s\-]{2,17})",
        re.IGNORECASE,
    )),
    ("pan", re.compile(
        r"(?:my\s+pan(?:\s+(?:number|no\.?|card))?"
        r"|pan\s+(?:number\s+)?(?:is|:)?)"
        r"\s*(?:is|:|-|=)?\s*([A-Z0-9]{5,12})",
        re.IGNORECASE,
    )),
    ("email", re.compile(
        r"(?:my\s+(?:email|e-mail|mail|gmail|yahoo)(?:\s+(?:id|address|is))?"
        r"|(?:email|mail|send)\s+(?:me\s+)?(?:at|to)?"
        r"|(?:reach|contact)\s+me\s+(?:at|via|on)\s+(?:email)?)"
        r"\s*(?:is|:|-|=)?\s*(\S+@\S+)",
        re.IGNORECASE,
    )),
    ("account_number", re.compile(
        r"(?:my\s+(?:account|card|debit|credit|bank)(?:\s+(?:number|no\.?))?"
        r"|(?:account|card)\s+(?:number\s+)?(?:is|:)?)"
        r"\s*(?:is|:|-|=)?\s*([\d][\d\s\-]{3,22})",
        re.IGNORECASE,
    )),
]

# ── Pass 2: standalone patterns (no intent phrase required) ─────────────────

_ACCOUNT_16_RE = re.compile(r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)")
_AADHAAR_RE    = re.compile(r"(?<!\d)\d{4}[\s\-]?\d{4}[\s\-]?\d{4}(?!\d)")
_PAN_RE        = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", re.IGNORECASE)
_PHONE_RE      = re.compile(r"(?<!\d)(?:\+91[\s\-]?|91[\s\-]?|0)?[6-9]\d{8,9}(?!\d)", re.IGNORECASE)
_EMAIL_RE      = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)

_STANDALONE_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("account_number", _ACCOUNT_16_RE),
    ("aadhaar",        _AADHAAR_RE),
    ("pan",            _PAN_RE),
    ("phone",          _PHONE_RE),
    ("email",          _EMAIL_RE),
]

# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class PIIScrubResult:
    cleaned_text: str
    pii_found: bool
    categories: list[str] = field(default_factory=list)


# ── spaCy NER (optional second pass for PERSON names) ───────────────────────

_spacy_nlp = None


def _get_nlp():
    global _spacy_nlp
    if _spacy_nlp is None:
        try:
            import spacy
            _spacy_nlp = spacy.load("en_core_web_sm")
        except Exception:
            _spacy_nlp = False
    return _spacy_nlp if _spacy_nlp is not False else None


# ── Core scrubber ────────────────────────────────────────────────────────────

def scrub_pii(text: str) -> PIIScrubResult:
    """Two-pass PII scrubber (M3). Returns PIIScrubResult."""
    if not text:
        return PIIScrubResult(cleaned_text=text, pii_found=False)

    cleaned = text
    found_cats: list[str] = []

    # Pass 1 — contextual
    for category, pattern in _CONTEXTUAL_PATTERNS:
        def _redact_value(m: re.Match, _cat: str = category) -> str:
            full_match = m.group(0)
            return full_match[: m.start(1) - m.start()] + _REDACT

        new_text, count = pattern.subn(_redact_value, cleaned)
        if count > 0:
            cleaned = new_text
            if category not in found_cats:
                found_cats.append(category)

    # Pass 2 — standalone
    for category, pattern in _STANDALONE_PATTERNS:
        new_text, count = pattern.subn(_REDACT, cleaned)
        if count > 0:
            cleaned = new_text
            if category not in found_cats:
                found_cats.append(category)

    return PIIScrubResult(cleaned_text=cleaned, pii_found=bool(found_cats), categories=found_cats)


def scrub(text: str) -> tuple[str, int]:
    """Compatibility wrapper: returns (clean_text, redaction_count).

    Used by pipeline_orchestrator and any code that expects the old interface.
    Also runs spaCy NER pass for PERSON names if available.
    """
    result = scrub_pii(text)
    cleaned = result.cleaned_text
    count = len(result.categories)

    # spaCy NER for PERSON entities
    nlp = _get_nlp()
    if nlp:
        doc = nlp(cleaned)
        for ent in reversed(doc.ents):
            if ent.label_ == "PERSON":
                cleaned = cleaned[: ent.start_char] + "[REDACTED]" + cleaned[ent.end_char :]
                count += 1

    return cleaned, count
