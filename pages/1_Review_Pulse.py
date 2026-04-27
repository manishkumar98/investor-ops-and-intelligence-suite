"""Weekly Review Pulse — embeds the baked dashboard.html.
No CSV upload required. Data is refreshed by running the pipeline.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from config import load_env
from session_init import init_session_state

try:
    load_env()
    _env_ok = True
    _env_err = ""
except EnvironmentError as exc:
    _env_ok = False
    _env_err = str(exc)

st.set_page_config(
    page_title="Review Pulse — Weekly Dashboard",
    page_icon="📊",
    layout="wide",
)
init_session_state(st.session_state)

DATA = ROOT / "data"


def _load_json(name: str) -> dict | None:
    path = DATA / name
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except Exception:
        return None


def _fmt_ts(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return iso


# ── Minimal page CSS ──────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; }
  .stApp { background-color: #0A0C14; color: #F5F0E8; }
  section[data-testid="stSidebar"] { background-color: #10131F !important; border-right: 1px solid #1E2235; }
  section[data-testid="stSidebar"] * { color: #F5F0E8 !important; }
  .stButton > button {
    background: linear-gradient(135deg, #C9A84C, #A8863C) !important;
    color: #0A0C14 !important; border: none !important;
    border-radius: 6px !important; font-weight: 600 !important;
  }
  h1, h2, h3 { color: #F5F0E8 !important; }
  div[data-testid="stMetricValue"] { color: #C9A84C !important; font-weight: 700; }
  #MainMenu, footer, header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Review Pulse")
    st.caption("Weekly INDMoney Review Pipeline")
    st.markdown("---")

    if _env_ok:
        st.success("✅ API keys loaded")
    else:
        st.error(f"❌ {_env_err}")

    _state = _load_json("system_state.json") or {}
    _last_run = _state.get("last_pipeline_run")
    if _last_run:
        st.info(f"**Last run:** {_fmt_ts(_last_run)}\n\n**Reviews:** {_state.get('last_review_count', '—')}")
    else:
        st.caption("Pipeline not yet run.")

    st.markdown("---")
    if st.session_state.get("pulse_generated"):
        st.markdown("**Session State**")
        st.info(f"Top theme: **{st.session_state.get('top_theme', '—')}**")
        pending = sum(1 for a in st.session_state.get("mcp_queue", []) if a.get("status") == "pending")
        st.metric("MCP Actions Queued", pending)


# ── Top bar: title + Run Pipeline button ─────────────────────────────────────
col_title, col_btn = st.columns([5, 1])
with col_title:
    st.title("📊 Weekly Review Pulse")
with col_btn:
    st.markdown("<br>", unsafe_allow_html=True)
    run_clicked = st.button("▶ Run Pipeline", type="primary", use_container_width=True)

# ── Run pipeline ──────────────────────────────────────────────────────────────
if run_clicked:
    if not _env_ok:
        st.error(f"Cannot run: {_env_err}")
    else:
        log_area = st.empty()
        logs: list[str] = []

        def _cb(msg: str) -> None:
            logs.append(msg)
            log_area.info("\n\n".join(logs))

        with st.spinner("Running weekly review pipeline…"):
            try:
                from run_review_pipeline import run_pipeline
                result = run_pipeline(status_cb=_cb)
                pulse = result["pulse"]
                top_3 = pulse.get("top_3_themes", [])
                st.session_state["weekly_pulse"]    = pulse.get("weekly_note", "")
                st.session_state["top_theme"]       = top_3[0] if top_3 else "General Feedback"
                st.session_state["top_3_themes"]    = top_3
                st.session_state["fee_bullets"]     = result["fee"].get("bullets", [])
                st.session_state["fee_sources"]     = result["fee"].get("sources", [])
                st.session_state["pulse_generated"] = True
                st.session_state["analytics_data"]  = result["analytics"]
                log_area.empty()
                st.success(f"✅ Done — {pulse.get('review_count', '?')} reviews processed. Dashboard updated.")
                st.rerun()
            except Exception as exc:
                log_area.empty()
                st.error(f"Pipeline failed: {exc}")

st.markdown("---")

# ── Dashboard embed ───────────────────────────────────────────────────────────
dashboard_file = DATA / "dashboard.html"

if not dashboard_file.exists():
    st.markdown("""
    <div style="text-align:center;padding:80px 20px;color:#5A5450;">
      <div style="font-size:3rem">📭</div>
      <h3 style="color:#9A9080;font-size:1.4rem;">No dashboard data yet</h3>
      <p>Click <strong>▶ Run Pipeline</strong> above to scrape this week's INDMoney reviews,
      analyse themes, generate the pulse, and build the fee context.</p>
      <p style="font-size:0.82rem;color:#3A3830;margin-top:20px;">
        Or run from the terminal:<br>
        <code style="background:#1e293b;padding:4px 8px;border-radius:4px;">
          python scripts/run_review_pipeline.py
        </code>
      </p>
    </div>
    """, unsafe_allow_html=True)
else:
    # Also push latest data to session state for the voice agent
    pulse_data = _load_json("pulse_latest.json")
    if pulse_data and not st.session_state.get("pulse_generated"):
        top_3 = pulse_data.get("top_3_themes", [])
        fee_data = _load_json("fee_latest.json") or {}
        st.session_state["weekly_pulse"]    = pulse_data.get("weekly_note", "")
        st.session_state["top_theme"]       = top_3[0] if top_3 else "General Feedback"
        st.session_state["top_3_themes"]    = top_3
        st.session_state["fee_bullets"]     = fee_data.get("bullets", [])
        st.session_state["fee_sources"]     = fee_data.get("sources", [])
        st.session_state["pulse_generated"] = True
        st.session_state["analytics_data"]  = _load_json("analytics_latest.json")

    html_content = dashboard_file.read_text(encoding="utf-8")
    components.html(html_content, height=950, scrolling=True)
