"""mfapi.in loader — fetches NAV data and scheme metadata for SBI funds.

API: https://api.mfapi.in/mf          — full fund list (JSON)
     https://api.mfapi.in/mf/{code}   — scheme details + NAV history

Returns data without any scraping — mfapi.in pulls directly from AMFI.
No API key required; no rate limiting for reasonable usage.
"""
import json
import re
import time
from datetime import date
from pathlib import Path
from typing import Optional
import urllib.request
import urllib.error

# ── Canonical fund names → AMFI scheme codes (hardcoded, verified live) ────────
# Scheme codes are stable identifiers from api.mfapi.in/mf
# Last verified: 2026-05-06 against live AMFI list
# NOTE: Fund names in AMFI change over time (rebranding, renaming).
#       Use scheme codes as the primary lookup key — they never change.
FUND_SCHEME_CODES: dict[str, int] = {
    "SBI Large Cap Fund":                   119598,   # SBI Large Cap FUND-DIRECT PLAN -GROWTH
    "SBI Flexicap Fund":                    119718,   # SBI Flexicap Fund - DIRECT PLAN - Growth Option
    "SBI ELSS Tax Saver Fund":              119723,   # SBI ELSS Tax Saver FUND - DIRECT PLAN -GROWTH
    "SBI Small Cap Fund":                   125497,   # SBI Small Cap Fund - Direct Plan - Growth
    "SBI Midcap Fund":                      119716,   # SBI MIDCAP FUND - DIRECT PLAN - GROWTH
    "SBI Focused Equity Fund":              119727,   # SBI FOCUSED FUND - DIRECT PLAN -GROWTH
    "SBI Liquid Fund":                      119800,   # SBI Liquid Fund - DIRECT PLAN -Growth
    "SBI Contra Fund":                      119835,   # SBI CONTRA FUND - DIRECT PLAN - GROWTH
    "SBI Technology Opportunities Fund":    120578,   # SBI TECHNOLOGY OPPORTUNITIES FUND - DIRECT PLAN - GROWTH
    "SBI Healthcare Opportunities Fund":    119783,   # SBI HEALTHCARE OPPORTUNITIES FUND - DIRECT PLAN -GROWTH
    "SBI Equity Hybrid Fund":               119609,   # SBI EQUITY HYBRID FUND - DIRECT PLAN - Growth
    "SBI Magnum Global Fund":               120575,   # SBI CONSUMPTION OPPORTUNITIES FUND - DIRECT PLAN - GROWTH (renamed)
}

# Keep FUND_SEARCH_TERMS as an alias so existing code that references it still works
FUND_SEARCH_TERMS: dict[str, str] = {k: str(v) for k, v in FUND_SCHEME_CODES.items()}

_MFAPI_BASE = "https://api.mfapi.in/mf"
_TIMEOUT = 15


def _fetch_json(url: str) -> Optional[dict | list]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        print(f"[mfapi] fetch error {url}: {exc}")
        return None


def _fetch_all_funds() -> list[dict]:
    """Return full AMFI fund list from mfapi.in — [{schemeCode, schemeName}, ...]."""
    data = _fetch_json(_MFAPI_BASE)
    if isinstance(data, list):
        return data
    return []


def _find_scheme_code(all_funds: list[dict], search_name: str) -> Optional[int]:
    """Look up scheme code — first checks FUND_SCHEME_CODES by canonical name,
    then falls back to name-matching against the AMFI list for unknown funds."""
    # Primary path: canonical name → hardcoded scheme code (instant, no API needed)
    if search_name in FUND_SCHEME_CODES:
        return FUND_SCHEME_CODES[search_name]
    # Try interpreting search_name as a numeric code string (from FUND_SEARCH_TERMS alias)
    try:
        return int(search_name)
    except ValueError:
        pass
    # Fallback: fuzzy name match against live AMFI list
    search_lower = search_name.lower()
    for fund in all_funds:
        if fund.get("schemeName", "").lower() == search_lower:
            return fund["schemeCode"]
    words = [w for w in search_lower.split() if len(w) > 2]
    for fund in all_funds:
        name = fund.get("schemeName", "").lower()
        if all(w in name for w in words):
            return fund["schemeCode"]
    return None


def _fetch_scheme_data(scheme_code: int) -> Optional[dict]:
    """Fetch scheme metadata + NAV history for a given scheme code."""
    return _fetch_json(f"{_MFAPI_BASE}/{scheme_code}")


