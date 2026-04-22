# Phase 2 Architecture — Corpus Ingestion

## What This Phase Does

Phase 2 builds the knowledge base that powers the FAQ engine. Before users can ask any question about SBI Mutual Funds, the system needs to have read, understood, and indexed all the relevant official documents. That preparation work happens here.

Think of it like a research assistant spending a day reading every official document from SBI Mutual Fund, AMFI, and SEBI — highlighting important passages, organising them by topic, and filing them in a cabinet. After this one-time preparation, finding the answer to any question takes seconds instead of hours.

**What actually happens technically:** The system fetches 30+ official web pages, strips out all the navigation menus and HTML clutter to get plain text, splits that text into small searchable passages (chunks), converts each passage into a numerical fingerprint (embedding), and stores everything in ChromaDB — a local vector database on disk. From then on, when a user asks a question, the question gets the same fingerprint treatment and the database finds the most similar passages in milliseconds.

This phase runs **once** during setup, not on every user request. The result (the populated ChromaDB) is what Phases 3 and 5 depend on. A hash guard ensures that re-running this phase does nothing if the source documents haven't changed — it won't waste money on re-embedding unless you explicitly force it.

---

## Pipeline Flow

```
SOURCE_MANIFEST.md
  (list of 30+ URLs, each tagged mf_faq: or fee:)
         │
         ▼
┌─────────────────────────────────┐
│  STEP 1: URL Loader             │
│  requests.get(url)              │
│  BeautifulSoup strips HTML      │
│  removes <script> and <style>   │
│  returns clean plain text       │
│  adds metadata: source_url,     │
│  corpus ("mf_faq"|"fee"),       │
│  loaded_at (ISO8601 timestamp)  │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  STEP 2: Chunker                │
│  RecursiveCharacterTextSplitter │
│  chunk_size  = 512 tokens       │
│  chunk_overlap = 64 tokens      │
│  each chunk gets chunk_id       │
│  = sha256(url+idx)[:8]          │
│  Each chunk is a dict:          │
│  {text, source_url, corpus,     │
│   chunk_id, loaded_at}          │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  STEP 3: Embedder               │
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
│  STEP 4: Route & Upsert into ChromaDB           │
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
│  STEP 5: Hash Guard             │
│  source_hash = sha256(          │
│    sorted(all_urls).encode())   │
│  save to data/.index_hash       │
│  on next run: compare → skip    │
│  if hash matches (no change)    │
│  use --force to override        │
└─────────────────────────────────┘
```

---

## Key Interfaces

```python
# pillar_a/ingest.py

def ingest_corpus(source_manifest_path: str, force: bool = False) -> dict:
    """
    Reads SOURCE_MANIFEST.md, fetches URLs, chunks, embeds, upserts.
    Returns: {"mf_faq_count": int, "fee_count": int, "skipped": bool}
    skipped=True means hash matched and ingest was skipped (no change).
    """

def get_collection(name: str):
    """
    name: "mf_faq_corpus" | "fee_corpus"
    Returns: chromadb.Collection
    Imported by Phase 3 (fee_explainer) and Phase 5 (retriever).
    """

def query_collection(collection_name: str, query_text: str, n: int = 4) -> list[dict]:
    """
    Returns list of {text, source_url, corpus, distance}
    Used by check_corpus.py to verify ingest quality.
    """
```

---

## Source URL Categories

The `SOURCE_MANIFEST.md` file lists all URLs to ingest. Each line is prefixed with either `mf_faq:` (goes into `mf_faq_corpus`) or `fee:` (goes into `fee_corpus`).

| Category | Target Count | Collection | What's in there |
|---|---|---|---|
| SBI ELSS Tax Advantage Fund factsheet + KIM/SID | 2–3 | `mf_faq_corpus` | Lock-in period, exit load, SIP minimums, riskometer |
| SBI Bluechip Fund factsheet + KIM/SID | 2–3 | `mf_faq_corpus` | Fund objective, benchmark, expense ratio, NAV |
| SBI Small Cap Fund factsheet + KIM/SID | 2–3 | `mf_faq_corpus` | Scheme details, category, AUM, fund manager |
| AMFI Scheme Detail Pages | 3–5 | `mf_faq_corpus` | Official scheme data from amfiindia.com |
| SEBI Circulars (MF-related) | 2–3 | `mf_faq_corpus` | Regulatory requirements, scheme categorisation |
| SBI MF Fee Schedule Pages | 2–3 | `fee_corpus` | Exit load tables, expense ratio tiers by plan |
| AMFI Fee Guidelines | 2–3 | `fee_corpus` | Total Expense Ratio caps, direct vs regular |
| SEBI Expense Ratio Circular | 1–2 | `fee_corpus` | Regulatory limits on expense ratios |

