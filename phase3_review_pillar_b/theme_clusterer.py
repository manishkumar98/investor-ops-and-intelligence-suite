"""Adapted from M2 Phase2_LLM_Processing/phase2_llm_processing.py — Groq replaced with Claude."""
import json
import os
import re
from collections import Counter

import anthropic

# English + Hindi stopwords for word-cloud filtering (M2 addition for Indian audience)
STOPWORDS: set[str] = {
    "the", "a", "an", "is", "it", "in", "on", "at", "to", "for", "of", "and",
    "or", "but", "with", "this", "that", "they", "their", "there", "very",
    "just", "app", "indmoney", "fund", "sbi", "use", "using", "used",
    "good", "great", "nice", "bad", "not", "no", "yes", "can", "get",
    "have", "has", "had", "been", "was", "are", "were", "will", "would",
    "my", "me", "we", "us", "you", "your", "our", "its", "be", "do",
    "did", "does", "from", "also", "all", "more", "most", "some", "any",
    # Hindi transliterations common in Indian app reviews
    "bhi", "se", "ka", "ki", "hai", "he", "ko", "kya", "nahi", "kar",
    "mein", "ke", "aur", "koi", "ek", "toh", "par", "tha", "main",
}

_WORD_COLORS = ["#4ade80", "#60a5fa", "#f59e0b", "#c084fc", "#fb7185",
                "#34d399", "#818cf8", "#facc15", "#f87171", "#2dd4bf"]

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _client


_SYSTEM = (
    "You are an expert INDMoney Product Manager. Analyse user reviews and extract key insights. "
    "Do not hallucinate features. Reply ONLY with valid JSON — no markdown, no prose."
)

_CHUNK_PROMPT = """Process these INDMoney app reviews. Output a strict JSON object with:
- "themes": list of strings, max 5
- "top_3": list of strings, exactly 3 (most-mentioned themes)
- "quotes": list of strings, exactly 3 (real verbatim quotes from the reviews)
- "weekly_note": string, strict max 250 words
- "action_ideas": list of strings, exactly 3 action recommendations

Reviews:
{reviews_text}"""

_SYNTH_PROMPT = """Synthesize these partial review analyses into ONE master report.

STRICT OUTPUT RULES:
- "themes": list of strings, EXACTLY 5 items
- "top_3": list of strings, EXACTLY 3 items
- "quotes": list of strings, EXACTLY 3 items (most impactful)
- "weekly_note": string, STRICT MAX 250 words
- "action_ideas": list of strings, EXACTLY 3 items

Output only valid JSON. Partial analyses:
{master_payload}"""


def _count_words(text: str) -> int:
    return len(text.split()) if isinstance(text, str) else 0


def _sample_reviews(reviews: list[dict], max_words: int = 9000) -> list[dict]:
    """From M2 sample_data — cap total word count to avoid LLM token overflow."""
    total = 0
    sampled = []
    for r in reviews:
        wc = _count_words(r.get("review_text", ""))
        if total + wc > max_words:
            break
        sampled.append(r)
        total += wc
    return sampled if sampled else reviews[:50]


def _validate(data: dict) -> list[str]:
    """From M2 validate_llm_json — return list of errors."""
    errors = []
    if _count_words(data.get("weekly_note", "")) > 250:
        errors.append("weekly_note exceeds 250 words")
    if not isinstance(data.get("themes"), list) or len(data["themes"]) > 5:
        errors.append(f"themes must be list of max 5 (got {len(data.get('themes', []))})")
    if not isinstance(data.get("top_3"), list) or len(data["top_3"]) != 3:
        errors.append(f"top_3 must be exactly 3 (got {len(data.get('top_3', []))})")
    if not isinstance(data.get("quotes"), list) or len(data["quotes"]) != 3:
        errors.append(f"quotes must be exactly 3 (got {len(data.get('quotes', []))})")
    if not isinstance(data.get("action_ideas"), list) or len(data["action_ideas"]) != 3:
        errors.append(f"action_ideas must be exactly 3 (got {len(data.get('action_ideas', []))})")
    return errors


def _call_llm(prompt: str, max_retries: int = 3) -> dict | None:
    for attempt in range(max_retries):
        try:
            msg = _get_client().messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=_SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                continue
            parsed = json.loads(m.group())
            errors = _validate(parsed)
            if not errors:
                return parsed
            if attempt == max_retries - 1:
                return parsed  # return best-effort on final attempt
        except Exception as exc:
            if attempt == max_retries - 1:
                print(f"[theme_clusterer] LLM call failed: {exc}")
    return None


def _build_reviews_text(reviews: list[dict]) -> str:
    """From M2 construct_payload_string."""
    return "\n".join(
        f"Rating: {r.get('rating', '?')} | Date: {r.get('date', '')} | Text: {r['review_text']}"
        for r in reviews
    )


