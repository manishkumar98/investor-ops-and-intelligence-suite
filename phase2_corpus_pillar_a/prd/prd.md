# Phase 2 PRD — Corpus Ingestion (M1 RAG Build)
**Owner:** CPO | **Depends on:** Phase 1 complete

---

## Goal
Load 15–25 official public pages from AMC/SEBI/AMFI into two persistent ChromaDB collections so that Phase 5's FAQ engine can retrieve grounded, citable answers.

## Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P2-01 | Load 15–25 URLs from `SOURCE_MANIFEST.md`; only AMC, SEBI, AMFI domains | All URLs resolve; no third-party blogs |
| P2-02 | Chunk each document at 512 tokens with 64-token overlap | Chunk count = ceil(doc_tokens / (512-64)) ± 10% |
| P2-03 | Each chunk carries metadata: `source_url`, `corpus`, `chunk_id`, `loaded_at` | `collection.get()` returns all 4 metadata fields per chunk |
| P2-04 | Embed with `text-embedding-3-small`; fallback to `all-MiniLM-L6-v2` | Embedding dimension ∈ {1536, 384} |
| P2-05 | MF FAQ chunks → `mf_faq_corpus` collection | `mf_faq_corpus.count()` ≥ 30 after ingestion |
| P2-06 | Fee/charge chunks → `fee_corpus` collection | `fee_corpus.count()` ≥ 8 after ingestion |
| P2-07 | Re-ingestion skipped when source hash unchanged | Second `ingest()` call completes in < 2 s |
| P2-08 | Top-4 cosine retrieval on a known question returns chunk with matching `source_url` | Manual spot-check on 3 sample queries |

## Phase Gate Checklist
- [ ] `mf_faq_corpus.count()` ≥ 30
- [ ] `fee_corpus.count()` ≥ 8
- [ ] All chunks have 4 required metadata fields
- [ ] `pytest phase2_corpus/tests/ -v` exits 0