**Minimum thresholds:** After ingest, `mf_faq_corpus` must have ≥30 chunks and `fee_corpus` must have ≥8 chunks. The `eval_corpus.py` script checks this.

---

## Prerequisites

- Phase 1 complete: `config.py` and `session_init.py` working, ChromaDB client initialises without error
- `SOURCE_MANIFEST.md` created and populated with 30+ URLs (see categories above)
- `OPENAI_API_KEY` valid and has available quota — embedding 30+ pages will cost a small amount
- Network access to `sbimf.com`, `amfiindia.com`, `sebi.gov.in`

---

## Credentials Required

| Env Var | Required? | Purpose |
|---|---|---|
| `OPENAI_API_KEY` | Yes | `openai.embeddings.create(model="text-embedding-3-small")` — generates 1536-dim vectors for every chunk |
| `CHROMA_PERSIST_DIR` | Yes | `PersistentClient(path=CHROMA_PERSIST_DIR)` — where ChromaDB writes files to disk |

**No `ANTHROPIC_API_KEY` needed for this phase.** Embedding is purely OpenAI. The LLM is not involved.

---

## Tools & Libraries

| Package | Version | Purpose | Notes |
|---|---|---|---|
| `requests` | >=2.31 | `requests.get(url, timeout=10)` — fetches each URL | Included via langchain; add explicit retry on 5xx |
| `beautifulsoup4` | >=4.12 | `BeautifulSoup(html, "html.parser")` — strips tags, removes `<script>`/`<style>` | May need `pip install beautifulsoup4` |
| `langchain` | >=0.3.0 | `RecursiveCharacterTextSplitter` — chunks text at 512 tokens with 64 overlap | Already in `requirements.txt` |
| `openai` | >=1.50.0 | `openai.embeddings.create(model="text-embedding-3-small", input=[...])` | Already in `requirements.txt` |
| `sentence-transformers` | >=3.0 | `SentenceTransformer("all-MiniLM-L6-v2").encode()` — fallback embedder (dim=384) | `pip install sentence-transformers` if no OpenAI key |
| `chromadb` | >=0.5.0 | `collection.upsert(ids, embeddings, documents, metadatas)` | Already in `requirements.txt` |
| `tiktoken` | >=0.8.0 | Token counting to enforce `chunk_size=512` accurately | Already in `requirements.txt` |
| `hashlib` | stdlib | `hashlib.sha256(sorted_urls_str.encode()).hexdigest()` — hash guard | No install |

### Critical: The Embedding Model Lock

**You must decide which embedding model to use before the first ingest, and you cannot change it afterward.**

- If `OPENAI_API_KEY` is set → use `text-embedding-3-small` (dim=1536)
- If `OPENAI_API_KEY` is not set → use `all-MiniLM-L6-v2` (dim=384)

ChromaDB stores the vector dimensions when you first write to a collection. If you later query with a different-dimension embedding, ChromaDB raises an error. The fix is to delete `data/chroma/` and re-ingest everything from scratch. This is why the decision must be made consciously once, not changed accidentally.

---

## Inputs

- `SOURCE_MANIFEST.md` — list of 30+ URLs, one per line, prefixed with `mf_faq:` or `fee:`
- `CHROMA_PERSIST_DIR` — disk directory for ChromaDB storage
- Network: HTML pages from `sbimf.com`, `amfiindia.com`, `sebi.gov.in`

---

## Step-by-Step Build Order

**1. `pillar_a/url_loader.py`**
Function: `fetch_url(url: str) -> str`
- `requests.get(url, timeout=10)` with max 2 retries on `ConnectionError` or `Timeout`
- `BeautifulSoup(response.text, "html.parser")`
- Remove all `<script>` and `<style>` tags: `[tag.decompose() for tag in soup(["script","style"])]`
- Extract body text: `soup.get_text(separator=" ", strip=True)`
- Return clean string. On failure (404, 403, empty body): return `""` and log warning

**2. `pillar_a/chunker.py`**
Function: `chunk_text(text: str, url: str, corpus: str, size=512, overlap=64) -> list[dict]`
- Wrap `RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap)`
- For each chunk at index `i`, create dict:
  ```python
  {
    "text":       chunk,
    "source_url": url,
    "corpus":     corpus,
    "chunk_id":   hashlib.sha256(f"{url}{i}".encode()).hexdigest()[:8],
    "loaded_at":  datetime.utcnow().isoformat()
  }
  ```
