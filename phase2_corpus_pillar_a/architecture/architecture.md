# Phase 2 Architecture — Corpus Ingestion

## What This Phase Does

Phase 2 builds the knowledge base that powers the FAQ engine. Before users can ask any question about SBI Mutual Funds, the system needs to have read, understood, and indexed all the relevant official documents. That preparation work happens here.

Think of it like a research assistant spending a day reading every official document from SBI Mutual Fund, AMFI, and SEBI — but now also filling out a structured form for each fund: exit load, expense ratio, minimum SIP, AUM, fund manager, benchmark, risk level, and so on. Both the filled form and the highlighted passages go into the filing cabinet. Finding the answer to any question takes seconds.

**What actually happens technically:** The system fetches all URLs listed in `SOURCE_MANIFEST.md`, strips HTML clutter to get plain text, runs a **structured extractor** to pull out named fields (exit load, expense ratio, min SIP, etc.), creates one synthetic "structured summary chunk" per URL that is always retrieved for direct field queries, splits remaining text into overlapping passage chunks, embeds everything with sentence-transformers or OpenAI, and upserts into ChromaDB. Extracted fields are also persisted to `data/fund_snapshot.json` — a structured JSON store that survives restarts and can be read without touching ChromaDB.

This phase runs **once** during setup, not on every user request. A hash guard ensures re-running does nothing if the source URLs haven't changed.

---

## Pipeline Flow

```
SOURCE_MANIFEST.md
  (list of URLs, each tagged mf_faq: or fee:)
         │
         ▼
┌─────────────────────────────────┐
│  STEP 1: URL Loader             │
│  url_loader.fetch_url(url)      │
│  requests.get → BeautifulSoup   │
│  strips <script><style>         │
│  <nav><footer><head>            │
│  returns clean plain text       │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 2: Structured Extractor  ← NEW                    │
│  structured_extractor.extract(url, text)                │
│                                                         │
│  Runs 14 field regex patterns on full page text:        │
│  exit_load, expense_ratio, min_sip, min_lumpsum,        │
│  aum, nav, benchmark, fund_manager, risk, category,     │
│  lock_in, inception_date, returns_1y, returns_3y        │
│                                                         │
│  Normalises fund name from URL slug                     │
│  Returns: dict of named field slots                     │
│                                                         │
│  ┌─────────────────────────────────────────────┐        │
│  │  to_summary_text(fields)                    │        │
│  │  Formats fields into labelled text block:   │        │
│  │  "[STRUCTURED FUND DATA — SBI ELSS …]       │        │
│  │   Exit Load: Nil                            │        │
│  │   Expense Ratio (Direct Plan): 0.87%        │        │
│  │   Minimum SIP Amount: 500                   │        │
│  │   Lock-in Period: 3 years  …"               │        │
│  └──────────────┬──────────────────────────────┘        │
│                 │                                        │
│                 ▼                                        │
│  Merged into data/fund_snapshot.json  ← persistent      │
│  (one entry per fund, survives restarts)                 │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 3: Chunk Builder                                   │
│                                                         │
│  A) make_structured_chunk(summary, url, corpus)         │
│     → single synthetic chunk, deterministic ID          │
│     → always retrieved for direct field queries         │
│     → prepended before all other chunks                 │
│                                                         │
│  B) chunk_text(text, url, corpus)                       │
│     RecursiveCharacterTextSplitter                      │
│     chunk_size=512 tokens, overlap=64 tokens            │
│     each chunk: {text, source_url, corpus,              │
│                  chunk_id=sha256(url+idx)[:8],          │
│                  loaded_at}                             │
│                                                         │
│  Final list = [structured_chunk] + text_chunks          │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  STEP 4: Embedder               │
│  if OPENAI_API_KEY set:         │
│    text-embedding-3-small       │
│    dim = 1536                   │
│  else:                          │
│    all-MiniLM-L6-v2 (fallback)  │
│    dim = 384                    │
│  Batches of 100 texts per call  │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│  STEP 5: Route & Upsert into ChromaDB           │
│                                                 │
│  corpus=="mf_faq"     corpus=="fee"             │
│       │                     │                   │
│       ▼                     ▼                   │
│  mf_faq_corpus         fee_corpus               │
│  .upsert(ids,          .upsert(ids,             │
│   embeddings,           embeddings,             │
│   documents,            documents,              │
│   metadatas)            metadatas)              │
└─────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  STEP 6: Hash Guard             │
│  source_hash = sha256(          │
│    sorted(all_urls).encode())   │
│  save to data/.index_hash       │
│  on next run: compare → skip    │
│  if hash matches (no change)    │
│  use --force to override        │
└─────────────────────────────────┘
```

---

## Structured Extractor Detail

### `structured_extractor.py`

