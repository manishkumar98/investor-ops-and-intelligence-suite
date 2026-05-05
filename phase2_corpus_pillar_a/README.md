# Phase 2 — Corpus Ingestion (Pillar A)

**Status:** Complete | **Depends on:** Phase 1

## What this phase does

Builds the full RAG corpus for all 12 SBI Mutual Fund schemes from three complementary sources:

1. **Live URL scraping** — 42 URLs from `SOURCE_MANIFEST.md` (sbimf.com, Groww, INDMoney, AMFI, SEBI, MFCentral). Some URLs may be blocked (403/404); failures are handled gracefully.
2. **Local raw files** — `data/raw/*.txt` pre-authored files covering all 12 funds (official scheme data, INDMoney metrics, Groww details) plus AMFI investor education and SEBI regulatory content. Always succeeds — no network dependency.
3. **mfapi.in (AMFI live data)** — `mfapi_loader.py` fetches live NAV + calculated returns for all 12 funds directly from AMFI via the free `api.mfapi.in` API. No scraping, no auth, no blocks. Writes `data/raw/*_(mfapi).txt` on every sync, then picked up by `ingest_local_files()`.

The result is a persistent ChromaDB corpus that Phase 5's FAQ engine queries at runtime.

## Files

| File | Purpose |
|---|---|
| `url_loader.py` | Fetches URLs via BeautifulSoup with retry logic; collapses page text to single-space strings |
| `chunker.py` | Splits text into 512-token overlapping chunks; `make_structured_chunk()` creates a priority chunk from extracted field summaries |
| `embedder.py` | OpenAI `text-embedding-3-small` with automatic fallback to local `all-MiniLM-L6-v2` |
| `ingest.py` | Orchestrates fetch → extract → chunk → embed → upsert; exposes `ingest_local_files()`, `ingest_mfapi_funds()`, `ingest_single_url()`; writes `data/fund_snapshot.json` |
| `mfapi_loader.py` | Fetches live NAV + return history for all 12 SBI funds from `api.mfapi.in` (AMFI data); writes `*_(mfapi).txt` to `data/raw/`; no API key or scraping required |
| `structured_extractor.py` | Regex-based field extractor for 14 named slots; handles sbimf.com, INDMoney, Groww, and mfapi URL patterns for all 12 funds |
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

## Data sources per fund

Each of the 12 supported SBI funds has up to 4 raw files:

| Suffix | Source | Content |
|---|---|---|
| `*(official).txt` | sbimf.com (pre-authored) | Scheme type, exit load, expense ratio, benchmark, lock-in, fund overview |
| `*(indmoney).txt` | INDMoney (pre-authored) | NAV, performance table, sector allocation, AUM, FAQs |
| `*(groww).txt` | Groww (pre-authored) | Fund details, returns, top holdings, category-specific FAQs |
| `*(mfapi).txt` | api.mfapi.in — **live, fetched on every Sync** | Current NAV, calculated 1Y/3Y/5Y CAGR, NAV history, AMFI metadata |

Additional raw files: `amfi_investor_education.txt` (SIP, ELSS, expense ratio, NAV basics), `sebi_investor_rights.txt` (regulatory framework, investor rights, TER limits), `capital_gains_statements_(official).txt` (CAMS/CAS guide).

Files named `*official*` are ingested into both `mf_faq_corpus` and `fee_corpus`. All other files go into `mf_faq_corpus` only. Each file uses M1-format: first line `Source URL: <url>`, then `---`, then content.

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
