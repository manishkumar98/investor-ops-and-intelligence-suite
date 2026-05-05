"""Unit tests for mfapi_loader.py — mocked, no live network calls."""
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from phase2_corpus_pillar_a.mfapi_loader import (
    FUND_SEARCH_TERMS,
    _calculate_returns,
    _find_scheme_code,
    format_fund_as_text,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

MOCK_FUND_LIST = [
    {"schemeCode": 119598, "schemeName": "SBI Bluechip Fund - Direct Plan Growth"},
    {"schemeCode": 125494, "schemeName": "SBI Flexicap Fund - Direct Plan Growth"},
    {"schemeCode": 119755, "schemeName": "SBI Long Term Equity Fund - Direct Plan Growth"},
    {"schemeCode": 125354, "schemeName": "SBI Small Cap Fund - Direct Plan Growth"},
    {"schemeCode": 119791, "schemeName": "SBI Magnum Midcap Fund - Direct Plan Growth"},
    {"schemeCode": 119597, "schemeName": "SBI Focused Equity Fund - Direct Plan Growth"},
    {"schemeCode": 119551, "schemeName": "SBI Liquid Fund - Direct Plan Growth"},
    {"schemeCode": 125174, "schemeName": "SBI Contra Fund - Direct Plan Growth"},
    {"schemeCode": 125172, "schemeName": "SBI Technology Opportunities Fund - Direct Plan Growth"},
    {"schemeCode": 119552, "schemeName": "SBI Healthcare Opportunities Fund - Direct Plan Growth"},
    {"schemeCode": 119775, "schemeName": "SBI Equity Hybrid Fund - Direct Plan Growth"},
    {"schemeCode": 119793, "schemeName": "SBI Magnum Global Fund - Direct Plan Growth"},
]

def _make_nav_data(n: int = 100) -> list[dict]:
    """Generate synthetic NAV history with descending dates."""
    today = date.today()
    return [
        {"date": (today - timedelta(days=i)).strftime("%d-%m-%Y"), "nav": str(round(100 + i * 0.1, 4))}
        for i in range(n)
    ]

MOCK_SCHEME_RESPONSE = {
    "status": "SUCCESS",
    "meta": {
        "fund_house":       "SBI Mutual Fund",
        "scheme_type":      "Open Ended Schemes",
        "scheme_category":  "Equity Scheme - Large Cap Fund",
        "scheme_code":      119598,
        "scheme_name":      "SBI Bluechip Fund - Direct Plan Growth",
    },
    "data": _make_nav_data(400),
}


# ── FUND_SEARCH_TERMS coverage ────────────────────────────────────────────────

class TestFundSearchTerms:
    def test_all_12_funds_present(self):
        assert len(FUND_SEARCH_TERMS) == 12

    def test_all_values_are_direct_growth(self):
        for canonical, search in FUND_SEARCH_TERMS.items():
            assert "Direct Plan Growth" in search or "Direct Growth" in search, (
                f"{canonical}: search term missing 'Direct Plan Growth'"
            )

    def test_canonical_names_are_sbi_funds(self):
        for name in FUND_SEARCH_TERMS:
            assert name.startswith("SBI "), f"Expected 'SBI ' prefix: {name}"


# ── _find_scheme_code ────────────────────────────────────────────────────────

class TestFindSchemeCode:
    def test_exact_match(self):
        code = _find_scheme_code(MOCK_FUND_LIST, "SBI Bluechip Fund - Direct Plan Growth")
        assert code == 119598

    def test_case_insensitive_exact(self):
        code = _find_scheme_code(MOCK_FUND_LIST, "sbi bluechip fund - direct plan growth")
        assert code == 119598

    def test_partial_match_fallback(self):
        # Partial: all significant words present
        code = _find_scheme_code(MOCK_FUND_LIST, "SBI Flexicap Fund Direct Plan Growth")
        assert code == 125494

    def test_not_found_returns_none(self):
        code = _find_scheme_code(MOCK_FUND_LIST, "SBI Nonexistent Fund - Direct Plan Growth")
        assert code is None

    def test_empty_list_returns_none(self):
        assert _find_scheme_code([], "SBI Bluechip Fund - Direct Plan Growth") is None

    def test_all_12_search_terms_resolve(self):
        """Every fund in FUND_SEARCH_TERMS must resolve against the mock list."""
        for canonical, search_name in FUND_SEARCH_TERMS.items():
            code = _find_scheme_code(MOCK_FUND_LIST, search_name)
            assert code is not None, f"Could not resolve: {canonical} → '{search_name}'"


# ── _calculate_returns ────────────────────────────────────────────────────────

class TestCalculateReturns:
    def test_empty_data_returns_empty(self):
        result = _calculate_returns([])
        assert result == {}

    def test_nav_extracted(self):
        nav_data = _make_nav_data(10)
        result = _calculate_returns(nav_data)
        assert "nav" in result
        assert result["nav"].startswith("₹")

    def test_inception_date_is_oldest(self):
        nav_data = _make_nav_data(100)
        result = _calculate_returns(nav_data)
        assert "inception_date" in result
        oldest = (date.today() - timedelta(days=99)).isoformat()
        assert result["inception_date"] == oldest

    def test_1y_return_calculated_with_enough_data(self):
        nav_data = _make_nav_data(400)
        result = _calculate_returns(nav_data)
        assert "returns_1y" in result
        assert result["returns_1y"].endswith("%")

    def test_3y_return_only_with_sufficient_history(self):
        # Only 100 days — no 3Y return possible
        result = _calculate_returns(_make_nav_data(100))
        assert "returns_3y" not in result

    def test_invalid_nav_skipped(self):
        bad_data = [
            {"date": "01-01-2026", "nav": "invalid"},
            {"date": "01-01-2025", "nav": "95.00"},
        ]
        result = _calculate_returns(bad_data)
        assert "nav" in result  # valid entry processed

    def test_both_date_formats_parsed(self):
        mixed = [
            {"date": "30-04-2026", "nav": "100.00"},   # dd-mm-yyyy
            {"date": "2024-04-30", "nav": "90.00"},     # yyyy-mm-dd
        ]
        result = _calculate_returns(mixed)
        assert "nav" in result


# ── format_fund_as_text ───────────────────────────────────────────────────────

class TestFormatFundAsText:
    def setup_method(self):
        self.meta     = MOCK_SCHEME_RESPONSE["meta"]
        self.nav_data = MOCK_SCHEME_RESPONSE["data"]

    def test_output_is_string(self):
        text = format_fund_as_text("SBI Large Cap Fund", self.meta, self.nav_data)
        assert isinstance(text, str)
        assert len(text) > 100

    def test_source_url_present(self):
        text = format_fund_as_text("SBI Large Cap Fund", self.meta, self.nav_data)
        assert "Source URL:" in text
        assert "mfapi.in/mf/119598" in text

    def test_canonical_name_in_output(self):
        text = format_fund_as_text("SBI Large Cap Fund", self.meta, self.nav_data)
        assert "SBI Large Cap Fund" in text

    def test_fund_house_in_output(self):
        text = format_fund_as_text("SBI Large Cap Fund", self.meta, self.nav_data)
        assert "SBI Mutual Fund" in text

    def test_nav_history_capped_at_10(self):
        text = format_fund_as_text("SBI Large Cap Fund", self.meta, self.nav_data)
        lines = [l for l in text.splitlines() if "NAV:" in l and "₹" in l]
        # Includes the summary NAV line + up to 10 history lines
        assert len(lines) <= 12

    def test_faq_section_present(self):
        text = format_fund_as_text("SBI Large Cap Fund", self.meta, self.nav_data)
        assert "Frequently Asked Questions" in text

    def test_empty_nav_data_handled(self):
        text = format_fund_as_text("SBI Large Cap Fund", self.meta, [])
        assert isinstance(text, str)
        assert "SBI Large Cap Fund" in text

    def test_missing_meta_fields_handled(self):
        text = format_fund_as_text("SBI Large Cap Fund", {}, self.nav_data)
        assert isinstance(text, str)

    def test_scraped_date_in_output(self):
        text = format_fund_as_text("SBI Large Cap Fund", self.meta, self.nav_data)
        assert str(date.today()) in text


# ── fetch_all_sbi_funds (mocked network) ─────────────────────────────────────

class TestFetchAllSbiFunds:
    def test_writes_12_files_on_success(self, tmp_path):
        from phase2_corpus_pillar_a.mfapi_loader import fetch_all_sbi_funds

        with patch("phase2_corpus_pillar_a.mfapi_loader._fetch_all_funds",
                   return_value=MOCK_FUND_LIST), \
             patch("phase2_corpus_pillar_a.mfapi_loader._fetch_scheme_data",
                   return_value=MOCK_SCHEME_RESPONSE):
            results = fetch_all_sbi_funds(tmp_path, delay_seconds=0)

        assert len(results) == 12
        ok_count = sum(1 for s in results.values() if s == "ok")
        assert ok_count == 12
        written = list(tmp_path.glob("*_(mfapi).txt"))
        assert len(written) == 12

    def test_empty_fund_list_marked_not_found(self, tmp_path):
        from phase2_corpus_pillar_a.mfapi_loader import fetch_all_sbi_funds

        # Empty list → _find_scheme_code returns None → "not_found" per fund
        with patch("phase2_corpus_pillar_a.mfapi_loader._fetch_all_funds",
                   return_value=[{"schemeCode": 1, "schemeName": "Unrelated Fund"}]):
            results = fetch_all_sbi_funds(tmp_path, delay_seconds=0)

        assert all(s == "not_found" for s in results.values())
        assert len(list(tmp_path.glob("*_(mfapi).txt"))) == 0

    def test_api_failure_marked_as_error(self, tmp_path):
        from phase2_corpus_pillar_a.mfapi_loader import fetch_all_sbi_funds

        bad_response = {"status": "FAILURE", "meta": {}, "data": []}
        with patch("phase2_corpus_pillar_a.mfapi_loader._fetch_all_funds",
                   return_value=MOCK_FUND_LIST), \
             patch("phase2_corpus_pillar_a.mfapi_loader._fetch_scheme_data",
                   return_value=bad_response):
            results = fetch_all_sbi_funds(tmp_path, delay_seconds=0)

        assert all(s == "error" for s in results.values())

    def test_network_exception_marked_as_error(self, tmp_path):
        from phase2_corpus_pillar_a.mfapi_loader import fetch_all_sbi_funds

        with patch("phase2_corpus_pillar_a.mfapi_loader._fetch_all_funds",
                   side_effect=Exception("network timeout")):
            results = fetch_all_sbi_funds(tmp_path, delay_seconds=0)

        assert all(s == "error" for s in results.values())

    def test_written_file_is_valid_m1_format(self, tmp_path):
        from phase2_corpus_pillar_a.mfapi_loader import fetch_all_sbi_funds

        with patch("phase2_corpus_pillar_a.mfapi_loader._fetch_all_funds",
                   return_value=MOCK_FUND_LIST), \
             patch("phase2_corpus_pillar_a.mfapi_loader._fetch_scheme_data",
                   return_value=MOCK_SCHEME_RESPONSE):
            fetch_all_sbi_funds(tmp_path, delay_seconds=0)

        files = list(tmp_path.glob("*_(mfapi).txt"))
        assert files
        content = files[0].read_text(encoding="utf-8")
        assert content.startswith("Source URL:")
        assert "Scraped Date:" in content
        assert "---" in content
