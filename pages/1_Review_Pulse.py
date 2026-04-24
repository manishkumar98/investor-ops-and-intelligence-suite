"""Phase 3 — Weekly Review Pulse Pipeline

Full step-by-step UI:
  Phase 1 (foundation): env health, session state
  Phase 2 (corpus):     FAQ/Fee corpus status, RAG-driven fee context
  Phase 3 (pipeline):   PII scrub → theme analysis → quotes → pulse → fees → MCP queue
"""
import io
import json
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import load_env
from session_init import init_session_state

# ── Bootstrap ────────────────────────────────────────────────────────────────
try:
    load_env()
    _env_ok = True
    _env_err = ""
except EnvironmentError as exc:
    _env_ok = False
    _env_err = str(exc)

st.set_page_config(
    page_title="Review Pulse — Phase 3",
    page_icon="📊",
    layout="wide",
)
init_session_state(st.session_state)

# Page-local session keys
for _k in ("rp_df_raw", "rp_df_clean", "rp_cluster", "rp_quotes", "rp_pulse", "rp_fee"):
    if _k not in st.session_state:
        st.session_state[_k] = None

# ── Shared theme + header/footer CSS ─────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }

  .stApp { background-color: #0A0C14; color: #F5F0E8; }

  section[data-testid="stSidebar"] {
    background-color: #10131F !important;
    border-right: 1px solid #1E2235;
  }
  section[data-testid="stSidebar"] * { color: #F5F0E8 !important; }

  .stButton > button {
    background: linear-gradient(135deg, #C9A84C, #A8863C) !important;
    color: #0A0C14 !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    padding: 8px 20px !important;
  }
  .stButton > button:hover { opacity: 0.88 !important; }

  div[data-testid="stMetricValue"] { color: #C9A84C !important; font-weight: 700; }
  h1, h2, h3, h4 { color: #F5F0E8 !important; font-weight: 600 !important; }
  hr { border-color: #1E2235 !important; }

  #MainMenu, footer, header { visibility: hidden; }

  /* ── NAV Ticker ── */
  .ticker-wrap {
    width: 100%; background: #0D0F1A;
    border-bottom: 1px solid #1E2235;
    overflow: hidden; padding: 7px 0;
    position: sticky; top: 0; z-index: 1000;
  }
  .ticker-track {
    display: flex; width: max-content;
    animation: ticker-scroll 38s linear infinite;
  }
  .ticker-track:hover { animation-play-state: paused; }
  @keyframes ticker-scroll {
    0%   { transform: translateX(0); }
    100% { transform: translateX(-50%); }
  }
  .ticker-item {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 0 28px; white-space: nowrap;
    font-size: 0.78rem; border-right: 1px solid #1E2235;
  }
  .ticker-symbol { color: #C9A84C; font-weight: 600; letter-spacing: 0.04em; }
  .ticker-nav    { color: #9A9080; font-size: 0.73rem; }
  .ticker-up     { color: #28a745; font-weight: 600; }
  .ticker-down   { color: #dc3545; font-weight: 600; }
  .ticker-neutral{ color: #9A9080; font-weight: 600; }

  /* ── App header ── */
  .app-header {
    position: sticky; top: 0; z-index: 999;
    background: linear-gradient(90deg, #0A0C14, #10131F);
    border-bottom: 1px solid #1E2235;
    padding: 14px 32px;
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 24px;
  }
  .app-header-left { display: flex; align-items: center; gap: 12px; }
  .app-header-logo { font-size: 1.4rem; }
  .app-header-title { font-size: 1.05rem; font-weight: 700; color: #F5F0E8; letter-spacing: 0.02em; }
  .app-header-subtitle { font-size: 0.72rem; color: #9A9080; margin-top: 1px; }
  .app-header-badge {
    font-size: 0.7rem;
    background-color: rgba(201,168,76,0.12);
    border: 1px solid rgba(201,168,76,0.35);
    color: #C9A84C; border-radius: 20px;
    padding: 4px 12px; font-weight: 500; letter-spacing: 0.04em;
  }

  /* ── Footer ── */
  .app-footer {
    margin-top: 48px; border-top: 1px solid #1E2235;
    padding: 20px 32px;
    display: flex; align-items: center; justify-content: space-between;
    flex-wrap: wrap; gap: 8px;
  }
  .app-footer-left  { font-size: 0.78rem; color: #5A5450; }
  .app-footer-left span { color: #C9A84C; font-weight: 600; }
  .app-footer-right { font-size: 0.72rem; color: #3A3830; }
</style>
""", unsafe_allow_html=True)

# ── NAV Ticker ────────────────────────────────────────────────────────────────
def _build_ticker_html() -> str:
    nav_file = ROOT / "data" / "nav_snapshot.json"
    try:
        data = json.loads(nav_file.read_text())
        funds = data["funds"]
        as_of = data.get("as_of", "")
    except Exception:
        return ""
    items_html = ""
    for f in funds:
        nav  = f["nav"]; prev = f["prev_nav"]
        pct  = (nav - prev) / prev * 100 if prev else 0
        arrow = "▲" if pct > 0 else ("▼" if pct < 0 else "—")
        cls   = "ticker-up" if pct > 0 else ("ticker-down" if pct < 0 else "ticker-neutral")
        sign  = "+" if pct > 0 else ""
        items_html += (
            f'<div class="ticker-item">'
            f'<span class="ticker-symbol">{f["name"]}</span>'
            f'<span class="ticker-nav">₹{nav:,.2f}</span>'
            f'<span class="{cls}">{arrow} {sign}{pct:.2f}%</span>'
            f'</div>'
        )
    track = f'<div class="ticker-track">{items_html}{items_html}</div>'
    as_of_label = f'<span style="font-size:0.65rem;color:#3A3830;padding-left:8px;">NAV as of {as_of}</span>' if as_of else ""
    return f'<div class="ticker-wrap">{track}{as_of_label}</div>'

_ticker = _build_ticker_html()
if _ticker:
    st.markdown(_ticker, unsafe_allow_html=True)

# ── App Header ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
  <div class="app-header-left">
    <div class="app-header-logo">📊</div>
    <div>
      <div class="app-header-title">Investor Ops & Intelligence Suite by Dalal Street Advisors</div>
      <div class="app-header-subtitle">Weekly Review Pulse — Phase 3 Pipeline</div>
    </div>
  </div>
  <div class="app-header-badge">📋 Review Intelligence</div>
</div>
""", unsafe_allow_html=True)

# ── Page CSS: dark cards ──────────────────────────────────────────────────────
st.markdown("""
<style>
.phase-badge {
    display:inline-block;background:#1e3a5f;color:#93c5fd;
    padding:2px 9px;border-radius:10px;font-size:0.72rem;font-weight:600;
    margin-bottom:6px;
}
.theme-chip {
    display:inline-block;padding:4px 11px;border-radius:14px;
    margin:3px;font-size:0.82rem;font-weight:500;
}
.theme-top  { background:#14532d; color:#4ade80; }
.theme-rest { background:#1e293b; color:#94a3b8; }
.quote-card {
    background:#1e293b;border-left:3px solid #4ade80;
    padding:14px;border-radius:6px;height:100%;
}
.quote-theme { color:#4ade80;font-size:0.75rem;font-weight:600;margin-bottom:6px; }
.quote-text  { color:#e2e8f0;font-style:italic;font-size:0.88rem;line-height:1.5; }
.quote-stars { color:#94a3b8;font-size:0.78rem;margin-top:8px; }
.action-card {
    background:#1e293b;border:1px solid #334155;
    padding:12px 16px;border-radius:6px;margin:5px 0;
}
.mcp-row {
    background:#1e293b;border:1px solid #334155;
    padding:10px 14px;border-radius:6px;margin:4px 0;
    display:flex;justify-content:space-between;align-items:center;
}
.badge-pending { background:#b45309;color:#fff;padding:2px 9px;border-radius:10px;font-size:0.73rem; }
.step-head { font-size:1.1rem;font-weight:700;margin:0; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# Sidebar — Phase 1 + Phase 2 health
# ════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("📊 Review Pulse")
    st.caption("Phase 3 · Weekly Investor Review Pipeline")
    st.markdown("---")

    # Phase 1 — environment
    st.markdown('<div class="phase-badge">PHASE 1 — FOUNDATION</div>', unsafe_allow_html=True)
    if _env_ok:
        st.success("✅ API key loaded")
    else:
        st.error(f"❌ {_env_err}")

    # Phase 2 — corpus
    st.markdown('<div class="phase-badge">PHASE 2 — CORPUS</div>', unsafe_allow_html=True)
    _faq_count = _fee_count = 0
    try:
        from phase2_corpus_pillar_a.ingest import get_collection
        _faq_count = get_collection("mf_faq_corpus").count()
        _fee_count = get_collection("fee_corpus").count()
        st.success(f"✅ FAQ corpus: {_faq_count} chunks") if _faq_count else st.warning("⚠ FAQ corpus empty")
        st.success(f"✅ Fee corpus: {_fee_count} chunks") if _fee_count else st.warning("⚠ Fee corpus empty — fallback mode")
    except Exception as e:
        st.error(f"❌ ChromaDB unavailable: {e}")

    st.markdown("---")

    # Session summary
    st.markdown("**Session State**")
    if st.session_state.get("pulse_generated"):
        st.info(f"📊 Top theme: **{st.session_state.get('top_theme', '—')}**")
        for t in st.session_state.get("top_3_themes", []):
            st.caption(f"• {t}")
    else:
        st.caption("No pulse generated yet")

    pending_count = sum(1 for a in st.session_state.get("mcp_queue", []) if a.get("status") == "pending")
    st.metric("MCP Actions Queued", pending_count)

    st.markdown("---")

    # Sample CSV download
    _sample = ROOT / "data" / "reviews_sample.csv"
    if _sample.exists():
        st.download_button("⬇ Download Sample CSV", data=_sample.read_bytes(),
                           file_name="reviews_sample.csv", mime="text/csv")

    if st.button("🔄 Reset Pipeline"):
        for k in ("rp_df_raw", "rp_df_clean", "rp_cluster", "rp_quotes", "rp_pulse", "rp_fee"):
            st.session_state[k] = None
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# Page header
# ════════════════════════════════════════════════════════════════════════════
st.title("📊 Weekly Review Pulse")
st.markdown(
    "Upload investor app reviews → PII scrub → theme analysis → "
    "weekly pulse → fee context → MCP queue."
)

# Pipeline progress bar at top
_steps = ["Upload", "PII Scrub", "Themes", "Quotes", "Pulse", "Fee Context", "MCP Queue"]
_done  = sum([
    st.session_state["rp_df_raw"]   is not None,
    st.session_state["rp_df_clean"] is not None,
    st.session_state["rp_cluster"]  is not None,
    st.session_state["rp_quotes"]   is not None,
    st.session_state["rp_pulse"]    is not None,
    st.session_state["rp_fee"]      is not None,
    st.session_state.get("pulse_generated", False),
])
st.progress(_done / len(_steps), text=f"Pipeline progress: {_done}/{len(_steps)} steps complete")
st.markdown("---")


# ════════════════════════════════════════════════════════════════════════════
# STEP 1 — Upload & Preview
# ════════════════════════════════════════════════════════════════════════════
st.markdown('<p class="step-head">Step 1 — Upload Reviews CSV</p>', unsafe_allow_html=True)
st.caption("Required columns: `review_id`, `review_text`, `rating` · Optional: `date`, `source`")

uploaded = st.file_uploader("Upload reviews CSV", type="csv", label_visibility="collapsed")

if uploaded:
    try:
        df = pd.read_csv(uploaded)
        missing_cols = {"review_id", "review_text", "rating"} - set(df.columns)
        if missing_cols:
            st.error(f"❌ Missing columns: {', '.join(missing_cols)}")
        else:
            st.session_state["rp_df_raw"] = df

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Reviews", len(df))
            c2.metric("Avg Rating", f"{df['rating'].mean():.1f} / 5")
            c3.metric("Low (≤ 2 stars)", int((df["rating"] <= 2).sum()))
            c4.metric("High (≥ 4 stars)", int((df["rating"] >= 4).sum()))

            with st.expander("📋 Preview (first 5 rows)", expanded=True):
                st.dataframe(df.head(), use_container_width=True)

            with st.expander("📊 Rating distribution"):
                st.bar_chart(df["rating"].value_counts().sort_index())

    except Exception as exc:
        st.error(f"Error reading CSV: {exc}")


# ════════════════════════════════════════════════════════════════════════════
# STEP 2 — PII Scrubbing
# ════════════════════════════════════════════════════════════════════════════
if st.session_state["rp_df_raw"] is not None:
    st.markdown("---")
    st.markdown('<p class="step-head">Step 2 — PII Scrubbing</p>', unsafe_allow_html=True)
    st.caption(
        "Pass 1: contextual patterns (\"my phone is...\") · "
        "Pass 2: standalone regex (bare numbers, emails, PAN, Aadhaar) · "
        "Pass 3: spaCy NER (PERSON names, if available)"
    )

    if st.button("🔍 Run PII Scrub", type="primary"):
        from phase3_review_pillar_b.pii_scrubber import scrub, scrub_pii

        df_raw = st.session_state["rp_df_raw"]
        rows = []
        prog = st.progress(0, text="Scrubbing…")
        for i, (_, row) in enumerate(df_raw.iterrows()):
            original = str(row["review_text"])
            detail   = scrub_pii(original)
            clean, _ = scrub(original)
            rows.append({
                "review_id":   str(row["review_id"]),
                "rating":      row["rating"],
                "review_text": clean,
                "original":    original,
                "pii_found":   detail.pii_found,
                "pii_cats":    ", ".join(detail.categories) if detail.categories else "—",
                "date":        str(row.get("date", "")),
            })
            prog.progress((i + 1) / len(df_raw), text=f"Scrubbed {i+1}/{len(df_raw)} reviews")

        st.session_state["rp_df_clean"] = rows
        prog.empty()

    if st.session_state["rp_df_clean"] is not None:
        rows = st.session_state["rp_df_clean"]
        pii_rows = [r for r in rows if r["pii_found"]]

        c1, c2, c3 = st.columns(3)
        c1.metric("Reviews Processed", len(rows))
        c2.metric("PII Detected In", len(pii_rows))
        c3.metric("Detection Rate", f"{int(len(pii_rows)/len(rows)*100)}%")

        display = pd.DataFrame([{
            "ID":            r["review_id"],
            "Rating":        r["rating"],
            "Cleaned Review": r["review_text"],
            "PII":           "⚠ Yes" if r["pii_found"] else "✅ Clean",
            "Categories":    r["pii_cats"],
        } for r in rows])
        st.dataframe(display, use_container_width=True, height=230)

        if pii_rows:
            st.warning(
                f"⚠ PII found and redacted in {len(pii_rows)} review(s). "
                "All downstream steps use the cleaned text."
            )
        else:
            st.success("✅ No PII detected. Reviews are clean.")


# ════════════════════════════════════════════════════════════════════════════
# STEP 3 — Theme Analysis
# ════════════════════════════════════════════════════════════════════════════
if st.session_state["rp_df_clean"] is not None:
    st.markdown("---")
    st.markdown('<p class="step-head">Step 3 — Theme Analysis</p>', unsafe_allow_html=True)

    n = len(st.session_state["rp_df_clean"])
    if n > 15:
        st.caption(f"2-pass clustering: {n} reviews → split in two halves → synthesize with Claude")
    else:
        st.caption(f"Single-pass clustering: {n} reviews → one Claude call")

    if st.button("🧠 Run Theme Analysis", type="primary"):
        from phase3_review_pillar_b.theme_clusterer import cluster
        with st.spinner("Analysing themes with Claude…"):
            result = cluster(st.session_state["rp_df_clean"])
        st.session_state["rp_cluster"] = result

    if st.session_state["rp_cluster"] is not None:
        cr     = st.session_state["rp_cluster"]
        themes = cr.get("themes", [])
        top_3  = cr.get("top_3", [])
        ideas  = cr.get("action_ideas", [])

        st.markdown("**All Themes Detected**")
        chips = "".join(
            f'<span class="theme-chip {"theme-top" if t in top_3 else "theme-rest"}">'
            f'{"⭐ " if t in top_3 else ""}{t}</span>'
            for t in themes
        )
        st.markdown(chips, unsafe_allow_html=True)

        col_left, col_right = st.columns(2)
        with col_left:
            st.markdown("**Top 3 Themes**")
            for i, t in enumerate(top_3, 1):
                st.markdown(f"**{i}.** {t}")

        with col_right:
            if ideas:
                st.markdown("**Action Ideas**")
                for idea in ideas:
                    st.markdown(
                        f'<div class="action-card">→ {idea}</div>',
                        unsafe_allow_html=True,
                    )


# ════════════════════════════════════════════════════════════════════════════
# STEP 4 — Representative Quotes
# ════════════════════════════════════════════════════════════════════════════
if st.session_state["rp_cluster"] is not None:
    st.markdown("---")
    st.markdown('<p class="step-head">Step 4 — Representative Quotes</p>', unsafe_allow_html=True)
    st.caption("One quote per top theme — highest-rated review, trimmed to 150 chars, PII-clean")

    if st.button("💬 Extract Quotes", type="primary"):
        from phase3_review_pillar_b.quote_extractor import extract

        cr      = st.session_state["rp_cluster"]
        top_3   = cr.get("top_3", [])
        themes  = cr.get("themes", [])
        all_ids = [r["review_id"] for r in st.session_state["rp_df_clean"]]
        # quote_extractor needs theme dicts with review_ids
        theme_dicts = [{"theme": t, "review_ids": all_ids} for t in themes]
        quotes = extract(st.session_state["rp_df_clean"], theme_dicts, top_3)
        st.session_state["rp_quotes"] = quotes

    if st.session_state["rp_quotes"] is not None:
        quotes = st.session_state["rp_quotes"]
        cols   = st.columns(max(len(quotes), 1))
        for col, q in zip(cols, quotes):
            with col:
                stars = "⭐" * max(1, int(float(q.get("rating", 3))))
                st.markdown(
                    f'<div class="quote-card">'
                    f'<div class="quote-theme">{q.get("theme","")}</div>'
                    f'<div class="quote-text">"{q.get("quote","")}"</div>'
                    f'<div class="quote-stars">{stars} &nbsp;{q.get("rating","")}/5</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ════════════════════════════════════════════════════════════════════════════
# STEP 5 — Weekly Pulse Note
# ════════════════════════════════════════════════════════════════════════════
if st.session_state["rp_quotes"] is not None:
    st.markdown("---")
    st.markdown('<p class="step-head">Step 5 — Weekly Pulse Note</p>', unsafe_allow_html=True)
    st.caption("Max 250 words · Neutral tone · Ends with exactly 3 numbered action items")

    if st.button("✍ Write Pulse Note", type="primary"):
        from phase3_review_pillar_b.pulse_writer import write
        cr     = st.session_state["rp_cluster"]
        top_3  = cr.get("top_3", [])
        quotes = st.session_state["rp_quotes"]
        with st.spinner("Writing pulse note with Claude…"):
            pulse = write(top_3, quotes)
        st.session_state["rp_pulse"] = pulse
        st.session_state["weekly_pulse"] = pulse
        st.session_state["top_theme"]    = top_3[0] if top_3 else "General Feedback"
        st.session_state["top_3_themes"] = top_3

    if st.session_state["rp_pulse"] is not None:
        pulse = st.session_state["rp_pulse"]
        wc    = len(pulse.split())
        actions_found = len(re.findall(r"^\d+\.", pulse, re.MULTILINE))

        col_text, col_meta = st.columns([3, 1])
        with col_text:
            st.text_area("Pulse Note", pulse, height=260, disabled=True, label_visibility="collapsed")
        with col_meta:
            st.metric("Word Count", wc, delta=f"{250 - wc} remaining")
            st.progress(min(wc / 250, 1.0))
            st.metric("Action Items Found", actions_found)
            st.download_button(
                "⬇ Download .txt",
                data=pulse,
                file_name="weekly_pulse.txt",
                mime="text/plain",
            )


# ════════════════════════════════════════════════════════════════════════════
# STEP 6 — Fee Context  (Phase 2 corpus-powered)
# ════════════════════════════════════════════════════════════════════════════
if st.session_state["rp_pulse"] is not None:
    st.markdown("---")
    st.markdown('<p class="step-head">Step 6 — Fee Context</p>', unsafe_allow_html=True)
    top_theme_now = st.session_state.get("top_theme", "General Feedback")
    st.caption(
        f"RAG retrieval from Phase-2 Fee corpus · Top theme: **{top_theme_now}** · "
        "Generates 6 bullet-point explanation"
    )

    if st.button("💰 Fetch Fee Context", type="primary"):
        from phase3_review_pillar_b.fee_explainer import explain
        with st.spinner(f"Retrieving fee context for '{top_theme_now}'..."):
            fee = explain(top_theme_now, st.session_state)
        st.session_state["rp_fee"]           = fee
        st.session_state["fee_bullets"]      = fee["bullets"]
        st.session_state["fee_sources"]      = fee["sources"]
        st.session_state["pulse_generated"]  = True

    if st.session_state["rp_fee"] is not None:
        fee = st.session_state["rp_fee"]

        col_bullets, col_meta = st.columns([2, 1])
        with col_bullets:
            scenario_label = fee.get("scenario", "").replace("_", " ").title()
            st.markdown(f"**Fee Scenario:** `{scenario_label}`")
            for b in fee.get("bullets", []):
                st.markdown(b if b.startswith("•") else f"• {b}")

        with col_meta:
            st.markdown("**Sources**")
            for src in fee.get("sources", []):
                label = src.split("/")[2] if src.startswith("http") else src
                st.markdown(f"🔗 [{label}]({src})")
            st.caption(f"Last checked: {fee.get('checked','—')}")

            if _fee_count > 0:
                st.success(f"✅ RAG ({_fee_count} chunks)")
            else:
                st.warning("⚠ Fallback (no corpus)")


# ════════════════════════════════════════════════════════════════════════════
# STEP 7 — Queue MCP Actions
# ════════════════════════════════════════════════════════════════════════════
if st.session_state["rp_fee"] is not None:
    st.markdown("---")
    st.markdown('<p class="step-head">Step 7 — Queue MCP Actions</p>', unsafe_allow_html=True)
    st.caption(
        "Enqueues **notes_append** and **email_draft** actions. "
        "Both require human approval in the Approval Center before executing."
    )

    if st.button("📤 Queue for Approval", type="primary"):
        from phase7_pillar_c_hitl.mcp_client import enqueue_action
        from datetime import date

        pulse = st.session_state["rp_pulse"]
        fee   = st.session_state["rp_fee"]
        top_3 = st.session_state.get("top_3_themes", [])

        enqueue_action(
            st.session_state,
            type="notes_append",
            payload={
                "doc_title": "Weekly Pulse Notes",
                "entry": {
                    "date":         str(date.today()),
                    "weekly_pulse": pulse[:500],
                    "top_themes":   top_3,
                    "fee_scenario": fee.get("scenario", ""),
                },
            },
            source="review_pulse_ui",
        )
        enqueue_action(
            st.session_state,
            type="email_draft",
            payload={
                "subject": f"Weekly Pulse + Fee Explainer — {date.today()}",
                "body": (
                    f"Weekly Pulse:\n{pulse}\n\n"
                    f"Fee Context ({fee.get('scenario','').replace('_',' ')}):\n"
                    + "\n".join(fee.get("bullets", []))
                    + f"\n\nSources: {', '.join(fee.get('sources', []))}"
                    + f"\n\nLast checked: {fee.get('checked','')}"
                ),
            },
            source="review_pulse_ui",
        )

        # Persist to disk so main app Approval Center picks it up
        (ROOT / "data" / "mcp_state.json").write_text(
            json.dumps(st.session_state["mcp_queue"], indent=2)
        )
        st.success("✅ 2 actions queued: notes_append + email_draft")

    # Current pending queue display
    pending = [a for a in st.session_state.get("mcp_queue", []) if a.get("status") == "pending"]
    if pending:
        st.markdown(f"**{len(pending)} pending action(s):**")
        for action in pending[-6:]:
            icon  = "📝" if "notes" in action.get("type", "") else "📧"
            src   = action.get("source", "")
            atype = action.get("type", "unknown")
            st.markdown(
                f'<div class="mcp-row">'
                f'<span>{icon} <code>{atype}</code> '
                f'<span style="color:#64748b;font-size:0.8rem">· {src}</span></span>'
                f'<span class="badge-pending">pending</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        st.info("👉 Open the **main app → Approval Center** tab to review and approve")

    # ── Pipeline complete summary ────────────────────────────────────────────
    st.markdown("---")
    n_reviews = len(st.session_state["rp_df_clean"] or [])
    n_themes  = len((st.session_state["rp_cluster"] or {}).get("top_3", []))
    n_quotes  = len(st.session_state["rp_quotes"] or [])
    n_pending = len([a for a in st.session_state.get("mcp_queue", []) if a.get("status") == "pending"])

    st.success(
        f"🎉 **Pipeline complete** — "
        f"{n_reviews} reviews → {n_themes} top themes → "
        f"{n_quotes} quotes → pulse written → fee context → "
        f"{n_pending} action(s) queued"
    )
    st.markdown(
        "The weekly pulse is now stored in session state. "
        "The **Voice Agent** in the main app can book an advisor call "
        "using this week's top theme."
    )

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-footer">
  <div class="app-footer-left">
    Built by <span>Dalal Street Advisors</span> · AI Bootcamp Capstone &nbsp;|&nbsp;
    Powered by <span>Claude Sonnet</span> + <span>ChromaDB</span>
  </div>
  <div class="app-footer-right">
    Facts only · No investment advice · SBI Mutual Fund data
  </div>
</div>
""", unsafe_allow_html=True)