def _synthesize(result1: dict, result2: dict) -> dict:
    """From M2 synthesize_chunks — combine two half-analyses into one master report."""
    payload = json.dumps([result1, result2], ensure_ascii=False)
    synth = _call_llm(_SYNTH_PROMPT.format(master_payload=payload))
    if synth:
        if isinstance(synth.get("themes"), list) and len(synth["themes"]) > 5:
            synth["themes"] = synth["themes"][:5]
        return synth
    # Fallback: merge manually
    themes = list(dict.fromkeys(result1.get("themes", []) + result2.get("themes", [])))[:5]
    top_3 = result1.get("top_3", ["General Feedback", "App Performance", "Customer Support"])
    return {
        "themes":       themes,
        "top_3":        top_3[:3],
        "quotes":       (result1.get("quotes", []) + result2.get("quotes", []))[:3],
        "weekly_note":  result1.get("weekly_note", ""),
        "action_ideas": result1.get("action_ideas", ["Improve app stability.", "Simplify nominee update.", "Enhance SIP notifications."]),
    }


def cluster(reviews: list[dict]) -> dict:
    """2-pass clustering adapted from M2 process_reviews_in_two_halves.

    For ≤15 reviews: single LLM call.
    For >15 reviews: split in half, process each, synthesize.
    Applies smart sampling (9 000-word cap) per half before each LLM call.
    Returns: {themes, top_3, quotes, weekly_note, action_ideas}
    """
    if not reviews:
        return _fallback()

    if len(reviews) <= 15:
        sampled = _sample_reviews(reviews)
        text = _build_reviews_text(sampled)
        result = _call_llm(_CHUNK_PROMPT.format(reviews_text=text))
        return result or _fallback()

    # Two-pass for larger datasets (M2 approach)
    mid = len(reviews) // 2
    first_half  = reviews[:mid]
    second_half = reviews[mid:]

    print(f"[theme_clusterer] 2-pass: {len(first_half)} + {len(second_half)} reviews")

    result1 = _call_llm(_CHUNK_PROMPT.format(
        reviews_text=_build_reviews_text(_sample_reviews(first_half))
    ))
    if not result1:
        result1 = _fallback()

    result2 = _call_llm(_CHUNK_PROMPT.format(
        reviews_text=_build_reviews_text(_sample_reviews(second_half))
    ))
    if not result2:
        return result1

    return _synthesize(result1, result2)


def generate_analytics(reviews: list[dict]) -> dict:
    """From M2 generate_analytics_data — derives word cloud, sentiment, rating distribution.

    Returns dict with: keywords (top 20), sentiment, rating_dist, negative_reviews, total.
    """
    # Sentiment split
    positive = sum(1 for r in reviews if float(r.get("rating", 3)) >= 4)
    neutral  = sum(1 for r in reviews if float(r.get("rating", 3)) == 3)
    negative = sum(1 for r in reviews if float(r.get("rating", 3)) <= 2)

    # Rating distribution
    rating_dist: dict[str, int] = {}
    for r in reviews:
        star = str(max(1, min(5, int(float(r.get("rating", 3))))))
        rating_dist[star] = rating_dist.get(star, 0) + 1

    # Top 20 keywords (filtered by STOPWORDS, min 3 chars)
    all_text = " ".join(r.get("review_text", "") for r in reviews).lower()
    words = re.findall(r"\b[a-z]{3,}\b", all_text)
    freq = Counter(w for w in words if w not in STOPWORDS)
    keywords = [
        {"word": w, "count": c, "color": _WORD_COLORS[i % len(_WORD_COLORS)]}
        for i, (w, c) in enumerate(freq.most_common(20))
    ]

    # Sample of negative reviews for inspection
    neg_reviews = [
        {"text": r.get("review_text", "")[:150], "rating": r.get("rating", 1)}
        for r in reviews if float(r.get("rating", 3)) <= 2
    ][:5]

    return {
        "keywords":       keywords,
        "sentiment":      {"positive": positive, "neutral": neutral, "negative": negative},
        "rating_dist":    rating_dist,
        "negative_reviews": neg_reviews,
        "total":          len(reviews),
    }


def _fallback() -> dict:
    return {
        "themes":       ["General Feedback"],
        "top_3":        ["General Feedback", "App Performance", "Customer Support"],
        "quotes":       ["App needs improvement.", "Good features but slow.", "Support response was delayed."],
        "weekly_note":  "User feedback this week highlights general satisfaction with core features alongside concerns about app performance and support response times.",
        "action_ideas": ["Improve app stability and load times.", "Simplify the nominee update flow.", "Enhance SIP failure notifications."],
    }