The structured extractor is the key quality improvement over plain text chunking. Instead of relying on cosine similarity to find "exit load: 1%" buried somewhere in a 512-token chunk, we extract it explicitly and store it in a labelled block that is always retrievable.

**Fund name normalisation:**
The extractor maintains a `_SLUG_MAP` dict mapping URL path fragments (`sbi-bluechip-fund`, `sbi-elss-tax-saver-fund`, etc.) to canonical fund names. This ensures all sources for the same fund are merged under one key in `fund_snapshot.json`.

**Field patterns (14 fields):**

| Field | Example extracted value |
|---|---|
| `exit_load` | `1% if redeemed within 1 year from date of allotment` |
| `expense_ratio` | `0.87%` |
| `min_sip` | `500` |
| `min_lumpsum` | `5000` |
| `aum` | `25847 cr` |
| `nav` | `84.32` |
| `benchmark` | `BSE 100 TRI` |
| `fund_manager` | `Mohit Jain` |
| `risk` | `Moderately High` |
| `category` | `Large Cap Equity` |
| `lock_in` | `3 years` |
| `inception_date` | `Jan 14 2013` |
| `returns_1y` | `12.4%` |
| `returns_3y` | `18.2%` |

Each field has 2–4 regex patterns tried in order. The first match wins. All patterns are case-insensitive. Empty string means not found on this page.

**Synthetic structured chunk:**
When at least one field is found, `to_summary_text()` creates a single text block:
```
[STRUCTURED FUND DATA — SBI ELSS Tax Saver Fund — as of 2026-04-24]
Exit Load: Nil
Expense Ratio (Direct Plan): 0.87%
Minimum SIP Amount: 500
Lock-in Period: 3 years
Benchmark Index: BSE 500 TRI
Fund Manager: Dinesh Balachandran
Risk Level: Very High
Fund Category: ELSS
Source: https://www.sbimf.com/...
```

This block is embedded as a single chunk with a **deterministic ID** (`sha256("structured_" + url)[:8]`). Re-ingesting the same URL replaces the chunk rather than duplicating it.

---

## fund_snapshot.json — Persistent Structured Store

`data/fund_snapshot.json` is written after every ingest run and persists between app restarts. It gives any part of the application direct access to structured fund data without a ChromaDB query.

**Structure:**
```json
{
  "funds": {
    "SBI Large Cap Fund (Bluechip)": {
      "fund_name":      "SBI Large Cap Fund (Bluechip)",
      "source_url":     "https://www.sbimf.com/...",
      "last_scraped":   "2026-04-24",
      "exit_load":      "1% if redeemed within 1 year",
      "expense_ratio":  "0.87%",
      "min_sip":        "500",
      "min_lumpsum":    "5000",
      "aum":            "25847 cr",
      "nav":            "84.32",
      "benchmark":      "BSE 100 TRI",
      "fund_manager":   "Mohit Jain",
      "risk":           "Moderately High",
      "category":       "Large Cap Equity",
      "lock_in":        "",
      "inception_date": "Feb 14 2006",
      "returns_1y":     "",
      "returns_3y":     ""
    },
    "SBI ELSS Tax Saver Fund": { ... },
    ...
  }
}
```

**Merge behaviour:** If multiple URLs cover the same fund (e.g. sbimf.com + indmoney.com both have SBI ELSS data), the extractor merges them — a field from a later URL fills in only if the earlier URL left it empty. The richest combined view is stored.

**When to re-ingest:** The snapshot is only as fresh as the last `ingest_corpus.py --force` run. The `last_scraped` field on each fund entry shows when it was last updated.

**Who reads it:**
- `scripts/health_monitor.py` — checks corpus freshness from `system_state.json` (ingest writes timestamp there too)
- Any future module that needs instant field lookup without RAG (e.g. a sidebar widget showing fund data)

---

## Local Raw File Ingestion

In addition to fetching live URLs, the ingest pipeline processes pre-scraped Playwright files from `data/raw/*.txt`. These files have richer content than live fetches because they capture fully JavaScript-rendered pages.

**File naming convention:**
- `*official*` → ingested into both `mf_faq_corpus` and `fee_corpus`
- `*indmoney*` → ingested into `mf_faq_corpus` only

**File format (M1 format):**
```
Source URL: https://www.indmoney.com/mutual-funds/sbi-bluechip-fund-direct-growth-3046
---
[collapsed page text — newlines joined with single space]
```

**Current files in `data/raw/`:**
- `sbi_large_cap_fund_(official).txt`, `sbi_flexicap_fund_(official).txt`, `sbi_elss_tax_saver_fund_(official).txt`, `sbi_midcap_fund_(official).txt`, `sbi_small_cap_fund_(official).txt`
- `sbi_flexicap_fund_(indmoney).txt`, `sbi_midcap_fund_(indmoney).txt`, `sbi_small_cap_fund_(indmoney).txt`, `sbi_bluechip_fund_(indmoney).txt`, `sbi_long_term_equity_fund_(indmoney).txt`
- `capital_gains_statements_(official).txt` — guide for downloading capital gains statements from CAMS / MF Central, fund-specific links for all 8 SBI funds

