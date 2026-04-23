import json
import os
import re

import anthropic

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


_SYSTEM = (
    "You are a product analyst. Cluster the provided app reviews into themes. "
    "Reply ONLY with valid JSON — no markdown, no prose."
)

_PROMPT = """Analyse these INDMoney app reviews and return exactly this JSON structure:

{{
  "themes": [
    {{"theme": "<name>", "description": "<1 sentence>", "review_ids": [<list of ids>]}}
  ],
  "top_3": ["<theme1>", "<theme2>", "<theme3>"]
}}

Rules:
- Maximum 5 themes total
- top_3 must list the three most-mentioned themes
- Use the review_id field from each review in review_ids

Reviews (JSON array):
{reviews_json}"""


def cluster(reviews: list[dict]) -> dict:
    """Return {{themes: [...], top_3: [..., ..., ...]}}."""
    reviews_json = json.dumps(
        [{"id": r["review_id"], "text": r["review_text"], "rating": r.get("rating")}
         for r in reviews],
        ensure_ascii=False,
        indent=2,
    )

    prompt = _PROMPT.format(reviews_json=reviews_json)
    msg = _get_client().messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()

    # Defensive parse — extract first {...} block
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if "themes" in result and "top_3" in result:
                return result
        except json.JSONDecodeError:
            pass

    # Fallback: single-theme response so pipeline never crashes
    return {
        "themes": [{"theme": "General Feedback", "description": "Mixed user feedback", "review_ids": []}],
        "top_3": ["General Feedback", "General Feedback", "General Feedback"],
    }
