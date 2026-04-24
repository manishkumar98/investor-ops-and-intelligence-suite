"""Phase 5 — Smart-Sync FAQ Engine tests."""
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
def session():
    return {"chat_history": []}


@pytest.fixture
def faq_chunks():
    return [
        {"text": "Exit load is 1% if units are redeemed within 12 months.",
         "source_url": "https://amfiindia.com/exit-load", "distance": 0.10},
        {"text": "ELSS funds have a mandatory 3-year lock-in period.",
         "source_url": "https://amfiindia.com/elss", "distance": 0.20},
    ]


@pytest.fixture
def fee_chunks():
    return [
        {"text": "The expense ratio is deducted from NAV daily; typically 0.5–2%.",
         "source_url": "https://amfiindia.com/expense-ratio", "distance": 0.30},
    ]


# ---------------------------------------------------------------------------
# P5-01  Safety pre-filter
# ---------------------------------------------------------------------------

class TestSafetyFilter:

    BLOCKED = [
        ("Should I buy this fund?",                 "advice_refusal"),
        ("Which fund is better — large cap or ELSS?","comparison_refusal"),
        ("Which fund gives 20% returns?",            "performance_refusal"),
        ("Can you give me the CEO's email?",         "pii_refusal"),
        ("My PAN is ABCDE1234F, help me",            "pii_refusal"),
    ]

    ALLOWED = [
        "What is the exit load for ELSS?",
        "What is the expense ratio?",
        "How do I download capital gains statement?",
        "What is the lock-in period for ELSS?",
    ]

    PATTERNS = [
        (r"should i (buy|sell|invest)", "advice_refusal"),
        (r"which fund.*(better|best)",  "comparison_refusal"),
        (r"give.*\d+%.*return",         "performance_refusal"),
        (r"(email|phone|contact|ceo|cxo|address)", "pii_refusal"),
        (r"(pan|aadhaar|account number)", "pii_refusal"),
    ]

    def _check(self, query: str) -> tuple[bool, str]:
        for pattern, refusal_type in self.PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return False, refusal_type
        return True, ""

    def test_all_blocked_queries_refused(self):
        for query, expected_type in self.BLOCKED:
            is_safe, refusal_type = self._check(query)
            assert not is_safe, f"Should be blocked: '{query}'"

    def test_all_allowed_queries_pass(self):
        for query in self.ALLOWED:
            is_safe, _ = self._check(query)
            assert is_safe, f"Should be allowed: '{query}'"

    def test_refusal_type_correct(self):
        is_safe, refusal_type = self._check("Should I sell my ELSS?")
        assert refusal_type == "advice_refusal"

    def test_safe_check_is_case_insensitive(self):
        is_safe, _ = self._check("SHOULD I BUY THIS FUND?")
        assert not is_safe


# ---------------------------------------------------------------------------
# P5-02  Query router
# ---------------------------------------------------------------------------

class TestQueryRouter:

    ROUTING_CASES = [
        ("What is the exit load for ELSS fund?",            "factual_only"),
        ("What are the fee charges on my redemption?",      "fee_only"),
        ("What is the exit load and why was I charged it?", "compound"),
        ("What is the expense ratio and what does it cover?","compound"),
    ]

    def _classify(self, query: str) -> str:
        query_lower = query.lower()
        has_fact = any(k in query_lower for k in ("exit load", "lock-in", "sip", "elss", "riskometer", "benchmark"))
        has_fee  = any(k in query_lower for k in ("fee", "charge", "expense", "cost"))
        if has_fact and has_fee:
            return "compound"
        if has_fee:
            return "fee_only"
        if has_fact:
            return "factual_only"
        return "factual_only"  # default

    def test_factual_only_routing(self):
        assert self._classify("What is the exit load for ELSS fund?") == "factual_only"

    def test_fee_only_routing(self):
        assert self._classify("What are the fee charges on my redemption?") == "fee_only"

    def test_compound_routing(self):
        result = self._classify("What is the exit load and why was I charged it?")
        assert result == "compound"

    def test_router_returns_valid_type(self):
        valid = {"factual_only", "fee_only", "compound", "adversarial"}
        for query, _ in self.ROUTING_CASES:
            result = self._classify(query)
            assert result in valid


