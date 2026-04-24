import hashlib
from datetime import date
from langchain_text_splitters import RecursiveCharacterTextSplitter


def make_structured_chunk(summary_text: str, url: str, corpus: str) -> dict | None:
    """Create a single high-priority chunk from structured field summary text.

    Returns None if summary_text is empty (no fields were extracted).
    The chunk ID is deterministic so re-ingesting the same URL replaces it.
    """
    if not summary_text.strip():
        return None
    chunk_id = hashlib.sha256(f"structured_{url}".encode()).hexdigest()[:8]
    return {
        "text":       summary_text,
        "source_url": url,
        "corpus":     corpus,
        "chunk_id":   chunk_id,
        "loaded_at":  str(date.today()),
        "chunk_type": "structured_summary",
    }

CHUNK_SIZE    = 512   # tokens (approximate via chars * 0.75)
CHUNK_OVERLAP = 64


def chunk_text(text: str, url: str, corpus: str) -> list[dict]:
    """Split text into overlapping chunks with metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE * 4,   # ~4 chars/token
        chunk_overlap=CHUNK_OVERLAP * 4,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    pieces = splitter.split_text(text)
    chunks = []
    loaded_at = str(date.today())
    for idx, piece in enumerate(pieces):
        chunk_id = hashlib.sha256(f"{url}_{idx}".encode()).hexdigest()[:8]
        chunks.append({
            "text":       piece,
            "source_url": url,
            "corpus":     corpus,
            "chunk_id":   chunk_id,
            "loaded_at":  loaded_at,
        })
    return chunks
