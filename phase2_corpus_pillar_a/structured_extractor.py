"""Structured field extractor for SBI MF and INDMoney pages.

Both url_loader.fetch_url() and _parse_raw_file() collapse page text into
single-space-separated strings. All patterns here are tuned to that format.

Sample inputs the patterns match against:
  "AUM as on 31 Mar 2026 ₹48925.75Cr"
  "Min SIP Amount ₹ 500 & in multiples"
  "Min Lumpsum ₹ 5,000 & in multiples"
  "NAV as on Apr 22, 2026 ₹ 93.3755 (-0.34% one day change)"
  "Date of Allotment 14 Feb, 2006"
  "Scheme Benchmark: BSE 100 TRI"
  "Mr. Saurabh Pant -"
  "VERY HIGH Risk"
  "The risk of the scheme is very high"
  "statutory lock-in period of 3 years"
  "Exit Load 1% if redeemed within 1 year"
  "Expense Ratio (Direct Plan) 0.87%"
"""
import re
from datetime import date
from urllib.parse import urlparse

# ── Fund name normalisation from URL slug ─────────────────────────────────────
_SLUG_MAP: dict[str, str] = {
    "sbi-bluechip-fund":           "SBI Large Cap Fund",
    "sbi-large-cap-fund":          "SBI Large Cap Fund",
    "sbi-flexicap-fund":           "SBI Flexicap Fund",
    "sbi-elss-tax-saver-fund":     "SBI ELSS Tax Saver Fund",
    "sbi-long-term-equity-fund":   "SBI ELSS Tax Saver Fund",
    "sbi-small-cap-fund":          "SBI Small Cap Fund",
    "sbi-midcap-fund":             "SBI Midcap Fund",
    "sbi-magnum-midcap-fund":      "SBI Midcap Fund",
    "sbi-focused-equity-fund":     "SBI Focused Equity Fund",
    "sbi-liquid-fund":             "SBI Liquid Fund",
    "sbi-contra-fund":             "SBI Contra Fund",
}

# Slug map for raw local file names (stem → canonical name)
_FILE_SLUG_MAP: dict[str, str] = {
    "sbi_bluechip_fund":         "SBI Large Cap Fund",
    "sbi_large_cap_fund":        "SBI Large Cap Fund",
    "sbi_flexicap_fund":         "SBI Flexicap Fund",
    "sbi_elss_tax_saver_fund":   "SBI ELSS Tax Saver Fund",
    "sbi_long_term_equity_fund": "SBI ELSS Tax Saver Fund",
    "sbi_small_cap_fund":        "SBI Small Cap Fund",
    "sbi_midcap_fund":           "SBI Midcap Fund",
    "sbi_focused_equity_fund":   "SBI Focused Equity Fund",
    "sbi_liquid_fund":           "SBI Liquid Fund",
    "sbi_contra_fund":           "SBI Contra Fund",
}

