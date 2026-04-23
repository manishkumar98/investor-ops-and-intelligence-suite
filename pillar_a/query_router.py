import os

from config import ROUTER_MODE

FACT_KEYWORDS = [
    "nav", "aum", "lock-in", "lock in", "exit load", "fund", "elss", "sip",
    "sbi", "bluechip", "smallcap", "small cap", "flexi", "midcap", "nfo",
    "riskometer", "benchmark", "minimum", "redemption", "statement",
]
FEE_KEYWORDS = [
    "charge", "expense ratio", "ter", "fee", "fees", "stt", "cost",
    "commission", "expense", "brokerage",
]


def route(query: str) -> str:
    """Return 'factual_only', 'fee_only', or 'compound'.

    Default mode: keyword-based (no LLM call, no extra latency).
    Set ROUTER_MODE=llm in .env to use LLM 1-shot classification.
    """
    if ROUTER_MODE == "llm":
        return _llm_route(query)
    return _keyword_route(query)


def _keyword_route(query: str) -> str:
    lower = query.lower()
    has_fact = any(kw in lower for kw in FACT_KEYWORDS)
    has_fee  = any(kw in lower for kw in FEE_KEYWORDS)

    if has_fact and has_fee:
        return "compound"
    if has_fee:
        return "fee_only"
    return "factual_only"


def _llm_route(query: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    prompt = (
        f"Classify this query into one of: factual_only, fee_only, compound.\n"
        f"factual_only = asks about fund facts (NAV, lock-in, SIP minimum, benchmark)\n"
        f"fee_only = asks about charges, expense ratio, TER, exit load, STT\n"
        f"compound = asks about BOTH facts and fees\n\n"
        f"Query: {query}\n\nReply with one word only."
    )
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=10,
        messages=[{"role": "user", "content": prompt}],
    )
    result = msg.content[0].text.strip().lower()
    if "fee" in result and "compound" not in result:
        return "fee_only"
    if "compound" in result:
        return "compound"
    return "factual_only"