**`ingest_local_files()` flow:**
1. Reads each `.txt` file from `data/raw/`
2. Calls `fund_name_from_filename(stem)` to resolve canonical fund name from file stem
3. Calls `extract(source_url, text, fund_name=...)` with the resolved name
4. Merges into `data/fund_snapshot.json` snapshot
5. Creates structured chunk + text chunks, upserts to ChromaDB

**`fund_name_from_filename(filename)`** uses `_FILE_SLUG_MAP` (underscore → canonical name) analogous to `_SLUG_MAP` for URLs.

---

## Key Interfaces

```python
# phase2_corpus_pillar_a/ingest.py

def ingest_corpus(manifest_path: str = "SOURCE_MANIFEST.md", force: bool = False) -> dict:
    """
    Full ingest pipeline: fetch → structured extract → chunk → embed → upsert.
    Writes data/fund_snapshot.json and data/.index_hash.
    Returns: {"mf_faq_count": int, "fee_count": int, "skipped": bool}
    """

def ingest_local_files(raw_dir: Path = Path("data/raw")) -> dict:
    """
    Ingests pre-scraped Playwright txt files from data/raw/.
    Calls structured extractor + merges into fund_snapshot.json.
    Returns: {"mf_faq_added": int, "fee_added": int}
    Called automatically by scripts/ingest_corpus.py after ingest_corpus().
    """

def get_collection(name: str) -> chromadb.Collection:
    """
    name: "mf_faq_corpus" | "fee_corpus"
    Imported by Phase 3 (fee_explainer) and Phase 5 (retriever).
    """

# phase2_corpus_pillar_a/structured_extractor.py

def extract(url: str, page_text: str, fund_name: str = "") -> dict:
    """
    Returns dict with fund_name, source_url, last_scraped, and 14 named fields.
    fund_name: optional override (used by ingest_local_files to pass resolved name).
    Empty string means field not found on this page.
    """

def fund_name_from_filename(filename: str) -> str:
    """
    Resolves canonical fund name from a raw file stem like 'sbi_elss_tax_saver_fund_(official)'.
    Uses _FILE_SLUG_MAP (underscore-separated slugs → canonical names).
    """

def to_summary_text(fields: dict) -> str:
    """
    Formats extracted fields into the structured chunk text block.
    Returns "" if no fields were found (no structured chunk created).
    """

# phase2_corpus_pillar_a/chunker.py

def chunk_text(text: str, url: str, corpus: str) -> list[dict]:
    """Splits raw text into overlapping chunks with metadata."""

def make_structured_chunk(summary_text: str, url: str, corpus: str) -> dict | None:
    """
    Creates a single synthetic structured chunk from to_summary_text() output.
    Returns None if summary_text is empty.
    Chunk ID is deterministic: sha256("structured_" + url)[:8]
    """
```

---

## Source URL Categories

The `SOURCE_MANIFEST.md` file lists all URLs to ingest. Each line is prefixed with either `mf_faq:` (goes into `mf_faq_corpus`) or `fee:` (goes into `fee_corpus`).

| Category | Collection | What's extracted |
|---|---|---|
| SBI MF scheme pages (sbimf.com) | `mf_faq_corpus` + `fee_corpus` | Exit load, expense ratio, min SIP, AUM, fund manager, benchmark, NAV |
| INDMoney fund detail pages | `mf_faq_corpus` | Category, risk level, returns, NAV, SIP minimums |
| SBI SIP calculator page | `mf_faq_corpus` | SIP mechanics, compounding explanation |

**Minimum thresholds after ingest:** `mf_faq_corpus` ≥ 30 chunks, `fee_corpus` ≥ 8 chunks.

---

## Prerequisites

- Phase 1 complete: `config.py` and `session_init.py` working
- `SOURCE_MANIFEST.md` populated with URLs
- `ANTHROPIC_API_KEY` set (used by FAQ engine in Phase 5; not needed for ingest itself)
- Network access to `sbimf.com`, `indmoney.com`

---

## Credentials Required

| Env Var | Required? | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Optional | `text-embedding-3-small` (dim=1536). If absent, falls back to local `all-MiniLM-L6-v2` (dim=384) |
| `CHROMA_PERSIST_DIR` | Yes | Where ChromaDB writes to disk |

---

## Tools & Libraries