# ── Field patterns ─────────────────────────────────────────────────────────────
# Text format after collapse: labels and values separated by a single space.
# e.g. "AUM as on 31 Mar 2026 ₹48925.75Cr"
_PATTERNS: dict[str, list[str]] = {
    "aum": [
        # "AUM as on 31 Mar 2026 ₹48925.75Cr"  — date contains digits, use lazy .{2,30}?
        r"aum\s+as\s+on\s+.{2,30}?(?:rs\.?\s*|₹\s*)([0-9][0-9,\.]+\s*(?:cr|crore|lakh)?)",
        # "Net Assets ₹ 48925.75 Cr" or "Net Assets: ₹48925 Cr"
        r"net\s+assets?\s*[:\-]?\s*(?:rs\.?\s*|₹\s*)([0-9][0-9,\.]+\s*(?:cr|crore|lakh)?)",
        r"aum\s*[:\-]\s*(?:rs\.?\s*|₹\s*)?([0-9][0-9,\.]+\s*(?:cr|crore|lakh)?)",
    ],
    "nav": [
        # "NAV as on Apr 22, 2026 ₹ 93.3755" — date contains digits, use lazy .{2,30}?
        r"nav\s+as\s+on\s+.{2,30}?(?:rs\.?\s*|₹\s*)([0-9][0-9,\.]+)",
        r"net\s+asset\s+value\s*[:\-]?\s*(?:rs\.?\s*|₹\s*)?([0-9][0-9,\.]+)",
    ],
    "min_sip": [
        # "Min SIP Amount ₹ 500 & in multiples"
        r"min(?:imum)?\s+sip\s+amount\s*(?:rs\.?\s*|₹\s*)([0-9][0-9,]+)",
        r"min(?:imum)?\s+sip\s*[:\-]?\s*(?:rs\.?\s*|₹\s*)([0-9][0-9,]+)",
        r"sip\s+(?:minimum|min)\s*[:\-]?\s*(?:rs\.?\s*|₹\s*)([0-9][0-9,]+)",
    ],
    "min_lumpsum": [
        # "Min Lumpsum ₹ 5,000 & in multiples"
        r"min(?:imum)?\s+lump\s*sum\s*(?:rs\.?\s*|₹\s*)([0-9][0-9,]+)",
        r"min(?:imum)?\s+(?:purchase|investment)\s*(?:rs\.?\s*|₹\s*)([0-9][0-9,]+)",
        r"lump\s*sum\s*[:\-]?\s*(?:rs\.?\s*|₹\s*)([0-9][0-9,]+)",
    ],
    "exit_load": [
        # "Exit Load 1% if redeemed within 1 year" — long descriptive form first
        r"exit\s+load\s+([0-9\.]+\s*%\s+if\s+[^\.]{5,80}\.?)",
        # "Exit Load 0.2%" — INDMoney short form
        r"exit\s+load\s+([0-9\.]+\s*%)",
        r"exit\s+load\s*[:\-]\s*([^\.]{10,100}\.)",
        r"exit\s+load\s*[:\-]\s*([^\n]{5,80})",
        r"exit\s+charges?\s*[:\-]\s*([^\.]{10,100}\.)",
    ],
    "expense_ratio": [
        # "Expense Ratio (Direct Plan) 0.87%" or "Expense Ratio: 0.87%"
        r"expense\s+ratio\s*(?:\([^)]*\))?\s*[:\-]?\s*([0-9]+\.?[0-9]*\s*%)",
        r"total\s+expense\s+ratio\s*[:\-]?\s*([0-9]+\.?[0-9]*\s*%)",
        r"\bter\b\s*[:\-]\s*([0-9]+\.?[0-9]*\s*%)",
    ],
    "benchmark": [
        # "Scheme Benchmark: BSE 100 TRI"
        r"scheme\s+benchmark\s*[:\-]\s*([A-Z][A-Za-z0-9\s]{3,50}?)(?=\s{2,}|additional|$)",
        r"benchmark\s*[:\-]\s*([A-Z][A-Za-z0-9\s]{3,50}?)(?=\s{2,}|additional|\.|$)",
    ],
    "fund_manager": [
        # (?-i:...) enforces case-sensitivity for name → rejects "CEO", "the fund"
        # \s (not \s+) prevents double-space from merging separate name occurrences
        # [A-Z][a-z]* allows single-letter initials like "R Srinivasan"
        r"(?:mr\.|ms\.|mrs\.)\s+(?-i:([A-Z][a-z]*(?:\s[A-Z][a-z]+){1,2}))\s*(?:-|–|,|$|\s)",
        r"fund\s+manager\s*[:\-]\s*(?:mr\.|ms\.)?\s*(?-i:([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}))",
        r"managed\s+by\s+(?:mr\.|ms\.)\s*(?-i:([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,2}))",
    ],
    "risk": [
        # "VERY HIGH Risk" (appears near top) — capture before scheme description
        r"\b(very\s*high|high|moderately\s*high|moderate|moderately\s*low|low)\s+risk\b",
        # "The risk of the scheme is very high"
        r"risk\s+of\s+the\s+scheme\s+is\s+(very\s+high|high|moderately\s+high|moderate|low)",
    ],
    "category": [
        # "Scheme Type : An open ended equity scheme..."
        r"scheme\s+type\s*[:\-]\s*(an\s+open\s+ended[^\.]{5,100}?)(?=\s{3,}|\.|equity|debt|$)",
        r"(?:scheme\s+)?category\s*[:\-]\s*([a-zA-Z\s\/\-&]{4,60}?)(?=\s{3,}|\.|,|$)",
    ],
    "lock_in": [
        # "statutory lock-in period of 3 years"
        r"(?:statutory\s+)?lock[- ]?in\s+(?:period\s+)?of\s+([0-9]+\s+(?:year|month)[s]?)",
        r"lock[- ]?in\s+period\s*[:\-]\s*([^\.\n]{3,50})",
    ],
    "inception_date": [
        # "Date of Allotment 14 Feb, 2006"
        r"date\s+of\s+allotment\s+([0-9]{1,2}\s+[A-Za-z]{3,9}[,\s]+[0-9]{4})",
        r"(?:inception|launch)\s+date\s*[:\-]\s*([a-zA-Z0-9\s,\-\/]{6,25})",
    ],
    "returns_1y": [
        r"1\s*(?:year|yr)\.?\s+(?:return|cagr|performance)\s*[:\-]?\s*([+-]?[0-9]+\.?[0-9]*\s*%)",
        r"returns?\s+for\s+direct\s+growth\s+([0-9]+\.?[0-9]*%)\s+since\s+inception",
    ],
    "returns_3y": [
        r"3\s*(?:year|yr)\.?\s+(?:return|cagr|performance)\s*[:\-]?\s*([+-]?[0-9]+\.?[0-9]*\s*%)",
        r"3\s*yr?\s*[:\-]\s*([+-]?[0-9]+\.?[0-9]*\s*%)",
    ],
}

