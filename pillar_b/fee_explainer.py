import os
from datetime import date

import anthropic

from pillar_a.ingest import get_collection
from pillar_a.embedder import get_embeddings

_client = None

FEE_SCENARIO_MAP = {
    "Fee Transparency":  "expense_ratio",
    "SIP Failures":      "expense_ratio",
    "Exit Load":         "exit_load",
    "_default":          "exit_load",
}

ALLOWED_DOMAINS = ["sbimf.com", "amfiindia.com", "sebi.gov.in"]


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


_SYSTEM = (
    "You are a facts-only fee explainer for INDMoney / SBI Mutual Fund. "
    "Use ONLY the provided context. Respond with exactly 6 bullet points. "
    "Each bullet starts with '• '. No investment advice. No recommendations."
)

_PROMPT = """Explain the {scenario} fee scenario for SBI Mutual Fund schemes using the context below.

Context:
{context}

Format: exactly 6 bullet points starting with '• '
Add at the end: "Last checked: {today}"
Include 2 official source URLs from the context."""


def explain(top_theme: str, session: dict) -> dict:
    """Retrieve fee info from fee_corpus and generate 6-bullet explanation."""
    scenario = FEE_SCENARIO_MAP.get(top_theme, FEE_SCENARIO_MAP["_default"])
    query = f"SBI Mutual Fund {scenario.replace('_', ' ')} charges explained"

    # Try RAG retrieval
    chunks = []
    try:
        col = get_collection("fee_corpus")
        if col.count() > 0:
            embeddings = get_embeddings([query])
            results = col.query(query_embeddings=embeddings, n_results=4)
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                chunks.append({"text": doc, "source_url": meta.get("source_url", "")})
    except Exception as exc:
        print(f"[fee_explainer] RAG retrieval failed: {exc}")

    if chunks:
        context = "\n\n".join(c["text"] for c in chunks)
        source_urls = list(dict.fromkeys(
            c["source_url"] for c in chunks
            if any(d in c["source_url"] for d in ALLOWED_DOMAINS)
        ))[:2]
    else:
        # Hardcoded fallback when corpus is empty
        context = (
            "SBI ELSS Tax Advantage Fund has an exit load of 0% (3-year lock-in period). "
            "Expense ratio for SBI Bluechip Direct Plan is typically 0.5–0.8% per annum. "
            "Regular plans have a higher expense ratio than direct plans due to distributor commission. "
            "STT (Securities Transaction Tax) of 0.001% applies on equity fund redemptions. "
            "SEBI mandates TER (Total Expense Ratio) disclosure for all mutual fund schemes."
        )
        source_urls = [
            "https://www.sbimf.com/en-us/investor-service/exit-load",
            "https://www.amfiindia.com/investor-corner/knowledge-center/expense-ratio.html",
        ]

    msg = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _PROMPT.format(
            scenario=scenario.replace("_", " "),
            context=context,
            today=str(date.today()),
        )}],
    )
    raw = msg.content[0].text.strip()

    bullets = [line.strip() for line in raw.splitlines() if line.strip().startswith("•")]
    if len(bullets) < 6:
        bullets = [line.strip() for line in raw.splitlines() if line.strip()]

    # If source_urls not already extracted from LLM output, use retrieved ones
    if not source_urls:
        source_urls = [
            "https://www.sbimf.com/en-us/investor-service/expense-ratio",
            "https://www.amfiindia.com/investor-corner/knowledge-center/expense-ratio.html",
        ]

    return {
        "bullets":  bullets[:6],
        "sources":  source_urls[:2],
        "checked":  str(date.today()),
        "scenario": scenario,
    }
