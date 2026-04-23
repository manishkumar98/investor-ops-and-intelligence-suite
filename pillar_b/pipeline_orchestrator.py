import io
from typing import Union

import pandas as pd

from pillar_b.pii_scrubber import scrub
from pillar_b.theme_clusterer import cluster
from pillar_b.quote_extractor import extract
from pillar_b.pulse_writer import write
from pillar_b.fee_explainer import explain


REQUIRED_COLUMNS = {"review_id", "review_text", "rating"}


def run_pipeline(csv_source: Union[str, io.IOBase], session: dict) -> dict:
    """Full M2 pipeline: CSV → themes → pulse → fee → session writes.

    Enqueues 2 MCP actions (notes_append + email_draft) via enqueue_action().
    Returns a result dict consumed by Tab 2 in app.py.
    """
    # ── 1. Load CSV ─────────────────────────────────────────────────────────
    if isinstance(csv_source, str):
        df = pd.read_csv(csv_source)
    else:
        df = pd.read_csv(csv_source)

    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Reviews CSV missing columns: {', '.join(missing)}")

    # Fill NaN dates / sources gracefully
    if "date" not in df.columns:
        df["date"] = ""
    if "source" not in df.columns:
        df["source"] = ""

    # ── 2. PII scrub ────────────────────────────────────────────────────────
    clean_reviews = []
    for _, row in df.iterrows():
        clean_text, _ = scrub(str(row["review_text"]))
        clean_reviews.append({
            "review_id":   str(row["review_id"]),
            "review_text": clean_text,
            "rating":      row["rating"],
            "date":        row.get("date", ""),
        })

    # ── 3. Theme clustering (2-pass for large datasets, from M2) ───────────
    cluster_result = cluster(clean_reviews)
    themes       = cluster_result["themes"]
    top_3        = cluster_result["top_3"]
    action_ideas = cluster_result.get("action_ideas", [])
    top_theme    = top_3[0] if top_3 else "General Feedback"

    # Use quotes from cluster result if available (M2 2-pass already extracts them)
    cluster_quotes = cluster_result.get("quotes", [])

    # ── 4. Quote extraction ─────────────────────────────────────────────────
    quotes = extract(clean_reviews, themes, top_3) if not cluster_quotes else [
        {"quote": q, "rating": 3} for q in cluster_quotes
    ]

    # ── 5. Pulse writing ────────────────────────────────────────────────────
    pulse = write(top_3, quotes)
    word_count = len(pulse.split())

    # ── 6. Fee explainer ────────────────────────────────────────────────────
    fee_result = explain(top_theme, session)

    # ── 7. Write session state ──────────────────────────────────────────────
    session["weekly_pulse"]    = pulse
    session["top_theme"]       = top_theme
    session["top_3_themes"]    = top_3
    session["fee_bullets"]     = fee_result["bullets"]
    session["fee_sources"]     = fee_result["sources"]
    session["pulse_generated"] = True

    # ── 8. Enqueue MCP actions ──────────────────────────────────────────────
    from pillar_c.mcp_client import enqueue_action
    from datetime import date

    enqueue_action(
        session,
        type="notes_append",
        payload={
            "doc_title": "Weekly Pulse Notes",
            "entry": {
                "date":         str(date.today()),
                "weekly_pulse": pulse[:500],
                "top_themes":   top_3,
                "fee_scenario": fee_result["scenario"],
            },
        },
        source="m2_pipeline",
    )

    enqueue_action(
        session,
        type="email_draft",
        payload={
            "subject": f"Weekly Pulse + Fee Explainer — {date.today()}",
            "body": (
                f"Weekly Pulse:\n{pulse}\n\n"
                f"Fee Context ({fee_result['scenario'].replace('_', ' ')}):\n"
                + "\n".join(fee_result["bullets"])
                + f"\n\nSources: {', '.join(fee_result['sources'])}"
                + f"\n\nLast checked: {fee_result['checked']}"
            ),
        },
        source="m2_pipeline",
    )

    return {
        "top_3":        top_3,
        "quotes":       quotes,
        "pulse":        pulse,
        "word_count":   word_count,
        "action_ideas": action_ideas,
        "fee_bullets":  fee_result["bullets"],
        "fee_sources":  fee_result["sources"],
        "fee_checked":  fee_result["checked"],
    }
