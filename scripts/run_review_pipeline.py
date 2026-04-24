"""Full weekly review pipeline: scrape → PII scrub → cluster → analytics → fee → save JSONs.

Usage:
    python scripts/run_review_pipeline.py

Called by GitHub Actions cron weekly.
Outputs written to data/:
    reviews_latest.csv     — scraped + cleaned reviews
    pulse_latest.json      — themes, quotes, weekly note, action ideas
    analytics_latest.json  — keywords, sentiment, rating distribution
    fee_latest.json        — fee explainer bullets + sources
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


def run_pipeline(status_cb=None) -> dict:
    """Run full pipeline, save outputs to data/, return result dict.

    status_cb: optional callable(str) for progress messages (used by Streamlit).
    """
    def _log(msg: str) -> None:
        print(msg)
        if status_cb:
            status_cb(msg)

    timestamp = datetime.now().isoformat()

    # Step 1 — Scrape
    _log("Step 1/5 — Scraping reviews from Google Play…")
    from phase3_review_pillar_b.review_scraper import run_scraper
    df = run_scraper(ROOT / "data" / "reviews_latest.csv")

    # Step 2 — PII scrub
    _log(f"Step 2/5 — PII scrubbing {len(df)} reviews…")
    from phase3_review_pillar_b.pii_scrubber import scrub
    clean_reviews = []
    for _, row in df.iterrows():
        clean_text, _ = scrub(str(row["review_text"]))
        clean_reviews.append({
            "review_id":   str(row.get("review_id", "")),
            "review_text": clean_text,
            "rating":      row["rating"],
            "date":        str(row.get("date", "")),
        })

    # Step 3 — Theme clustering
    _log("Step 3/5 — Theme clustering (2-pass with Claude)…")
    from phase3_review_pillar_b.theme_clusterer import cluster, generate_analytics
    cluster_result = cluster(clean_reviews)

    # Step 4 — Analytics
    _log("Step 4/5 — Generating analytics…")
    analytics = generate_analytics(clean_reviews)
    analytics["generated_at"] = timestamp
    analytics["review_count"] = len(clean_reviews)

    # Step 5 — Fee explainer
    _log("Step 5/5 — Fee context (RAG retrieval)…")
    from phase3_review_pillar_b.fee_explainer import explain
    top_theme = cluster_result.get("top_3", ["General Feedback"])[0]
    fee_result = explain(top_theme, {})

    # Build output dicts
    pulse_data = {
        "themes":       cluster_result.get("themes", []),
        "top_3_themes": cluster_result.get("top_3", []),
        "quotes":       cluster_result.get("quotes", []),
        "weekly_note":  cluster_result.get("weekly_note", ""),
        "action_ideas": cluster_result.get("action_ideas", []),
        "generated_at": timestamp,
        "review_count": len(clean_reviews),
    }
    fee_data = {
        "scenario":     fee_result.get("scenario", ""),
        "bullets":      fee_result.get("bullets", []),
        "sources":      fee_result.get("sources", []),
        "checked":      fee_result.get("checked", ""),
        "generated_at": timestamp,
    }

    # Save to data/
    data_dir = ROOT / "data"
    (data_dir / "pulse_latest.json").write_text(
        json.dumps(pulse_data, indent=2, ensure_ascii=False)
    )
    (data_dir / "analytics_latest.json").write_text(
        json.dumps(analytics, indent=2, ensure_ascii=False)
    )
    (data_dir / "fee_latest.json").write_text(
        json.dumps(fee_data, indent=2, ensure_ascii=False)
    )

    # Update system_state
    state_file = data_dir / "system_state.json"
    try:
        state = json.loads(state_file.read_text()) if state_file.exists() else {}
    except Exception:
        state = {}
    state["last_pipeline_run"] = timestamp
    state["last_review_count"] = len(clean_reviews)
    state_file.write_text(json.dumps(state, indent=2))

    # Bake data into dashboard.html
    _log("Updating dashboard.html…")
    try:
        from scripts.update_dashboard import run as _update_dashboard
        _update_dashboard()
    except ImportError:
        try:
            from update_dashboard import run as _update_dashboard  # direct script run
            _update_dashboard()
        except Exception as exc:
            print(f"[run_review_pipeline] dashboard update skipped: {exc}")
    except Exception as exc:
        print(f"[run_review_pipeline] dashboard update failed: {exc}")

    _log(f"✅ Pipeline complete — {len(clean_reviews)} reviews → data/ written.")
    return {"pulse": pulse_data, "analytics": analytics, "fee": fee_data}


if __name__ == "__main__":
    run_pipeline()
