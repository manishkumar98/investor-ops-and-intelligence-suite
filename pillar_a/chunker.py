import hashlib
from datetime import date
from langchain.text_splitter import RecursiveCharacterTextSplitter

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
