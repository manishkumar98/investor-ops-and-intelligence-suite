"""Adapted from M2 Phase1_Data_Ingestion/phase1_data_ingestion.py
Scrapes INDMoney app reviews from Google Play Store.
Saves to data/reviews_latest.csv with columns: review_id, review_text, rating, date, source.
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

INDMONEY_APP_ID = "com.indmoney.indstocks"


def _clean_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    try:
        import emoji
        text = emoji.replace_emoji(text, replace="")
    except ImportError:
        pass
    text = re.sub(r"\S+@\S+", "[EMAIL]", text)
    text = re.sub(r"\+?\d[( -]*\d{3}[) -]*\d{3}[ -]*\d{4}", "[PHONE]", text)
    text = re.sub(r"\b\d{10}\b", "[PHONE]", text)
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def scrape_google_play(app_id: str = INDMONEY_APP_ID, max_per_rating: int = 400) -> pd.DataFrame:
    """Scrape reviews from Google Play — both MOST_RELEVANT and NEWEST sorts."""
    from google_play_scraper import reviews as gp_reviews, Sort

    all_reviews = []
    for sort_method in [Sort.MOST_RELEVANT, Sort.NEWEST]:
        for score in range(1, 6):
            try:
                result, _ = gp_reviews(
                    app_id,
                    lang="en",
                    country="in",
                    sort=sort_method,
                    count=max_per_rating,
                    filter_score_with=score,
                )
                for r in result:
                    all_reviews.append({
                        "source":      "Google Play",
                        "review_id":   r.get("reviewId", ""),
                        "date":        str(r.get("at", "")),
                        "rating":      r.get("score", 3),
                        "review_text": _clean_text(r.get("content", "")),
                    })
            except Exception as exc:
                print(f"[review_scraper] ({sort_method.name}, {score}★): {exc}")

    if not all_reviews:
        return pd.DataFrame(columns=["source", "review_id", "date", "rating", "review_text"])

    df = pd.DataFrame(all_reviews)
    return df.drop_duplicates(subset=["review_id"]).reset_index(drop=True)


def run_scraper(output_path: Path | None = None) -> pd.DataFrame:
    """Scrape → clean → deduplicate → cap 1 000 → save CSV. Returns DataFrame.

    Falls back to data/reviews_sample.csv if the live scrape returns nothing
    (e.g., no network, rate-limited).
    """
    if output_path is None:
        output_path = ROOT / "data" / "reviews_latest.csv"

    print("[review_scraper] Scraping Google Play Store…")
    df = scrape_google_play()

    if df.empty:
        print("[review_scraper] Live scrape empty — falling back to reviews_sample.csv")
        fallback = ROOT / "data" / "reviews_sample.csv"
        if fallback.exists():
            df = pd.read_csv(fallback)
            if "review_text" not in df.columns and "text" in df.columns:
                df = df.rename(columns={"text": "review_text"})
        else:
            raise RuntimeError("No reviews available: live scrape empty and no fallback CSV found.")

    # Drop < 5-word reviews and duplicates
    df = df[df["review_text"].apply(lambda t: len(str(t).split()) >= 5)]
    df = df.drop_duplicates(subset=["review_text"]).reset_index(drop=True)

    # Cap at 1 000 with proportional rating distribution
    if len(df) > 1000:
        weights = df["rating"].value_counts(normalize=True)
        samples = []
        for r, w in weights.items():
            r_df = df[df["rating"] == r]
            n = min(len(r_df), max(1, int(round(1000 * w))))
            samples.append(r_df.sample(n=n, random_state=42))
        df = pd.concat(samples).reset_index(drop=True)
        if len(df) > 1000:
            df = df.sample(n=1000, random_state=42).reset_index(drop=True)

    df.to_csv(output_path, index=False)
    print(f"[review_scraper] {len(df)} reviews saved → {output_path}")
    return df