- Return list of these dicts

**3. `pillar_a/embedder.py`**
Function: `get_embeddings(texts: list[str]) -> list[list[float]]`
- Check `os.getenv("OPENAI_API_KEY")` — if set, use OpenAI; else use SentenceTransformer
- OpenAI path: batch in groups of 100; call `openai.embeddings.create(model="text-embedding-3-small", input=batch)`; retry on rate limit (429) with exponential backoff: 1s, 2s, 4s
- Fallback path: `SentenceTransformer("all-MiniLM-L6-v2").encode(texts, batch_size=64)`; return as `list[list[float]]`

**4. `pillar_a/ingest.py`**
Function: `ingest_corpus(manifest_path, force=False) -> dict`
- Parse `SOURCE_MANIFEST.md`: collect `(url, corpus_tag)` tuples
- Hash guard: compute `sha256(sorted_urls)`, compare to `data/.index_hash`; if equal and not `force`, print "Corpus already current" and return `{"skipped": True}`
- For each URL: fetch → chunk → embed → upsert into correct collection
- Write new hash to `data/.index_hash`
- Return `{"mf_faq_count": N, "fee_count": N, "skipped": False}`

Function: `get_collection(name: str) -> chromadb.Collection`
- `PersistentClient(path=CHROMA_PERSIST_DIR).get_or_create_collection(name)`
- Returns the live collection handle; called by Phase 3 and Phase 5

**5. `scripts/ingest_corpus.py`**
CLI entry point:
```bash
python scripts/ingest_corpus.py           # skip if already ingested
python scripts/ingest_corpus.py --force   # force re-ingest regardless
```
Calls `ingest_corpus()`, prints summary table, exits with code 0 on success.

**6. `scripts/check_corpus.py`**
Queries each collection with the 5 golden questions from `evals/golden_dataset.json`. For each query, prints the top result's cosine distance. Warns if any distance is > 0.6 (meaning the corpus may not have relevant content for that question).

---

## Outputs & Downstream Dependencies

| Output | Consumed By | What breaks if missing |
|---|---|---|
| `mf_faq_corpus` ChromaDB collection | Phase 5 `retriever.py` | FAQ engine returns "not in knowledge base" for all questions |
| `fee_corpus` ChromaDB collection | Phase 3 `fee_explainer.py`, Phase 5 `retriever.py` | Fee explanation returns placeholder; compound FAQ fails |
| `get_collection(name)` function | Phase 3, Phase 5 import this to get live collection handle | Import error at runtime |
| `data/.index_hash` | Phase 2 re-run guard | Corpus re-ingested on every run (wastes API quota) |

---

## Error Cases

**URL fetch fails (403 / 404 / timeout):**
Log `WARNING: Failed to fetch {url} — {status}. Skipping.` and continue with remaining URLs. Only fail the whole ingest if the total chunk count falls below the minimum thresholds after all URLs are tried.

**BeautifulSoup returns empty or near-empty text:**
Skip the URL, log `WARNING: {url} returned empty text after stripping HTML.`. This happens with JavaScript-heavy pages that render content client-side.

**OpenAI rate limit (HTTP 429):**
Retry with exponential backoff: wait 1s, then 2s, then 4s. After 3 failures on the same batch, log the error and skip that batch.

**ChromaDB dimension mismatch:**
This is a fatal error. It means a previous ingest used a different embedding model. The error message from ChromaDB will mention "dimensionality". Fix: `rm -rf data/chroma/ data/.index_hash` then re-ingest with `--force`.

**Hash unchanged but `--force` not passed:**
```
Corpus already current (hash matches SOURCE_MANIFEST.md).
To force re-ingest: python scripts/ingest_corpus.py --force
```
Exit 0 — this is not an error.

**No URLs in the `fee:` category:**
`fee_corpus` would have 0 chunks. Fee explainer and compound queries would fail. This is caught by `eval_corpus.py` which asserts `fee_count >= 8`.

---

## Phase Gate

All of the following must pass before starting Phase 3:

```bash
# Build the corpus (first time)
python scripts/ingest_corpus.py
# Expected output: mf_faq: N chunks, fee: N chunks ingested

# Verify cosine distances are reasonable
python scripts/check_corpus.py
# Expected: all 5 golden Q distances < 0.6

# Run unit tests
pytest phase2_corpus/tests/test_corpus.py -v
# Expected: all tests pass

# Run eval
python phase2_corpus/evals/eval_corpus.py
# Expected: mf_faq_corpus >= 30 chunks, fee_corpus >= 8 chunks
```
