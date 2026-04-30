import hashlib
import json
from pathlib import Path

import chromadb

from config import CHROMA_PERSIST_DIR
from .url_loader import fetch_url
from .chunker import chunk_text, make_structured_chunk
from .embedder import get_embeddings
from .structured_extractor import extract as extract_fields, to_summary_text, fund_name_from_filename

ROOT = Path(__file__).resolve().parents[2]
_INDEX_HASH_FILE  = ROOT / "data" / ".index_hash"
_RAW_DIR          = ROOT / "data" / "raw"
_SNAPSHOT_FILE    = ROOT / "data" / "fund_snapshot.json"
_MANIFEST_PATH    = ROOT / "SOURCE_MANIFEST.md"


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


def _parse_raw_file(path: Path) -> tuple[str, str]:
    """Parse M1-format raw txt: first line is 'Source URL: <url>', rest is content."""
    lines = path.read_text(encoding="utf-8").splitlines()
    source_url = ""
    content_start = 0
    for i, line in enumerate(lines):
        if line.startswith("Source URL:"):
            source_url = line.split("Source URL:", 1)[1].strip()
        if line.startswith("---"):
            content_start = i + 1
            break
    text = " ".join(lines[content_start:])
    return source_url, text


def ingest_local_files(raw_dir: Path = _RAW_DIR) -> dict:
    """Ingest pre-scraped txt files from data/raw/ into ChromaDB.

    Files named *official* → both mf_faq_corpus and fee_corpus.
    Files named *indmoney* → mf_faq_corpus only.
    """
    if not raw_dir.exists():
        return {"mf_faq_added": 0, "fee_added": 0}

    col_faq = get_collection("mf_faq_corpus")
    col_fee = get_collection("fee_corpus")
    snapshot = _load_snapshot()
    mf_faq_added = fee_added = 0

    for txt_file in sorted(raw_dir.glob("*.txt")):
        source_url, text = _parse_raw_file(txt_file)
        if not text.strip():
            print(f"[ingest_local] SKIP {txt_file.name}: empty")
            continue
        if not source_url:
            source_url = f"file://{txt_file.name}"

        # ── Structured extraction ──────────────────────────────────────────
        fund_name = fund_name_from_filename(txt_file.stem)
        fields = extract_fields(source_url, text, fund_name=fund_name)
        summary = to_summary_text(fields)

        existing = snapshot["funds"].get(fund_name, {})
        merged = {**existing, **{k: v for k, v in fields.items() if v}}
        snapshot["funds"][fund_name] = merged

        if summary:
            print(f"[ingest_local]   structured fields extracted for {fund_name}")
        else:
            print(f"[ingest_local]   no structured fields found for {fund_name}")

        is_official = "official" in txt_file.name.lower()
        targets = ["mf_faq_corpus", "fee_corpus"] if is_official else ["mf_faq_corpus"]

        for corpus in targets:
            all_chunks: list[dict] = []
            if summary:
                sc = make_structured_chunk(summary, source_url, corpus)
                if sc:
                    all_chunks.append(sc)
            all_chunks.extend(chunk_text(text, source_url, corpus))
            if not all_chunks:
                continue
            _upsert_chunks(col_faq if corpus == "mf_faq_corpus" else col_fee, all_chunks)
            if corpus == "mf_faq_corpus":
                mf_faq_added += len(all_chunks)
            else:
                fee_added += len(all_chunks)
            print(f"[ingest_local] {txt_file.name} → {corpus}: {len(all_chunks)} chunks ({1 if summary else 0} structured)")

    _save_snapshot(snapshot)
    print(f"[ingest_local] fund snapshot saved → {_SNAPSHOT_FILE}  ({len(snapshot['funds'])} funds)")
    return {"mf_faq_added": mf_faq_added, "fee_added": fee_added}


def _load_snapshot() -> dict:
    if _SNAPSHOT_FILE.exists():
        try:
            return json.loads(_SNAPSHOT_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {"funds": {}}


def _save_snapshot(snapshot: dict) -> None:
    _SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SNAPSHOT_FILE.write_text(json.dumps(snapshot, indent=2))


def _upsert_chunks(col, chunks: list[dict]) -> None:
    if not chunks:
        return
    embeddings = get_embeddings([c["text"] for c in chunks])
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


def ingest_corpus(manifest_path: str | Path | None = None, force: bool = False) -> dict:
    if manifest_path is None:
        manifest_path = _MANIFEST_PATH
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
    snapshot = _load_snapshot()

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

        # ── Structured extraction ──────────────────────────────────────────
        fields = extract_fields(url, text)
        summary = to_summary_text(fields)

        # Persist to snapshot (merge: later URL for same fund keeps richer data)
        fund_name = fields["fund_name"]
        existing = snapshot["funds"].get(fund_name, {})
        merged = {**existing, **{k: v for k, v in fields.items() if v}}
        snapshot["funds"][fund_name] = merged

        if summary:
            print(f"[ingest]   structured fields extracted for {fund_name}")
        else:
            print(f"[ingest]   no structured fields found for {fund_name}")

        # ── Build chunks: structured summary first, then regular chunks ───
        col = col_faq if corpus == "mf_faq_corpus" else col_fee
        all_chunks: list[dict] = []

        if summary:
            sc = make_structured_chunk(summary, url, corpus)
            if sc:
                all_chunks.append(sc)

        all_chunks.extend(chunk_text(text, url, corpus))

        if not all_chunks:
            continue

        _upsert_chunks(col, all_chunks)

        count = len(all_chunks)
        if corpus == "mf_faq_corpus":
            mf_faq_total += count
        else:
            fee_total += count
        print(f"[ingest] upserted {count} chunks ({1 if summary else 0} structured + {count - (1 if summary else 0)} text)")

    _save_snapshot(snapshot)
    print(f"[ingest] fund snapshot saved → {_SNAPSHOT_FILE}  ({len(snapshot['funds'])} funds)")

    _INDEX_HASH_FILE.parent.mkdir(parents=True, exist_ok=True)
    _INDEX_HASH_FILE.write_text(new_hash)

    return {
        "mf_faq_count": col_faq.count(),
        "fee_count": col_fee.count(),
        "skipped": False,
    }
