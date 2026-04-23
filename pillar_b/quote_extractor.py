from pillar_b.pii_scrubber import scrub


def extract(clean_reviews: list[dict], themes: list[dict], top_3: list[str]) -> list[dict]:
    """Return up to 3 representative quotes, one per top theme."""
    theme_map = {t["theme"]: t for t in themes}
    quotes = []

    for theme_name in top_3:
        theme_data = theme_map.get(theme_name)
        if not theme_data:
            continue

        candidate_ids = set(theme_data.get("review_ids", []))
        candidates = [
            r for r in clean_reviews
            if r.get("review_id") in candidate_ids and r.get("review_text")
        ]

        if not candidates:
            # Fall back to any review
            candidates = [r for r in clean_reviews if r.get("review_text")]

        if not candidates:
            continue

        # Pick the review with the highest rating (most representative positive)
        best = max(candidates, key=lambda r: float(r.get("rating", 3)))
        quote_text, _ = scrub(best["review_text"])

        # Trim to ~150 chars for readability
        if len(quote_text) > 150:
            quote_text = quote_text[:147] + "..."

        quotes.append({
            "theme":  theme_name,
            "quote":  quote_text,
            "rating": best.get("rating", "N/A"),
        })

    return quotes[:3]
