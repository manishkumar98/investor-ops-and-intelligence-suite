from phase2_corpus_pillar_a.ingest import get_collection
from phase2_corpus_pillar_a.embedder import get_embeddings

MAX_DISTANCE = 1.2  # local sentence-transformers cosine distance is in 0-2 scale

# Maps query-side keywords → slug/text patterns that identify the fund in stored chunks.
# When a user mentions a fund, we use this to filter out chunks from other funds.
_QUERY_TO_SLUGS: dict[str, list[str]] = {
    "elss":        ["elss", "long-term-equity", "long_term_equity", "tax-saver", "tax_saver"],
    "tax saver":   ["elss", "long-term-equity", "long_term_equity", "tax-saver", "tax_saver"],
    "bluechip":    ["bluechip", "blue-chip", "large-cap", "large_cap"],
    "large cap":   ["large-cap", "large_cap", "bluechip"],
    "small cap":   ["small-cap", "small_cap", "smallcap"],
    "flexicap":    ["flexicap", "flexi-cap", "flexi_cap"],
    "flexi cap":   ["flexicap", "flexi-cap", "flexi_cap"],
    "midcap":      ["midcap", "mid-cap", "mid_cap"],
    "mid cap":     ["midcap", "mid-cap", "mid_cap"],
}


def _active_slugs(query_lower: str) -> list[str]:
    """Return the URL/text slug patterns for every fund mentioned in the query."""
    slugs: list[str] = []
    for keyword, patterns in _QUERY_TO_SLUGS.items():
        if keyword in query_lower:
            for p in patterns:
                if p not in slugs:
                    slugs.append(p)
    return slugs


def _fund_score(chunk: dict, active_slugs: list[str]) -> int:
    """Score a chunk by how well it matches the fund(s) mentioned in the query.

    +3 if a fund slug appears in the chunk text (strong signal — structured data labels).
    +2 if it appears in the source URL (moderate signal).
    Returns 0 if no fund was queried (generic question) or no match found.
    """
    if not active_slugs:
        return 0
    url = chunk["source_url"].lower()
    text = chunk["text"][:400].lower()
    score = 0
    for slug in active_slugs:
        if slug in url:
            score += 2
        if slug in text:
            score += 3
    return score


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
        # n=4 so that after dedup of shared chunks the fee_corpus still contributes
        # unique chunks (e.g. the sbimf official structured chunk for the queried fund)
        chunks.extend(_query_collection("fee_corpus", embedding, n=4))

    # Deduplicate by chunk id (compound queries may retrieve same chunk twice)
    seen: set[str] = set()
    unique = []
    for c in chunks:
        if c["chunk_id"] not in seen:
            seen.add(c["chunk_id"])
            unique.append(c)

    # Distance filter
    filtered = [c for c in unique if c["distance"] <= MAX_DISTANCE]

    # Fund relevance reranking — when the query names a specific fund, drop chunks
    # from other funds so they don't pollute sources or the LLM context.
    slugs = _active_slugs(query.lower())
    if slugs:
        scored = [(c, _fund_score(c, slugs)) for c in filtered]
        fund_matched = [(c, s) for c, s in scored if s > 0]
        if fund_matched:
            # Sort by score DESC then distance ASC; discard zero-score (wrong-fund) chunks
            filtered = [c for c, _ in sorted(fund_matched, key=lambda x: (-x[1], x[0]["distance"]))]

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
        for chunk_id, doc, meta, dist in zip(
            results["ids"][0],          # always present regardless of include list
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text":       doc,
                "source_url": meta.get("source_url", ""),
                "chunk_id":   chunk_id,   # actual ChromaDB hash ID — safe for dedup
                "distance":   dist,
            })
        return chunks
    except Exception as exc:
        print(f"[retriever] collection '{name}' error: {exc}")
        return []