# Post-process cleanups per field (strip junk that bleeds past the match)
_CLEANUPS: dict[str, list[str]] = {
    "fund_manager": [r"\s*[-–,].*$",              # "Saurabh Pant - " → "Saurabh Pant"
                     r"\s+(?:videos?|for|is|in|has|the|and|or|of)\b.*$"],  # strip trailing common words
    "category":     [r"\s{2,}.*$"],               # trim after double-space
    "benchmark":    [r"\s+additional.*$",          # trim "Additional Benchmark…"
                     r"\s+bse\s+sensex.*$"],
    "risk":         [r"\s+risk$"],                 # "moderately high risk" → "moderately high"
    "aum":          [r"\s+as\s+on.*$"],            # trim date suffix if it bleeds in
    "exit_load":    [r"\s+lock\s+in.*$",           # strip "Lock In No Lock-in TurnOver…"
                     r"\s+turnover.*$"],
}


def _fund_name_from_url(url: str) -> str:
    path = urlparse(url).path.lower()
    for slug, name in _SLUG_MAP.items():
        if slug in path:
            return name
    segment = path.rstrip("/").split("/")[-1]
    segment = re.sub(r"-\d+$", "", segment)
    segment = re.sub(r"\(.*?\)", "", segment).strip()
    return segment.replace("-", " ").title()


def fund_name_from_filename(filename: str) -> str:
    """Guess canonical fund name from a raw local file stem like 'sbi_elss_tax_saver_fund_(official)'."""
    stem = re.sub(r"[_\s]*\([^)]*\)\s*$", "", filename.lower()).strip()
    for slug, name in _FILE_SLUG_MAP.items():
        if stem.startswith(slug):
            return name
    return stem.replace("_", " ").title()


def _extract_field(text: str, patterns: list[str]) -> str:
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip().rstrip(".,;:")
            if val and len(val) > 1:
                return val
    return ""


def _clean_field(field: str, value: str) -> str:
    for pat in _CLEANUPS.get(field, []):
        value = re.sub(pat, "", value, flags=re.IGNORECASE).strip()
    return value.strip().rstrip(".,;:")


def extract(url: str, page_text: str, fund_name: str = "") -> dict:
    """Extract structured fields from collapsed page text.

    Args:
        url:       Source URL (used for fund name normalisation if fund_name not given)
        page_text: Full collapsed plain text from url_loader or _parse_raw_file
        fund_name: Optional override (used when called from local file ingest)

    Returns a dict with all known slots. Empty string means not found.
    """
    name = fund_name or _fund_name_from_url(url)
    fields: dict[str, str] = {
        "fund_name":    name,
        "source_url":   url,
        "last_scraped": str(date.today()),
    }
    for field, patterns in _PATTERNS.items():
        raw = _extract_field(page_text, patterns)
        fields[field] = _clean_field(field, raw) if raw else ""

    return fields


def to_summary_text(fields: dict) -> str:
    """Format extracted fields into a labelled structured chunk text block.

    Returns "" if no data fields were found (no chunk created).
    """
    fund = fields.get("fund_name", "Unknown Fund")
    scraped = fields.get("last_scraped", "")
    lines = [f"[STRUCTURED FUND DATA — {fund} — as of {scraped}]"]

    label_map = [
        ("aum",            "AUM / Net Assets"),
        ("nav",            "NAV"),
        ("exit_load",      "Exit Load"),
        ("expense_ratio",  "Expense Ratio (Direct Plan)"),
        ("min_sip",        "Minimum SIP Amount"),
        ("min_lumpsum",    "Minimum Lumpsum"),
        ("benchmark",      "Benchmark Index"),
        ("fund_manager",   "Fund Manager"),
        ("risk",           "Risk Level"),
        ("category",       "Fund Category"),
        ("lock_in",        "Lock-in Period"),
        ("inception_date", "Inception Date"),
        ("returns_1y",     "1-Year Return"),
        ("returns_3y",     "3-Year Return (CAGR)"),
    ]

    any_found = False
    for key, label in label_map:
        val = fields.get(key, "")
        if val:
            lines.append(f"{label}: {val}")
            any_found = True

    if not any_found:
        return ""

    lines.append(f"Source: {fields.get('source_url', '')}")
    return "\n".join(lines)
