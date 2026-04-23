import os

_openai_client = None
_sentence_model = None
_openai_failed = False  # set True on first quota/auth failure; then skip for session


def _use_openai() -> bool:
    return bool(os.getenv("OPENAI_API_KEY")) and not _openai_failed


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Return embeddings for a list of texts.

    Uses OpenAI text-embedding-3-small (dim=1536) when OPENAI_API_KEY is set,
    falls back to all-MiniLM-L6-v2 (dim=384) otherwise.
    The model chosen at first ingest is fixed — mixing dimensions breaks ChromaDB.
    """
    if _use_openai():
        try:
            return _openai_embed(texts)
        except Exception as exc:
            global _openai_failed
            _openai_failed = True
            print(f"[embedder] OpenAI failed ({exc}) — switching to local embeddings for this session")
            return _local_embed(texts)
    return _local_embed(texts)


def _openai_embed(texts: list[str]) -> list[list[float]]:
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    all_embeddings: list[list[float]] = []
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = _openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=batch,
        )
        all_embeddings.extend([item.embedding for item in resp.data])
    return all_embeddings


def _local_embed(texts: list[str]) -> list[list[float]]:
    global _sentence_model
    if _sentence_model is None:
        from sentence_transformers import SentenceTransformer
        _sentence_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _sentence_model.encode(texts, convert_to_numpy=True).tolist()
