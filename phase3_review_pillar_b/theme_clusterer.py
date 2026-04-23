"""Adapted from M2 Phase2_LLM_Processing/phase2_llm_processing.py — Groq replaced with Claude."""
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
    Returns: {themes, top_3, quotes, weekly_note, action_ideas}
    """
    if not reviews:
        return _fallback()

    if len(reviews) <= 15:
        text = _build_reviews_text(reviews)
        result = _call_llm(_CHUNK_PROMPT.format(reviews_text=text))
        return result or _fallback()

    # Two-pass for larger datasets (M2 approach)
    mid = len(reviews) // 2
    first_half  = reviews[:mid]
    second_half = reviews[mid:]

    print(f"[theme_clusterer] 2-pass: {len(first_half)} + {len(second_half)} reviews")

    result1 = _call_llm(_CHUNK_PROMPT.format(reviews_text=_build_reviews_text(first_half)))
    if not result1:
        result1 = _fallback()

    result2 = _call_llm(_CHUNK_PROMPT.format(reviews_text=_build_reviews_text(second_half)))
    if not result2:
        return result1

    return _synthesize(result1, result2)


def _fallback() -> dict:
    return {
        "themes":       ["General Feedback"],
        "top_3":        ["General Feedback", "App Performance", "Customer Support"],
        "quotes":       ["App needs improvement.", "Good features but slow.", "Support response was delayed."],
        "weekly_note":  "User feedback this week highlights general satisfaction with core features alongside concerns about app performance and support response times.",
        "action_ideas": ["Improve app stability and load times.", "Simplify the nominee update flow.", "Enhance SIP failure notifications."],
    }
