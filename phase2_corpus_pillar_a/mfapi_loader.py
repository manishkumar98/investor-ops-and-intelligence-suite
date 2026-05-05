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

# ── Canonical fund names → AMFI scheme name search terms ─────────────────────
# We match these strings (case-insensitive) against the full AMFI fund list
# to find the correct Direct Plan Growth scheme code automatically.
FUND_SEARCH_TERMS: dict[str, str] = {
    "SBI Large Cap Fund":                   "SBI Bluechip Fund - Direct Plan Growth",
    "SBI Flexicap Fund":                    "SBI Flexicap Fund - Direct Plan Growth",
    "SBI ELSS Tax Saver Fund":              "SBI Long Term Equity Fund - Direct Plan Growth",
    "SBI Small Cap Fund":                   "SBI Small Cap Fund - Direct Plan Growth",
    "SBI Midcap Fund":                      "SBI Magnum Midcap Fund - Direct Plan Growth",
    "SBI Focused Equity Fund":              "SBI Focused Equity Fund - Direct Plan Growth",
    "SBI Liquid Fund":                      "SBI Liquid Fund - Direct Plan Growth",
    "SBI Contra Fund":                      "SBI Contra Fund - Direct Plan Growth",
    "SBI Technology Opportunities Fund":    "SBI Technology Opportunities Fund - Direct Plan Growth",
    "SBI Healthcare Opportunities Fund":    "SBI Healthcare Opportunities Fund - Direct Plan Growth",
    "SBI Equity Hybrid Fund":               "SBI Equity Hybrid Fund - Direct Plan Growth",
    "SBI Magnum Global Fund":               "SBI Magnum Global Fund - Direct Plan Growth",
}

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
    """Find scheme code by exact name match, then partial match fallback."""
    search_lower = search_name.lower()
    # Exact match first
    for fund in all_funds:
        if fund.get("schemeName", "").lower() == search_lower:
            return fund["schemeCode"]
    # Partial match — all words in search_name must be in scheme name
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

    Returns dict of canonical_name → status ("ok" / "not_found" / "error")
    """
    print("[mfapi] Fetching full AMFI fund list...")
    try:
        all_funds = _fetch_all_funds()
    except Exception as exc:
        print(f"[mfapi] ERROR fetching fund list: {exc}")
        return {name: "error" for name in FUND_SEARCH_TERMS}
    if not all_funds:
        print("[mfapi] ERROR: Could not fetch fund list from mfapi.in")
        return {name: "not_found" for name in FUND_SEARCH_TERMS}

    print(f"[mfapi] {len(all_funds)} funds in AMFI list")
    raw_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    for canonical_name, search_name in FUND_SEARCH_TERMS.items():
        print(f"[mfapi] Looking up: {search_name}")
        scheme_code = _find_scheme_code(all_funds, search_name)
        if not scheme_code:
            print(f"[mfapi]   NOT FOUND: {search_name}")
            results[canonical_name] = "not_found"
            continue

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