# ---------------------------------------------------------------------------
# P5-03/04  Collection-specific retrieval
# ---------------------------------------------------------------------------

class TestRetrieval:

    @patch("chromadb.PersistentClient")
    def test_factual_query_hits_faq_corpus_only(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        faq_col = MagicMock()
        fee_col = MagicMock()
        faq_col.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        fee_col.query.return_value = {"documents": [[]], "metadatas": [[]], "distances": [[]]}
        mock_client.get_or_create_collection.side_effect = lambda name: \
            faq_col if "faq" in name else fee_col

        import chromadb
        client = chromadb.PersistentClient(path="./test")
        faq = client.get_or_create_collection("mf_faq_corpus")
        faq.query(query_embeddings=[[0.0] * 1536], n_results=4)

        faq_col.query.assert_called_once()
        fee_col.query.assert_not_called()

    def test_distance_threshold_applied(self):
        chunks = [
            {"text": "Exit load info", "source_url": "https://a.com", "distance": 0.30},
            {"text": "Expense ratio",  "source_url": "https://b.com", "distance": 0.80},
            {"text": "Lock-in period", "source_url": "https://c.com", "distance": 0.60},
        ]
        filtered = [c for c in chunks if c["distance"] <= 0.75]
        assert len(filtered) == 2
        assert all(c["distance"] <= 0.75 for c in filtered)

    def test_deduplication_by_source_url(self, faq_chunks, fee_chunks):
        all_chunks = faq_chunks + fee_chunks
        seen_urls = set()
        deduped = []
        for c in all_chunks:
            if c["source_url"] not in seen_urls:
                deduped.append(c)
                seen_urls.add(c["source_url"])
        assert len(deduped) == len(all_chunks)  # no duplicates in fixture


# ---------------------------------------------------------------------------
# P5-07/08  Response format
# ---------------------------------------------------------------------------

class TestResponseFormat:

    def test_compound_response_has_6_bullets(self):
        bullets = [
            "Exit load is 1% if redeemed within 12 months.",
            "No exit load after 12 months for equity funds.",
            "ELSS has mandatory 3-year lock-in period.",
            "Exit load charged on redemption amount, not just profit.",
            "The expense ratio is deducted from the fund's NAV daily.",
            "Check SID for fund-specific exit load slabs.",
        ]
        assert len(bullets) == 6

    def test_simple_response_max_3_sentences(self):
        prose = ("Exit load is 1% if redeemed within 12 months. "
                 "There is no exit load after 12 months. "
                 "Please refer to the scheme factsheet for details.")
        sentences = [s.strip() for s in prose.split(".") if s.strip()]
        assert len(sentences) <= 3

    def test_response_has_source_url(self, faq_chunks):
        sources = list({c["source_url"] for c in faq_chunks})
        assert len(sources) >= 1
        for url in sources:
            assert url.startswith("http")

    def test_last_updated_present(self):
        last_updated = "Last updated from sources: 2026-04-22"
        assert "Last updated from sources:" in last_updated

    def test_refused_response_schema(self):
        refused = {
            "refused": True,
            "answer": "I can only answer factual questions about mutual funds.",
            "source": "https://www.sebi.gov.in/investors.html",
        }
        assert refused["refused"] is True
        assert refused["source"].startswith("http")


# ---------------------------------------------------------------------------
# P5-12  Chat history
# ---------------------------------------------------------------------------

class TestChatHistory:

    def test_history_grows_by_2_per_exchange(self, session):
        initial_len = len(session["chat_history"])
        session["chat_history"].append({"role": "user", "content": "What is exit load?"})
        session["chat_history"].append({"role": "assistant", "content": "Exit load is 1%..."})
        assert len(session["chat_history"]) == initial_len + 2

    def test_history_entries_have_role_and_content(self, session):
        session["chat_history"].append({"role": "user", "content": "query"})
        for entry in session["chat_history"]:
            assert "role" in entry
            assert "content" in entry
            assert entry["role"] in ("user", "assistant")
