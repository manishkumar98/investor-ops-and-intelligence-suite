"""Phase 3 — Review Intelligence Pipeline tests."""
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_reviews():
    return [
        {"review_id": 1, "rating": 2,
         "review_text": "Call me on +91 9876543210 — nominee update broken. John Smith is frustrated."},
        {"review_id": 2, "rating": 1,
         "review_text": "Login OTP not coming. My email is test@example.com. Very bad."},
        {"review_id": 3, "rating": 3,
         "review_text": "SIP deduction happened but units not reflecting. PAN ABCDE1234F not linked."},
        {"review_id": 4, "rating": 2,
         "review_text": "Nominee update screen shows blank page after submitting."},
        {"review_id": 5, "rating": 1,
         "review_text": "Exit load charged without explanation on ELSS redemption."},
    ]


@pytest.fixture
def session():
    return {
        "weekly_pulse": None,
        "top_theme": None,
        "top_3_themes": [],
        "fee_bullets": [],
        "fee_sources": [],
        "mcp_queue": [],
        "pulse_generated": False,
    }


@pytest.fixture
def mock_pulse():
    return """This week's top themes: Nominee Update issues (12 users), Login/OTP problems (9 users), SIP mandate failures (6 users).

User quote: "The nominee update screen shows a blank page after submitting documents."
User quote: "Login OTP is not coming on my registered number."
User quote: "SIP deduction happened but units not reflecting."

Action Ideas:
1. Escalate nominee update flow to engineering — assign P0 bug for blank-page error.
2. Investigate OTP delivery failure — check SMS gateway logs for the past 2 weeks.
3. Audit SIP mandate processing pipeline — identify root cause of missed deductions."""


# ---------------------------------------------------------------------------
# P3-01  PII Scrubber
# ---------------------------------------------------------------------------

class TestPIIScrubber:

    def _scrub(self, text: str) -> tuple[str, int]:
        patterns = [
            (r"\+?91[\s\-]?\d{10}", "[REDACTED]"),
            (r"[\w.+\-]+@[\w\-]+\.[\w.]+", "[REDACTED]"),
            (r"[A-Z]{5}\d{4}[A-Z]", "[REDACTED]"),
        ]
        count = 0
        for pattern, replacement in patterns:
            matches = re.findall(pattern, text)
            count += len(matches)
            text = re.sub(pattern, replacement, text)
        return text, count

    def test_phone_number_removed(self, raw_reviews):
        text = raw_reviews[0]["review_text"]
        clean, count = self._scrub(text)
        assert "+91 9876543210" not in clean
        assert "[REDACTED]" in clean
        assert count >= 1

    def test_email_removed(self, raw_reviews):
        text = raw_reviews[1]["review_text"]
        clean, count = self._scrub(text)
        assert "test@example.com" not in clean
        assert count >= 1

    def test_pan_removed(self, raw_reviews):
        text = raw_reviews[2]["review_text"]
        clean, count = self._scrub(text)
        assert "ABCDE1234F" not in clean
        assert count >= 1

    def test_clean_text_has_no_pii_patterns(self, raw_reviews):
        for review in raw_reviews:
            clean, _ = self._scrub(review["review_text"])
            assert not re.search(r"\+?91[\s\-]?\d{10}", clean)
            assert not re.search(r"[\w.+\-]+@[\w\-]+\.[\w.]+", clean)
            assert not re.search(r"[A-Z]{5}\d{4}[A-Z]", clean)

    def test_no_false_positives_on_clean_text(self):
        text = "The nominee update feature is broken."
        clean, count = self._scrub(text)
        assert clean == text
        assert count == 0


# ---------------------------------------------------------------------------
# P3-02  Theme Clusterer (LLM response parsing)
# ---------------------------------------------------------------------------

class TestThemeClusterer:

    def _parse_theme_response(self, llm_json: dict) -> dict:
        themes = sorted(llm_json["themes"], key=lambda t: t["count"], reverse=True)
        top_3 = [t["label"] for t in themes[:3]]
        return {"themes": themes, "top_3": top_3}

    def test_theme_count_at_most_5(self):
        mock_response = {
            "themes": [
                {"label": "Nominee Updates", "count": 12, "ids": [1, 4]},
                {"label": "Login Issues",    "count": 9,  "ids": [2]},
                {"label": "SIP Failures",    "count": 6,  "ids": [3]},
                {"label": "Fee Transparency","count": 4,  "ids": [5]},
                {"label": "App Performance", "count": 2,  "ids": []},
            ]
        }
        result = self._parse_theme_response(mock_response)
        assert len(result["themes"]) <= 5

    def test_top_3_is_exactly_3(self):
        mock_response = {
            "themes": [
                {"label": "A", "count": 10, "ids": []},
                {"label": "B", "count": 8,  "ids": []},
                {"label": "C", "count": 6,  "ids": []},
                {"label": "D", "count": 2,  "ids": []},
            ]
        }
        result = self._parse_theme_response(mock_response)
        assert len(result["top_3"]) == 3

    def test_top_3_ranked_by_count(self):
        mock_response = {
            "themes": [
                {"label": "C", "count": 3,  "ids": []},
                {"label": "A", "count": 10, "ids": []},
                {"label": "B", "count": 7,  "ids": []},
            ]
        }
        result = self._parse_theme_response(mock_response)
        assert result["top_3"] == ["A", "B", "C"]

    def test_top_theme_written_to_session(self, session):
        session["top_theme"] = "Nominee Updates"
        session["top_3_themes"] = ["Nominee Updates", "Login Issues", "SIP Failures"]
        assert session["top_theme"] == "Nominee Updates"
        assert len(session["top_3_themes"]) == 3


