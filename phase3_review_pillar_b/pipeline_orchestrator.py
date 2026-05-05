import io
from typing import Union

import pandas as pd

from .pii_scrubber import scrub
from .theme_clusterer import cluster, generate_analytics
from .quote_extractor import extract
from .pulse_writer import write
from .fee_explainer import explain


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

    # ── 5. Pulse writing — narrative note only (action ideas come from clusterer) ─
    # Use weekly_note from cluster_result if available; otherwise generate via pulse_writer
    weekly_note = cluster_result.get("weekly_note", "")
    if not weekly_note or len(weekly_note.split()) < 20:
        weekly_note = write(top_3, quotes)
    word_count = len(weekly_note.split())

    # ── 6. Fee explainer ────────────────────────────────────────────────────
    fee_result = explain(top_theme, session)

    # ── 7. Analytics (word cloud, sentiment, rating distribution) ───────────
    analytics = generate_analytics(clean_reviews)

    # ── 8. Write session state ──────────────────────────────────────────────
    session["weekly_pulse"]    = weekly_note
    session["top_theme"]       = top_theme
    session["top_3_themes"]    = top_3
    session["pulse_quotes"]    = cluster_result.get("quotes", [q["quote"] for q in quotes])
    session["action_ideas"]    = action_ideas
    session["fee_bullets"]     = fee_result["bullets"]
    session["fee_sources"]     = fee_result["sources"]
    session["pulse_generated"] = True
    session["analytics_data"]  = analytics

    # ── 9. Enqueue M2 MCP actions (pending HITL approval) ──────────────────
    try:
        from phase7_pillar_c_hitl.mcp_client import enqueue_action
        from datetime import date
        _today = str(date.today())
        enqueue_action(session, type="notes_append", source="m2_pipeline", payload={
            "doc_title": "Weekly Product Pulse",
            "entry": {
                "date":               _today,
                "weekly_pulse":       weekly_note,
                "top_3_themes":       top_3,
                "fee_bullets":        fee_result["bullets"],
                "source_links":       fee_result["sources"],
            },
        })
        enqueue_action(session, type="email_draft", source="m2_pipeline", payload={
            "subject": f"Weekly Pulse — {_today}",
            "body":    f"Top themes: {', '.join(top_3)}\n\n{weekly_note}",
            "to":      "advisor-team@nia.one",
        })
    except Exception:
        pass  # MCP enqueue is best-effort; pipeline result is still returned

    return {
        "top_3":        top_3,
        "quotes":       quotes,
        "pulse":        {"weekly_note": weekly_note, "action_ideas": action_ideas},
        "word_count":   word_count,
        "action_ideas": action_ideas,
        "fee_bullets":  fee_result["bullets"],
        "fee_sources":  fee_result["sources"],
        "fee_checked":  fee_result["checked"],
        "analytics":    analytics,
    }
