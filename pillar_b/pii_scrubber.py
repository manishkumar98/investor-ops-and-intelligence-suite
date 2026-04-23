import re

_REGEX_PATTERNS = [
    (r"\b[6-9]\d{9}\b",                           "[PHONE]"),
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL]"),
    (r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",               "[PAN]"),
    (r"\b\d{12}\b",                                "[AADHAAR]"),
    (r"\b[A-Z]{2}\d{2}[A-Z]{1,2}\d{4}\b",         "[ACCOUNT]"),
]

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


def scrub(text: str) -> tuple[str, int]:
    """Return (clean_text, redaction_count).

    Pass 1: regex patterns for phone, email, PAN, Aadhaar, account numbers.
    Pass 2: spaCy NER for PERSON entities (falls back gracefully if unavailable).
    """
    count = 0

    # Pass 1 — regex
    for pattern, replacement in _REGEX_PATTERNS:
        new_text, n = re.subn(pattern, replacement, text)
        text = new_text
        count += n

    # Pass 2 — spaCy NER
    nlp = _get_nlp()
    if nlp:
        doc = nlp(text)
        for ent in reversed(doc.ents):
            if ent.label_ == "PERSON":
                text = text[: ent.start_char] + "[REDACTED]" + text[ent.end_char :]
                count += 1

    return text, count
