import hashlib
import os
from pathlib import Path

import chromadb

from config import CHROMA_PERSIST_DIR
from pillar_a.url_loader import fetch_url
from pillar_a.chunker import chunk_text
from pillar_a.embedder import get_embeddings

_INDEX_HASH_FILE = Path("data/.index_hash")


def get_collection(name: str):
    """Return a ChromaDB collection by name (creates it if absent)."""
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return client.get_or_create_collection(name)


def _parse_manifest(manifest_path: str) -> list[tuple[str, str]]:
    """Parse SOURCE_MANIFEST.md — lines like 'mf_faq: https://...' or 'fee: https://...'"""
    entries = []
    for line in Path(manifest_path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("mf_faq:"):
            url = line.split("mf_faq:", 1)[1].strip()
            entries.append((url, "mf_faq_corpus"))
        elif line.startswith("fee:"):
            url = line.split("fee:", 1)[1].strip()
            entries.append((url, "fee_corpus"))
    return entries


def ingest_corpus(manifest_path: str = "SOURCE_MANIFEST.md", force: bool = False) -> dict:
    entries = _parse_manifest(manifest_path)
    urls_sorted = sorted(e[0] for e in entries)
    new_hash = hashlib.sha256("|".join(urls_sorted).encode()).hexdigest()

    if not force and _INDEX_HASH_FILE.exists():
        if _INDEX_HASH_FILE.read_text().strip() == new_hash:
            print("Corpus already current. Use --force to re-ingest.")
            col_faq = get_collection("mf_faq_corpus")
            col_fee = get_collection("fee_corpus")
            return {
                "mf_faq_count": col_faq.count(),
                "fee_count": col_fee.count(),
                "skipped": True,
            }

    col_faq = get_collection("mf_faq_corpus")
    col_fee = get_collection("fee_corpus")

    mf_faq_total = 0
    fee_total = 0

    for url, corpus in entries:
        print(f"[ingest] fetching {url} → {corpus}")
        try:
            text = fetch_url(url)
        except Exception as exc:
            print(f"[ingest] SKIP {url}: {exc}")
            continue

        if not text.strip():
            print(f"[ingest] SKIP {url}: empty content")
            continue

        chunks = chunk_text(text, url, corpus)
        if not chunks:
            continue

        embeddings = get_embeddings([c["text"] for c in chunks])

        col = col_faq if corpus == "mf_faq_corpus" else col_fee
        col.upsert(
            ids=[c["chunk_id"] for c in chunks],
            embeddings=embeddings,
            documents=[c["text"] for c in chunks],
            metadatas=[{
                "source_url": c["source_url"],
                "corpus":     c["corpus"],
                "loaded_at":  c["loaded_at"],
            } for c in chunks],
        )

        if corpus == "mf_faq_corpus":
            mf_faq_total += len(chunks)
        else:
            fee_total += len(chunks)
        print(f"[ingest] upserted {len(chunks)} chunks")

    _INDEX_HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    _INDEX_HASH_FILE.write_text(new_hash)

    return {
        "mf_faq_count": col_faq.count(),
        "fee_count": col_fee.count(),
        "skipped": False,
    }
