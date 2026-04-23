from pillar_a.ingest import get_collection
from pillar_a.embedder import get_embeddings

MAX_DISTANCE = 0.75


def retrieve(query: str, query_type: str) -> list[dict]:
    """Embed query and retrieve chunks from appropriate collection(s).

    Returns list of {text, source_url, distance} dicts.
    Discards chunks with distance > MAX_DISTANCE.
    """
    embedding = get_embeddings([query])[0]
    chunks: list[dict] = []

    if query_type in ("factual_only", "compound"):
        chunks.extend(_query_collection("mf_faq_corpus", embedding, n=4))

    if query_type in ("fee_only", "compound"):
        chunks.extend(_query_collection("fee_corpus", embedding, n=2))

    # Deduplicate by chunk id (compound queries may retrieve same chunk twice)
    seen: set[str] = set()
    unique = []
    for c in chunks:
        if c["chunk_id"] not in seen:
            seen.add(c["chunk_id"])
            unique.append(c)

    # Distance filter
    filtered = [c for c in unique if c["distance"] <= MAX_DISTANCE]
    return filtered


def _query_collection(name: str, embedding: list[float], n: int) -> list[dict]:
    try:
        col = get_collection(name)
        if col.count() == 0:
            return []
        results = col.query(
            query_embeddings=[embedding],
            n_results=min(n, col.count()),
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text":       doc,
                "source_url": meta.get("source_url", ""),
                "chunk_id":   meta.get("chunk_id", doc[:16]),
                "distance":   dist,
            })
        return chunks
    except Exception as exc:
        print(f"[retriever] collection '{name}' error: {exc}")
        return []
