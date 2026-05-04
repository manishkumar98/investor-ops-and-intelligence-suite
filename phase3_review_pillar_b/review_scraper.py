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


def _scrape_lang(
    app_id: str,
    lang: str,
    cutoff,
    batch_size: int,
    cap: int,
) -> list[dict]:
    """Scrape one language pass — returns raw review dicts up to cutoff/cap."""
    from google_play_scraper import reviews as gp_reviews, Sort

    collected = []
    continuation_token = None

    while True:
        try:
            kwargs = dict(
                app_id=app_id,
                lang=lang,
                country="in",
                sort=Sort.NEWEST,
                count=batch_size,
            )
            if continuation_token:
                kwargs["continuation_token"] = continuation_token
            result, continuation_token = gp_reviews(**kwargs)
        except Exception as exc:
            print(f"[review_scraper] Fetch error ({lang}): {exc}")
            break

        if not result:
            break

        hit_cutoff = False
        for r in result:
            ts = r.get("at")
            if ts is None:
                continue
            from datetime import timezone as _tz
            review_dt = ts if ts.tzinfo else ts.replace(tzinfo=_tz.utc)
            if review_dt < cutoff:
                hit_cutoff = True
                break
            collected.append({
                "source":      "Google Play",
                "review_id":   r.get("reviewId", ""),
                "date":        str(r.get("at", "")),
                "rating":      r.get("score", 3),
                "review_text": _clean_text(r.get("content", "")),
                "lang":        lang,
            })

        if hit_cutoff or not continuation_token or len(collected) >= cap:
            break

    return collected


def scrape_google_play(
    app_id: str = INDMONEY_APP_ID,
    lookback_weeks: int = 12,
    batch_size: int = 200,
    cap: int = 1000,
) -> pd.DataFrame:
    """Scrape reviews from Google Play — English + Hindi, NEWEST sort, stopping once
    reviews fall outside the lookback window. Caps combined result at `cap` reviews.
    """
    from datetime import datetime, timedelta, timezone

    cutoff = datetime.now(timezone.utc) - timedelta(weeks=lookback_weeks)
    print(f"[review_scraper] Fetching EN+HI reviews since {cutoff.strftime('%Y-%m-%d')} ({lookback_weeks} weeks)")

    en_reviews = _scrape_lang(app_id, "en", cutoff, batch_size, cap)
    hi_reviews = _scrape_lang(app_id, "hi", cutoff, batch_size, cap)
    print(f"[review_scraper] Raw: {len(en_reviews)} EN + {len(hi_reviews)} HI")

    all_reviews = en_reviews + hi_reviews
    if not all_reviews:
        return pd.DataFrame(columns=["source", "review_id", "date", "rating", "review_text", "lang"])

    df = pd.DataFrame(all_reviews).drop_duplicates(subset=["review_id"]).reset_index(drop=True)
    if len(df) > cap:
        df = df.head(cap)
    print(f"[review_scraper] {len(df)} reviews after dedup (EN+HI) within last {lookback_weeks} weeks")
    return df


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