def _calculate_returns(nav_data: list[dict]) -> dict[str, str]:
    """Calculate approximate returns from NAV history."""
    if not nav_data:
        return {}

    def parse_date(d: str) -> Optional[date]:
        for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
            try:
                from datetime import datetime
                return datetime.strptime(d, fmt).date()
            except ValueError:
                pass
        return None

    # Build (date, nav) list sorted newest first
    entries = []
    for entry in nav_data:
        d = parse_date(entry.get("date", ""))
        try:
            nav = float(entry.get("nav", 0))
        except (ValueError, TypeError):
            nav = 0.0
        if d and nav > 0:
            entries.append((d, nav))
    entries.sort(key=lambda x: x[0], reverse=True)

    if not entries:
        return {}

    latest_date, latest_nav = entries[0]
    returns = {"nav": f"₹{latest_nav:.2f}", "nav_date": str(latest_date)}

    def nav_on_or_before(target: date) -> Optional[float]:
        for d, n in entries:
            if d <= target:
                return n
        return None

    def cagr(n_then: float, n_now: float, years: float) -> str:
        if n_then <= 0 or years <= 0:
            return ""
        r = ((n_now / n_then) ** (1 / years) - 1) * 100
        return f"{r:.2f}%"

    from datetime import timedelta
    nav_1y = nav_on_or_before(latest_date.replace(year=latest_date.year - 1))
    nav_3y = nav_on_or_before(latest_date.replace(year=latest_date.year - 3))
    nav_5y = nav_on_or_before(latest_date.replace(year=latest_date.year - 5))

    if nav_1y:
        returns["returns_1y"] = cagr(nav_1y, latest_nav, 1)
    if nav_3y:
        returns["returns_3y"] = cagr(nav_3y, latest_nav, 3)
    if nav_5y:
        returns["returns_5y"] = cagr(nav_5y, latest_nav, 5)

    # Inception date from oldest entry
    oldest = entries[-1]
    returns["inception_date"] = str(oldest[0])
    returns["nav_inception"] = f"₹{oldest[1]:.4f}"

    return returns


def format_fund_as_text(canonical_name: str, meta: dict, nav_data: list[dict]) -> str:
    """Format mfapi data into a structured text suitable for RAG ingestion."""
    scheme_code = meta.get("scheme_code", "")
    scheme_name = meta.get("scheme_name", canonical_name)
    fund_house   = meta.get("fund_house", "SBI Mutual Fund")
    scheme_type  = meta.get("scheme_type", "")
    category     = meta.get("scheme_category", "")
    source_url   = f"https://api.mfapi.in/mf/{scheme_code}"

    returns = _calculate_returns(nav_data)
    nav      = returns.get("nav", "N/A")
    nav_date = returns.get("nav_date", str(date.today()))
    r_1y     = returns.get("returns_1y", "")
    r_3y     = returns.get("returns_3y", "")
    r_5y     = returns.get("returns_5y", "")
    inception = returns.get("inception_date", "")

    lines = [
        f"Source URL: {source_url}",
        f"Scraped Date: {date.today()}",
        "--------------------------------------------------",
        f"{canonical_name}",
        f"Fund House: {fund_house}",
        f"AMFI Scheme Name: {scheme_name}",
        f"Scheme Code: {scheme_code}",
        f"Category: {category}",
        f"Scheme Type: {scheme_type}",
        "",
        f"NAV: {nav} (as on {nav_date})",
    ]
    if r_1y:
        lines.append(f"1-Year Return (CAGR): {r_1y}")
    if r_3y:
        lines.append(f"3-Year Return (CAGR): {r_3y}")
    if r_5y:
        lines.append(f"5-Year Return (CAGR): {r_5y}")
    if inception:
        lines.append(f"Inception Date: {inception}")

    lines += [
        "",
        f"About {canonical_name}:",
        f"{canonical_name} is a mutual fund scheme offered by {fund_house}.",
        f"It is classified under: {category}.",
        f"The scheme is of type: {scheme_type}.",
        "",
        "NAV History (recent 10 entries):",
    ]
    for entry in nav_data[:10]:
        lines.append(f"  {entry.get('date', '')} — NAV: ₹{entry.get('nav', '')}")

    lines += [
        "",
        "Frequently Asked Questions:",
        f"What is the current NAV of {canonical_name}?",
        f"The current NAV is {nav} as on {nav_date}.",
        "",
        f"What is the 1-year return of {canonical_name}?",
        f"The 1-year CAGR is {r_1y or 'not available'}.",
        "",
        f"What is the 3-year return of {canonical_name}?",
        f"The 3-year CAGR is {r_3y or 'not available'}.",
        "",
        "Mutual Fund investments are subject to market risks, read all scheme related documents carefully.",
        "Data sourced from AMFI via api.mfapi.in",
    ]
    return "\n".join(lines)


def fetch_all_sbi_funds(
    raw_dir: Path,
    delay_seconds: float = 0.5,
) -> dict[str, str]:
    """Fetch data for all 12 SBI funds from mfapi.in and write to data/raw/.

    Uses hardcoded scheme codes (FUND_SCHEME_CODES) for reliable lookup —
    bypasses the full AMFI list download entirely.

    Returns dict of canonical_name → status ("ok" / "not_found" / "error")
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    for canonical_name, scheme_code in FUND_SCHEME_CODES.items():
        print(f"[mfapi] Fetching scheme {scheme_code}: {canonical_name}")
        time.sleep(delay_seconds)
        scheme_data = _fetch_scheme_data(scheme_code)
        if not scheme_data or scheme_data.get("status") != "SUCCESS":
            print(f"[mfapi]   ERROR fetching scheme {scheme_code}")
            results[canonical_name] = "error"
            continue

        meta     = scheme_data.get("meta", {})
        nav_data = scheme_data.get("data", [])

        text = format_fund_as_text(canonical_name, meta, nav_data)

        safe_name = canonical_name.lower().replace(" ", "_")
        out_path  = raw_dir / f"{safe_name}_(mfapi).txt"
        out_path.write_text(text, encoding="utf-8")
        print(f"[mfapi]   → {out_path.name}  (NAV entries: {len(nav_data)})")
        results[canonical_name] = "ok"

    return results
