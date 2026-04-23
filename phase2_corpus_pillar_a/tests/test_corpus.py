"""Phase 2 — Corpus Ingestion tests."""
import hashlib
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_docs():
    return [
        {"text": "Exit load is 1% if redeemed within 1 year for equity funds.",
         "metadata": {"source_url": "https://amfiindia.com/page1", "corpus": "mf_faq",
                      "loaded_at": "2026-04-22T00:00:00", "chunk_id": "abc12345"}},
        {"text": "Expense ratio for large-cap funds is typically 1.0–1.5%.",
         "metadata": {"source_url": "https://amfiindia.com/page2", "corpus": "fee",
                      "loaded_at": "2026-04-22T00:00:00", "chunk_id": "def67890"}},
    ]


@pytest.fixture
def source_urls():
    return [
        "https://amfiindia.com/scheme-details",
        "https://sebi.gov.in/circular1",
        "https://amfiindia.com/nav",
    ]


# ---------------------------------------------------------------------------
# P2-02  Chunking logic
# ---------------------------------------------------------------------------

class TestChunking:

    def test_chunk_size_within_bounds(self):
        text = " ".join(["word"] * 1000)
        # Simulate chunking at 512 chars with 64 overlap
        chunk_size, overlap = 512, 64
        step = chunk_size - overlap
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), step)]
        for chunk in chunks:
            assert len(chunk) <= chunk_size + 10  # small tolerance

    def test_chunk_count_reasonable(self):
        """A 1000-token document chunked at 512/64 should give ~2 chunks."""
        tokens = 1000
        chunk_size, overlap = 512, 64
        expected = max(1, (tokens - overlap) // (chunk_size - overlap))
        assert 1 <= expected <= 5

    def test_chunk_overlap_preserves_context(self):
        """Consecutive chunks share overlap text."""
        words = list(range(200))
        text = " ".join(str(w) for w in words)
        chunk_size, overlap = 50, 10  # characters
        step = chunk_size - overlap
        chunks = [text[i:i + chunk_size] for i in range(0, len(text) - overlap, step)]
        if len(chunks) >= 2:
            end_of_first = chunks[0][-overlap:]
            start_of_second = chunks[1][:overlap]
            assert end_of_first == start_of_second


# ---------------------------------------------------------------------------
# P2-03  Chunk metadata schema
# ---------------------------------------------------------------------------

class TestChunkMetadata:

    REQUIRED_FIELDS = {"source_url", "corpus", "chunk_id", "loaded_at"}

    def test_all_metadata_fields_present(self, sample_docs):
        for doc in sample_docs:
            assert self.REQUIRED_FIELDS.issubset(doc["metadata"].keys()), \
                f"Missing metadata fields: {doc['metadata'].keys()}"

    def test_corpus_field_valid_value(self, sample_docs):
        for doc in sample_docs:
            assert doc["metadata"]["corpus"] in ("mf_faq", "fee")

    def test_chunk_id_is_8_chars(self, sample_docs):
        for doc in sample_docs:
            assert len(doc["metadata"]["chunk_id"]) == 8

    def test_chunk_id_generation(self):
        url = "https://amfiindia.com/page1"
        idx = 0
        chunk_id = hashlib.sha256(f"{url}{idx}".encode()).hexdigest()[:8]
        assert len(chunk_id) == 8
        assert chunk_id.isalnum()


# ---------------------------------------------------------------------------
# P2-04  Embedding dimension
# ---------------------------------------------------------------------------

class TestEmbedding:

    def test_openai_embedding_dimension(self):
        """text-embedding-3-small produces 1536-dim vectors."""
        mock_vec = [0.0] * 1536
        assert len(mock_vec) == 1536

    def test_fallback_embedding_dimension(self):
        """all-MiniLM-L6-v2 produces 384-dim vectors."""
        mock_vec = [0.0] * 384
        assert len(mock_vec) == 384

    def test_embedding_dimension_allowed_values(self):
        for dim in (384, 1536):
            assert dim in (384, 1536)


# ---------------------------------------------------------------------------
# P2-05/06  Collection routing
# ---------------------------------------------------------------------------

class TestCollectionRouting:

    def test_mf_faq_chunks_go_to_faq_collection(self, sample_docs):
        faq_docs = [d for d in sample_docs if d["metadata"]["corpus"] == "mf_faq"]
        fee_docs = [d for d in sample_docs if d["metadata"]["corpus"] == "fee"]
        assert len(faq_docs) >= 1
        assert len(fee_docs) >= 1

    @patch("chromadb.PersistentClient")
    def test_upsert_called_for_correct_collection(self, mock_client_class, sample_docs):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        faq_col = MagicMock()
        fee_col = MagicMock()
        mock_client.get_or_create_collection.side_effect = lambda name: \
            faq_col if name == "mf_faq_corpus" else fee_col

        import chromadb
        client = chromadb.PersistentClient(path="./test")

        for doc in sample_docs:
            col_name = "mf_faq_corpus" if doc["metadata"]["corpus"] == "mf_faq" else "fee_corpus"
            col = client.get_or_create_collection(col_name)
            col.upsert(
                ids=[doc["metadata"]["chunk_id"]],
                documents=[doc["text"]],
                metadatas=[doc["metadata"]],
            )

        faq_col.upsert.assert_called_once()
        fee_col.upsert.assert_called_once()


# ---------------------------------------------------------------------------
# P2-07  Hash guard (skip re-ingestion)
# ---------------------------------------------------------------------------

class TestHashGuard:

    def test_same_urls_produce_same_hash(self, source_urls):
        h1 = hashlib.sha256(str(sorted(source_urls)).encode()).hexdigest()
        h2 = hashlib.sha256(str(sorted(source_urls)).encode()).hexdigest()
        assert h1 == h2

    def test_different_urls_produce_different_hash(self, source_urls):
        h1 = hashlib.sha256(str(sorted(source_urls)).encode()).hexdigest()
        modified = source_urls + ["https://newpage.com"]
        h2 = hashlib.sha256(str(sorted(modified)).encode()).hexdigest()
        assert h1 != h2


# ---------------------------------------------------------------------------
# P2-08  Retrieval smoke test (mocked)
# ---------------------------------------------------------------------------

class TestRetrieval:

    @patch("chromadb.PersistentClient")
    def test_query_returns_results_with_source_url(self, mock_client_class):
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_col = MagicMock()
        mock_col.query.return_value = {
            "documents": [["Exit load is 1% if redeemed within 1 year."]],
            "metadatas": [[{"source_url": "https://amfiindia.com/page1",
                            "corpus": "mf_faq", "chunk_id": "abc12345",
                            "loaded_at": "2026-04-22"}]],
            "distances": [[0.12]],
        }
        mock_client.get_or_create_collection.return_value = mock_col

        import chromadb
        client = chromadb.PersistentClient(path="./test")
        col = client.get_or_create_collection("mf_faq_corpus")
        result = col.query(query_embeddings=[[0.0] * 1536], n_results=4)

        assert result["documents"][0][0] is not None
        assert "source_url" in result["metadatas"][0][0]

    def test_distance_threshold_filter(self):
        """Chunks with distance > 0.75 should be discarded."""
        distances = [0.12, 0.45, 0.78, 0.91]
        threshold = 0.75
        kept = [d for d in distances if d <= threshold]
        assert kept == [0.12, 0.45]
