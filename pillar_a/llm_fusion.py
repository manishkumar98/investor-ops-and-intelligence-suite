import os
from dataclasses import dataclass, field
from datetime import date

import anthropic

_client = None
NOT_IN_KB = "This information is not available in our knowledge base. Please check https://www.amfiindia.com"

ALLOWED_DOMAINS = ["sbimf.com", "amfiindia.com", "sebi.gov.in"]


@dataclass
class FaqResponse:
    refused:     bool            = False
    refusal_msg: str | None      = None
    bullets:     list[str]       = field(default_factory=list)
    prose:       str | None      = None
    sources:     list[str]       = field(default_factory=list)
    last_updated: str            = ""


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


_SYSTEM = """You are a Facts-Only Mutual Fund Assistant for INDMoney users.
Answer using ONLY the retrieved context provided below.

Rules:
- For compound questions (query_type=compound): respond in exactly 6 numbered bullet points.
- For simple factual or fee questions: respond in ≤3 clear sentences.
- Never infer returns. Never recommend specific funds.
- If context is insufficient, respond: "This information is not available in our knowledge base. Please check https://www.amfiindia.com"
- End every answer with "Source: <url>" and "Last updated from sources: <date>"."""

_PROMPT = """Context:
{context}

Query type: {query_type}
Question: {question}"""


def fuse(query: str, chunks: list[dict], query_type: str) -> FaqResponse:
    """Call claude-sonnet-4-6 with retrieved context and return FaqResponse."""
    today = str(date.today())

    if not chunks:
        return FaqResponse(
            prose=NOT_IN_KB,
            last_updated=today,
        )

    context = "\n\n---\n\n".join(c["text"] for c in chunks)
    source_urls = list(dict.fromkeys(
        c["source_url"] for c in chunks
        if any(d in c["source_url"] for d in ALLOWED_DOMAINS)
    ))

    prompt = _PROMPT.format(
        context=context,
        query_type=query_type,
        question=query,
    )

    try:
        msg = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
    except anthropic.APIError:
        return FaqResponse(
            refused=True,
            refusal_msg="Service temporarily unavailable. Please try again.",
            last_updated=today,
        )

    # Parse bullets vs prose
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    bullets = [l for l in lines if l[0].isdigit() and "." in l[:3]]

    # Extract source URLs from response text if any
    import re
    url_matches = re.findall(r"https?://\S+", raw)
    for url in url_matches:
        url = url.rstrip(")")
        if any(d in url for d in ALLOWED_DOMAINS) and url not in source_urls:
            source_urls.append(url)

    if query_type == "compound" and bullets:
        return FaqResponse(
            bullets=bullets[:6],
            sources=source_urls[:3],
            last_updated=today,
        )

    # Prose response — strip Source: line from text
    prose_lines = [l for l in lines if not l.startswith("Source:") and not l.startswith("Last updated")]
    prose = " ".join(prose_lines)

    return FaqResponse(
        prose=prose or raw,
        sources=source_urls[:2],
        last_updated=today,
    )
