# Phase 2 Architecture — Corpus Ingestion

## Pipeline Flow

```
SOURCE_MANIFEST.md
  (list of 15–25 URLs)
         │
         ▼
┌─────────────────────────────────┐
│  STEP 1: URL Loader             │
│  WebBaseLoader(url).load()      │
│  adds metadata: source_url,     │
│  corpus ("mf_faq"|"fee"),       │
│  loaded_at (ISO8601)            │
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
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  STEP 3: Embedder               │
│  primary:  OpenAI               │
│   text-embedding-3-small        │
│   dim = 1536                    │
│  fallback: SentenceTransformer  │
│   all-MiniLM-L6-v2              │
│   dim = 384                     │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────┐
│  STEP 4: Route & Upsert                         │
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
│  source_hash = sha256(urls)     │
│  save to data/.index_hash       │
│  on next run: compare → skip    │
│  re-embed if hash unchanged     │
└─────────────────────────────────┘
```

## Key Interfaces

```python
# pillar_a/ingest.py

def ingest_corpus(source_manifest_path: str, force: bool = False) -> dict:
    """
    Returns: {"mf_faq_count": int, "fee_count": int, "skipped": bool}
    """

def get_collection(name: str):  # "mf_faq_corpus" | "fee_corpus"
    """Returns chromadb.Collection"""

def query_collection(collection_name: str, query_text: str, n: int = 4) -> list[dict]:
    """
    Returns list of {text, source_url, corpus, distance}
    """
```

## Source URL Categories

| Category | Count | Collection |
|---|---|---|
| AMC Factsheets | 3–5 | mf_faq_corpus |
| KIM / SID Documents | 3–5 | mf_faq_corpus |
| SEBI Circulars / Scheme Pages | 2–3 | mf_faq_corpus |
| AMFI NAV / Scheme Pages | 3–5 | mf_faq_corpus |
| AMC Fee Schedule Pages | 2–3 | fee_corpus |
| SEBI/AMFI Fee Guidance | 2–3 | fee_corpus |
