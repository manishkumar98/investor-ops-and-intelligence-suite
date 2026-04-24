# Phase 2 — Corpus Ingestion (Pillar A)

**Status:** Complete | **Depends on:** Phase 1

## What this phase does

Fetches 30+ official public pages from SBI MF and INDMoney, extracts structured fund fields (AUM, NAV, exit load, expense ratio, etc.) into named slots, chunks the raw text, embeds everything, and stores it in two ChromaDB collections. Also ingests pre-scraped local files from `data/raw/`. The result is a persistent corpus that Phase 5's FAQ engine queries at runtime.

## Files

| File | Purpose |
|---|---|
| `url_loader.py` | Fetches URLs via BeautifulSoup with retry logic; collapses page text to single-space strings |
| `chunker.py` | Splits text into 512-token overlapping chunks; `make_structured_chunk()` creates a priority chunk from extracted field summaries |
| `embedder.py` | OpenAI `text-embedding-3-small` with automatic fallback to local `all-MiniLM-L6-v2` |
| `ingest.py` | Orchestrates fetch → extract → chunk → embed → upsert; writes `data/fund_snapshot.json`; hash guard skips re-ingestion when sources unchanged |
| `structured_extractor.py` | Regex-based field extractor tuned to collapsed single-line text; extracts 14 named slots per fund page |
| `prd/prd.md` | Requirements (P2-01 → P2-08) and acceptance criteria |
| `architecture/architecture.md` | 6-step pipeline design including structured extractor detail |
| `tests/test_corpus.py` | Unit + mock tests for all 8 requirements |
| `evals/eval_corpus.py` | Live retrieval spot-checks (3 queries × expected corpus) |

## Collections

| Collection | Content | Min count |
|---|---|---|
| `mf_faq_corpus` | Fund facts: NAV, AUM, benchmark, inception, category, capital gains guides | ≥ 30 chunks |
| `fee_corpus` | Fee data: exit load, expense ratio, TER, lock-in | ≥ 8 chunks |

## Structured fields extracted per fund

`aum` · `nav` · `exit_load` · `expense_ratio` · `min_sip` · `min_lumpsum` · `benchmark` · `fund_manager` · `risk` · `category` · `lock_in` · `inception_date` · `returns_1y` · `returns_3y`

Extracted values are merged into `data/fund_snapshot.json` on every ingest run. Later scrapes only fill in empty slots — they never overwrite populated data.

## Local raw files

Pre-scraped Playwright files in `data/raw/*.txt` are ingested by `ingest_local_files()`. Files named `*official*` go into both collections; files named `*indmoney*` go into `mf_faq_corpus` only. Each file uses M1-format: first line `Source URL: <url>`, then `---`, then content.

## Running ingest

```bash
# Normal run — skips if source list unchanged
python scripts/ingest_corpus.py

# Force re-fetch and re-extract everything
python scripts/ingest_corpus.py --force
```

## Running tests

```bash
pytest phase2_corpus_pillar_a/tests/ -v
```

## Running evals

```bash
python phase2_corpus_pillar_a/evals/eval_corpus.py
```

## Phase gate

- `mf_faq_corpus.count()` ≥ 30
- `fee_corpus.count()` ≥ 8
- All chunks have 4 required metadata fields (`source_url`, `corpus`, `chunk_id`, `loaded_at`)
- `data/fund_snapshot.json` written with ≥ 5 funds and ≥ 8 fields each
- `pytest phase2_corpus_pillar_a/tests/ -v` exits 0
