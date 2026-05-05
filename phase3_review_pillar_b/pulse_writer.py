import os
import re

import anthropic

_client = None

MAX_RETRIES = 3
MAX_WORDS = 250


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


_SYSTEM = (
    "You are a product analyst writing a concise internal weekly note. "
    "Reply with plain text only — no markdown headers, no bullet points, no numbered lists."
)

_PROMPT = """Write a weekly product pulse narrative for the INDMoney app based on these themes and quotes.

Top 3 themes: {themes}

User quotes (one per theme, in theme order):
{quotes}

Requirements:
- Maximum 250 words total (strictly enforced — count every word)
- Pure narrative prose only — NO action ideas, NO numbered lists, NO bullet points
- Cover all 3 themes and reference the quotes naturally in the narrative
- No PII in the output
- Neutral, facts-only tone
- Do NOT include a header or title"""


def write(themes: list[str], quotes: list[dict]) -> str:
    """Write a ≤250-word narrative note. Action ideas come from theme_clusterer, not here."""
    quotes_text = "\n".join(
        f'- "{q["quote"]}" (Rating: {q["rating"]}/5)' for q in quotes
    )
    prompt = _PROMPT.format(
        themes=", ".join(themes),
        quotes=quotes_text,
    )

    for attempt in range(1, MAX_RETRIES + 1):
        msg = _get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        pulse = msg.content[0].text.strip()
        # Strip any numbered lines the model may still emit
        pulse = re.sub(r"(?m)^\d+\. .+$\n?", "", pulse).strip()

        if len(pulse.split()) <= MAX_WORDS:
            return pulse

        if attempt == MAX_RETRIES:
            # Hard-truncate to 250 words
            return " ".join(pulse.split()[:MAX_WORDS])

    return "User feedback this week highlights concerns around app performance, support responsiveness, and investment flow usability."

