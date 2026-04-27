import os
from dataclasses import dataclass, field
from datetime import date

import anthropic

_client = None
NOT_IN_KB = "This information is not available in our knowledge base. Please check https://www.amfiindia.com"

ALLOWED_DOMAINS = ["sbimf.com", "amfiindia.com", "sebi.gov.in", "indmoney.com", "camsonline.com", "mfcentral.com"]


@dataclass
class FaqResponse:
    refused:     bool            = False
    refusal_msg: str | None      = None
    bullets:     list[str]       = field(default_factory=list)
    prose:       str | None      = None
    sources:     list[str]       = field(default_factory=list)
    last_updated: str            = ""
    query_type:  str             = ""


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


_SYSTEM = """You are a Facts-Only Mutual Fund Assistant for INDMoney users.
Answer using ONLY the retrieved context provided below.

Rules:
- FUND SPECIFICITY: Answer ONLY about the exact fund(s) named in the question. Never use data from other funds as substitutes.
- For compound questions (query_type=compound): write numbered bullet points (max 6). EACH bullet must be a single self-contained line in the form "N. Topic — answer text here." with the full answer on that same line. Do NOT write a heading on one line and the answer on the next line.
- FEE COMPLETENESS: Whenever the question is about fees, charges, or costs — always include ALL fee-related fields present in context as separate bullets: Exit Load %, Expense Ratio %, lock-in period, and any redemption terms. Do not stop after answering only the specific fee asked; cover the full fee picture.
- For simple factual or fee questions: respond in ≤3 clear sentences.
- Never infer returns. Never recommend funds.
- "Not available" rule: only say information is unavailable when the context truly has no data for that fund. Never add this disclaimer after you have already answered.
- End with "Source: <exact_url>" — use only the raw URL, no markdown link syntax."""

_PROMPT = """Context:
{context}

Query type: {query_type}
Question: {question}

Answer only about the specific fund(s) named above. Each numbered point must contain its full answer on the same line.
If the question is about fees or charges, cover ALL fee components available in the context (exit load, expense ratio, lock-in, redemption terms) as separate numbered bullets."""


def _extract_bullets(lines: list[str]) -> list[str]:
    """Collect numbered sections from LLM output.

    Handles two formats the LLM may produce:
      A) Single-line: "1. Topic — answer on same line."
      B) Multi-line:  "1. Topic heading:"
                      "   answer text on next line(s)"
    Returns one merged string per numbered item.
    """
    import re
    bullets: list[str] = []
    current: list[str] = []

    for line in lines:
        if re.match(r"^\d+[\.\)]\s", line):
            if current:
                bullets.append(" ".join(current))
            current = [line]
        elif current and not line.startswith("Source:") and not line.startswith("Last updated"):
            # continuation line for the current numbered item
            current.append(line)
        else:
            if current:
                bullets.append(" ".join(current))
                current = []

    if current:
        bullets.append(" ".join(current))

    return bullets


def fuse(query: str, chunks: list[dict], query_type: str) -> FaqResponse:
    """Call claude-sonnet-4-6 with retrieved context and return FaqResponse."""
    today = str(date.today())

    if not chunks:
        return FaqResponse(
            prose=NOT_IN_KB,
            last_updated=today,
            query_type=query_type,
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
            query_type=query_type,
        )

    import re

    # Extract source URLs — stop at markdown/punctuation chars that aren't part of a URL
    url_matches = re.findall(r"https?://[^\s\)\]\,\"\'<>]+", raw)
    for url in url_matches:
        url = url.rstrip("./,")
        if any(d in url for d in ALLOWED_DOMAINS) and url not in source_urls:
            source_urls.append(url)

    # Parse bullets: collect numbered sections (header line + any continuation lines)
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    bullets = _extract_bullets(lines)

    if query_type == "compound" and bullets:
        return FaqResponse(
            bullets=bullets[:6],
            sources=source_urls[:3],
            last_updated=today,
            query_type=query_type,
        )

    # Prose response — strip Source: / Last updated lines
    prose_lines = [l for l in lines if not l.startswith("Source:") and not l.startswith("Last updated")]
    prose = " ".join(prose_lines)

    return FaqResponse(
        prose=prose or raw,
        sources=source_urls[:2],
        last_updated=today,
        query_type=query_type,
    )