| Package | Purpose |
|---|---|
| `requests` | `fetch_url()` — fetches each URL with retry |
| `beautifulsoup4` | Strips HTML tags, extracts plain text |
| `re` (stdlib) | Structured extractor field patterns |
| `langchain-text-splitters` | `RecursiveCharacterTextSplitter` for text chunking |
| `sentence-transformers` | Local embedding fallback (`all-MiniLM-L6-v2`) |
| `openai` | Optional: `text-embedding-3-small` embeddings |
| `chromadb` | Vector store — persistent on disk |
| `hashlib` (stdlib) | Hash guard + chunk ID generation |

### Critical: The Embedding Model Lock

**Decide before the first ingest. Cannot change afterward without deleting `data/chroma/`.**

- `OPENAI_API_KEY` set → `text-embedding-3-small` (dim=1536)
- No key → `all-MiniLM-L6-v2` (dim=384)

ChromaDB locks the vector dimension on first write. Querying with a different-dimension embedding raises an error. Fix: `rm -rf data/chroma/ data/.index_hash` then re-ingest with `--force`.

---

## Step-by-Step Build Order

**1. `url_loader.py`** — `fetch_url(url) -> str`
- `requests.get` with retry, BeautifulSoup strip, return plain text

**2. `structured_extractor.py`** — `extract(url, text) -> dict`, `to_summary_text(fields) -> str`
- Regex field extraction on full page text
- Fund name normalisation from URL slug via `_SLUG_MAP`
- Summary text formatter for synthetic chunk

**3. `chunker.py`** — `chunk_text(text, url, corpus) -> list[dict]`, `make_structured_chunk(summary, url, corpus) -> dict|None`
- RecursiveCharacterTextSplitter for text chunks
- Deterministic structured chunk builder

**4. `embedder.py`** — `get_embeddings(texts) -> list[list[float]]`
- OpenAI or sentence-transformers, batched

**5. `ingest.py`** — `ingest_corpus(manifest_path, force) -> dict`
- Orchestrates all steps above
- Loads/saves `data/fund_snapshot.json`
- Writes `data/.index_hash`

**6. `scripts/ingest_corpus.py`** — CLI entry point
```bash
python scripts/ingest_corpus.py           # skip if already ingested
python scripts/ingest_corpus.py --force   # force re-ingest
```

---

## Outputs & Downstream Dependencies

| Output | Consumed By | What breaks if missing |
|---|---|---|
| `mf_faq_corpus` ChromaDB collection | Phase 5 `retriever.py` | FAQ returns "not in knowledge base" for all questions |
| `fee_corpus` ChromaDB collection | Phase 3 `fee_explainer.py`, Phase 5 `retriever.py` | Fee explanation fails; compound FAQ fails |
| `data/fund_snapshot.json` | `health_monitor.py`, any direct-lookup module | No structured field store; RAG-only mode |
| `get_collection(name)` function | Phase 3, Phase 5 | Import error at runtime |
| `data/.index_hash` | Phase 2 re-run guard | Corpus re-ingested on every run |

---

## Error Cases

**URL fetch fails (403 / 404 / timeout):** Skip URL, log warning. Ingest continues with remaining URLs.

**Structured extractor finds no fields:** `to_summary_text()` returns `""`, no structured chunk is created. Regular text chunks are still ingested. This is not an error — just means the page layout didn't match any patterns.

**Same fund covered by multiple URLs:** Fields are merged — empty fields from the first URL are filled in by the second URL. Richer combined data is stored in `fund_snapshot.json`.

**OpenAI rate limit (HTTP 429):** Retry with exponential backoff (1s, 2s, 4s). After 3 failures, skip that batch and log error.

**ChromaDB dimension mismatch:** Fatal. Means a prior ingest used a different embedding model. Fix: `rm -rf data/chroma/ data/.index_hash` then re-ingest.

**Hash unchanged, `--force` not passed:**
```
Corpus already current. Use --force to re-ingest.
```
Not an error — exit 0.

---

## Phase Gate

All of the following must pass before starting Phase 3:

```bash
# Build corpus (first time, or after adding new URLs to SOURCE_MANIFEST.md)
python scripts/ingest_corpus.py --force

# Verify chunks were created and structured extraction ran
# Look for lines like:
#   [ingest] structured fields extracted for SBI Large Cap Fund (Bluechip)
#   [ingest] fund snapshot saved → data/fund_snapshot.json  (8 funds)

# Check fund_snapshot.json is populated
python3 -c "
import json
s = json.load(open('data/fund_snapshot.json'))
for name, f in s['funds'].items():
    filled = sum(1 for v in f.values() if v and v not in (name, f.get('source_url',''), f.get('last_scraped','')))
    print(f'{name}: {filled} fields extracted')
"

# Run unit tests
pytest phase2_corpus_pillar_a/tests/ -v

# Run health check
python scripts/health_monitor.py
```