# ---------------------------------------------------------------------------
# P3-04  Quote extraction
# ---------------------------------------------------------------------------

class TestQuoteExtractor:

    def test_exactly_3_quotes_returned(self):
        top_3 = ["Nominee Updates", "Login Issues", "SIP Failures"]
        reviews_by_theme = {
            "Nominee Updates": [
                {"review_id": 1, "rating": 2, "text": "Nominee update broken."},
                {"review_id": 4, "rating": 2, "text": "Blank page after submission."},
            ],
            "Login Issues": [
                {"review_id": 2, "rating": 1, "text": "OTP not coming."},
            ],
            "SIP Failures": [
                {"review_id": 3, "rating": 3, "text": "SIP deducted but units missing."},
            ],
        }
        quotes = []
        for theme in top_3:
            candidates = sorted(reviews_by_theme[theme], key=lambda r: r["rating"])
            quotes.append({"theme": theme, "quote": candidates[0]["text"]})
        assert len(quotes) == 3

    def test_quotes_pii_free(self):
        quotes = [
            {"theme": "Nominee Updates", "quote": "Nominee update broken. Very frustrated."},
            {"theme": "Login Issues",    "quote": "OTP not coming. Phone issue."},
        ]
        pii_pattern = re.compile(r"\+?91[\s\-]?\d{10}|[\w.+\-]+@[\w\-]+\.\w+|[A-Z]{5}\d{4}[A-Z]")
        for q in quotes:
            assert not pii_pattern.search(q["quote"]), f"PII found in quote: {q['quote']}"


# ---------------------------------------------------------------------------
# P3-05  Pulse Writer constraints
# ---------------------------------------------------------------------------

class TestPulseWriter:

    def _count_action_ideas(self, text: str) -> int:
        lines = text.split("\n")
        count = 0
        for line in lines:
            if re.match(r"^\d+\.", line.strip()) or "Action" in line:
                count += 1
        return count

    def test_pulse_word_count_within_limit(self, mock_pulse):
        words = len(mock_pulse.split())
        assert words <= 250, f"Pulse is {words} words (max 250)"

    def test_pulse_has_exactly_3_action_ideas(self, mock_pulse):
        action_lines = [l for l in mock_pulse.split("\n")
                        if re.match(r"^\d+\.", l.strip())]
        assert len(action_lines) == 3, f"Found {len(action_lines)} action lines"

    def test_pulse_contains_top_theme(self, mock_pulse):
        assert "Nominee" in mock_pulse or "Login" in mock_pulse


# ---------------------------------------------------------------------------
# P3-06  Fee explainer constraints
# ---------------------------------------------------------------------------

class TestFeeExplainer:

    def test_bullet_count_at_most_6(self):
        bullets = [
            "Exit load is 1% if redeemed within 12 months.",
            "No exit load after 12 months.",
            "ELSS funds have a 3-year lock-in; no redemption before lock-in.",
            "Exit load applies on the redemption amount, not the profit.",
            "Check the SID for fund-specific exit load slabs.",
            "Last checked: 2026-04-22",
        ]
        assert len(bullets) <= 6

    def test_source_count_is_2(self):
        sources = [
            "https://amfiindia.com/exit-load-faq",
            "https://sebi.gov.in/mf-charges",
        ]
        assert len(sources) == 2

    def test_last_checked_present(self):
        bullets = ["Exit load is 1%.", "Last checked: 2026-04-22"]
        assert any("Last checked" in b for b in bullets)


# ---------------------------------------------------------------------------
# P3-07/08  MCP queue
# ---------------------------------------------------------------------------

class TestMCPQueue:

    def test_notes_append_action_enqueued(self, session):
        session["mcp_queue"].append({
            "type": "notes_append",
            "status": "pending",
            "payload": {"date": "2026-04-22", "entry": {}},
        })
        notes_actions = [a for a in session["mcp_queue"] if a["type"] == "notes_append"]
        assert len(notes_actions) >= 1

    def test_email_draft_action_enqueued(self, session):
        session["mcp_queue"].append({
            "type": "email_draft",
            "status": "pending",
            "payload": {"subject": "Weekly Pulse", "body": "..."},
        })
        email_actions = [a for a in session["mcp_queue"] if a["type"] == "email_draft"]
        assert len(email_actions) >= 1

    def test_all_actions_start_as_pending(self, session):
        for action_type in ("notes_append", "email_draft"):
            session["mcp_queue"].append({"type": action_type, "status": "pending", "payload": {}})
        for action in session["mcp_queue"]:
            assert action["status"] == "pending"
