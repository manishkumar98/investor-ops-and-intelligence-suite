"""Investor Ops & Intelligence Suite — main Streamlit entry point.

Run: streamlit run app.py
"""
import json
import re
from pathlib import Path

import streamlit as st

from config import load_env, MCP_MODE
from session_init import init_session_state
from phase5_pillar_a_faq.faq_engine import query as faq_query
from phase2_corpus_pillar_a.ingest import get_collection
from phase3_review_pillar_b.pipeline_orchestrator import run_pipeline
from phase4_voice_pillar_b.voice_agent import VoiceAgent
from phase7_pillar_c_hitl.mcp_client import MCPClient
from phase7_pillar_c_hitl.hitl_panel import render as render_hitl

_DOMAIN_LABELS = {
    "sbimf.com":      "SBI Mutual Fund",
    "amfiindia.com":  "AMFI India",
    "sebi.gov.in":    "SEBI",
    "indmoney.com":   "INDMoney",
}


_ACRONYMS = {"Sbi", "Elss", "Sip", "Nav", "Kyc", "Amc", "Amfi", "Sebi", "Nri"}


def _source_label(url: str) -> str:
    """Return a human-readable label for a source URL."""
    domain_label = next((v for k, v in _DOMAIN_LABELS.items() if k in url), None)
    try:
        path = url.split("//", 1)[1].split("/", 1)[1]
        slug = path.rstrip("/").split("/")[-1]
        slug = re.sub(r"\.[a-z]{2,5}$", "", slug)              # strip .html .aspx etc.
        slug = re.sub(r"-\d+$", "", slug)                       # strip trailing ID -2754
        slug = re.sub(r"\(.*?\)", "", slug).strip()             # strip parentheses
        slug = re.sub(r"[_\-]+", " ", slug)
        words = [w.upper() if w.title() in _ACRONYMS else w.title() for w in slug.split()]
        name = " ".join(words)
        return f"{name} — {domain_label}" if domain_label else name
    except Exception:
        return domain_label or url


# ── 1. Bootstrap ──────────────────────────────────────────────────────────────
load_env()
st.set_page_config(
    page_title="Investor Ops & Intelligence Suite by Dalal Street Advisors",
    page_icon="📊",
    layout="wide",
)
init_session_state(st.session_state)

# ── Theme CSS (M3-grade Dezerv-inspired: charcoal + warm gold) ───────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── CSS Variables ── */
:root {
  --bg-base:   #0A0C14;
  --bg-card:   #10131F;
  --bg-glass:  rgba(255,255,255,0.04);
  --border:    rgba(255,255,255,0.08);
  --gold-1:    #C9A84C;
  --gold-2:    #E8C96D;
  --gold-glow: rgba(201,168,76,0.18);
  --gold-dim:  rgba(201,168,76,0.55);
  --text-1:    #F5F0E8;
  --text-2:    #9A9080;
  --text-3:    #6B6358;
  --green:     #22C55E;
  --red:       #EF4444;
}

/* ── Reset Streamlit chrome ── */
#MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stHeader"] { background: transparent !important; height: 0 !important; }

/* ── Full-width block container ── */
.block-container {
  padding: 0 !important;
  max-width: 100% !important;
  margin: 0 !important;
}

/* ── Base ── */
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
section.main > div {
  background: var(--bg-base) !important;
  color: var(--text-1) !important;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* ── Ambient glow ── */
.stApp::before {
  content: '';
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background:
    radial-gradient(ellipse 80% 40% at 50% -5%, rgba(201,168,76,0.07) 0%, transparent 70%),
    radial-gradient(ellipse 40% 30% at 85% 100%, rgba(201,168,76,0.04) 0%, transparent 60%);
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
  background-color: var(--bg-card) !important;
  border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] * { color: var(--text-1) !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background-color: var(--bg-card);
  border-bottom: 1px solid var(--border);
  gap: 0; padding: 0 48px;
}
.stTabs [data-baseweb="tab"] {
  color: var(--text-2) !important;
  background-color: transparent !important;
  border: none !important;
  padding: 14px 24px;
  font-weight: 500; font-size: 0.875rem; letter-spacing: 0.02em;
}
.stTabs [aria-selected="true"] {
  color: var(--gold-2) !important;
  border-bottom: 2px solid var(--gold-1) !important;
  background-color: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover {
  color: var(--gold-2) !important;
  background-color: rgba(201,168,76,0.04) !important;
}

/* ── Metrics ── */
div[data-testid="stMetric"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important; padding: 16px !important;
}
div[data-testid="stMetricValue"] { color: var(--gold-2) !important; font-weight: 700; }

/* ── Buttons ── */
.stButton > button {
  background: linear-gradient(135deg, var(--gold-1), #A8873A) !important;
  color: #0A0C14 !important; border: none !important;
  border-radius: 100px !important; font-weight: 700 !important;
  font-size: 0.875rem !important; padding: 10px 24px !important;
  letter-spacing: 0.02em !important;
  box-shadow: 0 4px 20px rgba(201,168,76,0.25) !important;
  transition: all 0.2s ease !important;
}
.stButton > button:hover {
  background: linear-gradient(135deg, var(--gold-2), var(--gold-1)) !important;
  box-shadow: 0 6px 28px rgba(201,168,76,0.40) !important;
  transform: translateY(-1px) !important;
}

/* ── Chat ── */
[data-testid="stChatMessage"] {
  background: var(--bg-card); border: 1px solid var(--border);
  border-radius: 12px; margin-bottom: 8px;
}
[data-testid="stChatInput"] textarea {
  background: var(--bg-card) !important; border: 1px solid var(--border) !important;
  color: var(--text-1) !important; border-radius: 12px !important;
}
[data-testid="stChatInput"] textarea:focus {
  border-color: var(--gold-1) !important;
  box-shadow: 0 0 0 2px var(--gold-glow) !important;
}

/* ── Text inputs ── */
.stTextInput > div > div > input {
  background: var(--bg-card) !important; border: 1px solid var(--border) !important;
  color: var(--text-1) !important; border-radius: 8px !important;
}
.stTextInput > div > div > input:focus {
  border-color: var(--gold-1) !important;
  box-shadow: 0 0 0 2px var(--gold-glow) !important;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
  background: var(--bg-card) !important; border: 1px dashed var(--border) !important;
  border-radius: 12px !important;
}
[data-testid="stFileUploader"]:hover { border-color: var(--gold-1) !important; }

/* ── Alerts ── */
.stAlert { border-radius: 10px !important; }
[data-testid="stNotificationContentInfo"],
[data-testid="stWarning"], [data-testid="stInfo"] {
  background: rgba(201,168,76,0.06) !important;
  border: 1px solid rgba(201,168,76,0.20) !important;
  border-radius: 10px !important;
}

/* ── Misc ── */
.stCode { background: #0D0F1A !important; border: 1px solid var(--border) !important; border-radius: 8px !important; }
h1,h2,h3,h4 { color: var(--text-1) !important; font-weight: 700 !important; }
hr { border-color: var(--border) !important; margin: 24px 0 !important; }
[data-testid="stMarkdownContainer"] p { color: var(--text-2) !important; }
.stSpinner > div { color: var(--gold-dim) !important; }

/* ── Tab content padding (restores breathing room removed by block-container reset) ── */
.stTabs [data-testid="stTabsContent"] {
  padding: 32px 48px 40px !important;
  max-width: 1200px !important;
  margin: 0 auto !important;
}
@media(max-width:768px) {
  .stTabs [data-testid="stTabsContent"] { padding: 24px 20px 32px !important; }
}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {
  padding: 16px 20px !important;
  border-radius: 16px !important;
  margin-bottom: 12px !important;
}
/* User bubble — subtle gold tint */
[data-testid="stChatMessage"][data-testid*="user"],
.stChatMessage:has([data-testid="chatAvatarIcon-user"]) {
  background: rgba(201,168,76,0.06) !important;
  border: 1px solid rgba(201,168,76,0.18) !important;
}
/* Assistant bubble — card style */
[data-testid="stChatMessage"][data-testid*="assistant"],
.stChatMessage:has([data-testid="chatAvatarIcon-assistant"]) {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
}
/* Text inside chat messages */
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
  color: var(--text-1) !important;
  line-height: 1.7 !important;
  font-size: 0.93rem !important;
}
/* Chat avatar icons */
[data-testid="chatAvatarIcon-user"] {
  background: rgba(201,168,76,0.15) !important;
  border: 1px solid rgba(201,168,76,0.30) !important;
}
[data-testid="chatAvatarIcon-assistant"] {
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid var(--border) !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] {
  background: var(--bg-card) !important;
  border: 1px solid var(--border) !important;
  border-radius: 16px !important;
  padding: 4px 8px !important;
  transition: border-color 0.2s !important;
}
[data-testid="stChatInput"]:focus-within {
  border-color: var(--gold-1) !important;
  box-shadow: 0 0 0 3px rgba(201,168,76,0.12) !important;
}
[data-testid="stChatInput"] textarea {
  background: transparent !important;
  border: none !important;
  color: var(--text-1) !important;
  font-size: 0.93rem !important;
  padding: 12px 16px !important;
  border-radius: 12px !important;
  box-shadow: none !important;
}
[data-testid="stChatInput"] textarea::placeholder {
  color: var(--text-3) !important;
}
/* Send button inside chat input */
[data-testid="stChatInput"] button {
  background: linear-gradient(135deg, var(--gold-1), #A8873A) !important;
  border: none !important;
  border-radius: 10px !important;
  color: #0A0C14 !important;
  margin: 4px !important;
}

/* ── Fund cards ── */
.fund-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:12px; margin:16px 0 24px; }
.fund-card { background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:18px; transition:all 0.25s; }
.fund-card:hover { border-color:rgba(201,168,76,0.4); background:rgba(201,168,76,0.03); transform:translateY(-2px); box-shadow:0 8px 32px rgba(0,0,0,0.3); }
.fund-name { color:var(--gold-1); font-weight:600; font-size:0.92rem; margin-bottom:6px; }
.fund-meta { color:var(--text-2); font-size:0.8rem; display:flex; gap:10px; margin-bottom:8px; flex-wrap:wrap; }
.fund-tag { background:rgba(255,255,255,0.04); border:1px solid var(--border); border-radius:4px; padding:2px 8px; font-size:0.72rem; color:var(--text-2); }
.fund-coverage { color:var(--text-3); font-size:0.78rem; margin-top:6px; line-height:1.4; }

/* ── NAV Ticker ── */
.ticker-wrap {
  width:100%; background:#0D0F1A; border-bottom:1px solid var(--border);
  overflow:hidden; padding:7px 0; position:sticky; top:0; z-index:1000;
}
.ticker-track { display:flex; width:max-content; animation:ticker-scroll 38s linear infinite; }
.ticker-track:hover { animation-play-state:paused; }
@keyframes ticker-scroll { 0%{transform:translateX(0);} 100%{transform:translateX(-50%);} }
.ticker-item { display:inline-flex; align-items:center; gap:6px; padding:0 28px; white-space:nowrap; font-size:0.78rem; border-right:1px solid var(--border); }
.ticker-symbol { color:var(--gold-1); font-weight:600; letter-spacing:0.04em; }
.ticker-nav    { color:var(--text-2); font-size:0.73rem; }
.ticker-up     { color:#22C55E; font-weight:600; }
.ticker-down   { color:#EF4444; font-weight:600; }
.ticker-neutral{ color:var(--text-2); font-weight:600; }

/* ── Site Header ── */
.dsa-header {
  position:sticky; top:0; z-index:100;
  background:rgba(10,12,20,0.95); backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border);
  display:flex; align-items:center; justify-content:space-between;
  padding:0 48px; height:64px; width:100%; box-sizing:border-box;
}
.dsa-logo-wrap { display:flex; align-items:center; gap:12px; }
.dsa-logo-icon {
  width:38px; height:38px; border-radius:10px;
  background:linear-gradient(135deg,var(--gold-1),#8a6820);
  display:flex; align-items:center; justify-content:center;
  font-size:20px; flex-shrink:0;
}
.dsa-logo-text { font-size:1.05rem; font-weight:800; color:var(--text-1); letter-spacing:-0.02em; }
.dsa-logo-sub  { font-size:0.65rem; color:var(--gold-dim); letter-spacing:0.08em; text-transform:uppercase; font-weight:500; }
.dsa-nav { display:flex; gap:32px; align-items:center; }
.dsa-nav a { font-size:0.85rem; font-weight:500; color:var(--text-2); text-decoration:none; letter-spacing:0.01em; transition:color 0.2s; }
.dsa-nav a:hover { color:var(--gold-2); }
.dsa-header-badge {
  background:rgba(201,168,76,0.10); border:1px solid rgba(201,168,76,0.35);
  color:var(--gold-2); border-radius:100px; padding:6px 16px;
  font-size:0.72rem; font-weight:600; letter-spacing:0.06em; text-transform:uppercase;
}
@media(max-width:768px){ .dsa-nav{display:none;} .dsa-header{padding:0 20px;} }

/* ── Site Footer ── */
.dsa-footer {
  background:#07080F; border-top:1px solid var(--border);
  padding:48px 48px 32px; margin-top:0;
}
.dsa-footer-grid {
  display:grid; grid-template-columns:2fr 1fr 1fr 1fr;
  gap:40px; max-width:1200px; margin:0 auto 40px;
}
.dsa-footer-brand p { font-size:0.85rem; color:var(--text-3); line-height:1.7; margin-top:12px; max-width:280px; }
.dsa-footer-col h4 { font-size:0.78rem; font-weight:700; color:var(--gold-dim); letter-spacing:0.1em; text-transform:uppercase; margin-bottom:16px; }
.dsa-footer-col a  { display:block; font-size:0.84rem; color:var(--text-3); text-decoration:none; margin-bottom:10px; transition:color 0.2s; }
.dsa-footer-col a:hover { color:var(--text-1); }
.dsa-footer-bottom {
  border-top:1px solid var(--border); padding-top:24px;
  display:flex; justify-content:space-between; align-items:flex-start;
  max-width:1200px; margin:0 auto; flex-wrap:wrap; gap:12px;
}
.dsa-footer-copy { font-size:0.78rem; color:var(--text-3); line-height:1.6; max-width:640px; }
.dsa-footer-right { font-size:0.75rem; color:var(--text-3); text-align:right; }
.dsa-footer-right span { color:var(--gold-dim); font-weight:600; }
@media(max-width:768px){
  .dsa-footer-grid{grid-template-columns:1fr 1fr;}
  .dsa-footer{padding:40px 20px 24px;}
  .dsa-footer-bottom{flex-direction:column;}
}
</style>
""", unsafe_allow_html=True)

# ── NAV Ticker ───────────────────────────────────────────────────────────────
def _build_ticker_html() -> str:
    nav_file = Path("data/nav_snapshot.json")
    try:
        data = json.loads(nav_file.read_text())
        funds = data["funds"]
        as_of = data.get("as_of", "")
    except Exception:
        return ""

    items_html = ""
    for f in funds:
        nav   = f["nav"]
        prev  = f["prev_nav"]
        pct   = (nav - prev) / prev * 100 if prev else 0
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

    # Duplicate items so the scroll loops seamlessly
    track = f'<div class="ticker-track">{items_html}{items_html}</div>'
    as_of_label = f'<span style="font-size:0.65rem;color:#3A3830;padding-left:8px;">NAV as of {as_of}</span>' if as_of else ""
    return f'<div class="ticker-wrap">{track}{as_of_label}</div>'


_ticker = _build_ticker_html()
if _ticker:
    st.markdown(_ticker, unsafe_allow_html=True)

# ── App Header ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dsa-header">
  <div class="dsa-logo-wrap">
    <div class="dsa-logo-icon">📊</div>
    <div>
      <div class="dsa-logo-text">Investor Ops & Intelligence Suite by Dalal Street Advisors</div>
      <div class="dsa-logo-sub">Investor Ops &amp; Intelligence Platform</div>
    </div>
  </div>
  <nav class="dsa-nav">
    <a href="#">Smart FAQ</a>
    <a href="#">Review Pulse</a>
    <a href="#">Approvals</a>
  </nav>
  <div class="dsa-header-badge">⚡ AI-Powered · Facts Only</div>
</div>
""", unsafe_allow_html=True)

# Reload MCP queue from disk if session is fresh (handles page reloads)
if not st.session_state["mcp_queue"]:
    state_file = Path("data/mcp_state.json")
    if state_file.exists():
        try:
            st.session_state["mcp_queue"] = json.loads(state_file.read_text())
        except json.JSONDecodeError:
            pass

# ── 2. Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📊 Investor Ops & Intelligence Suite by Dalal Street Advisors")
    st.caption("Investor Ops & Intelligence Suite — Demo")
    st.markdown("---")

    # Corpus status
    try:
        faq_count = get_collection("mf_faq_corpus").count()
        fee_count = get_collection("fee_corpus").count()
        st.success(f"✅ FAQ corpus: {faq_count} chunks")
        st.success(f"✅ Fee corpus: {fee_count} chunks")
    except Exception:
        st.error("❌ Corpus not loaded — run:")
        st.code("python scripts/ingest_corpus.py")

    st.markdown("---")

    # Pulse status
    if st.session_state["pulse_generated"]:
        st.info(f"📊 Top theme: **{st.session_state['top_theme']}**")
    else:
        st.warning("📊 No pulse generated yet")

    # MCP pending count
    pending = sum(1 for a in st.session_state["mcp_queue"] if a["status"] == "pending")
    st.metric("Pending Approvals", pending)

    st.markdown("---")
    if st.button("🔄 Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        Path("data/mcp_state.json").unlink(missing_ok=True)
        st.rerun()

# ── 3. Tabs ───────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📚 Smart-Sync FAQ",
    "📊 Review Pulse & Voice",
    "✅ Approval Center",
])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Smart-Sync FAQ
# ══════════════════════════════════════════════════════════════════════════════
_SUPPORTED_FUNDS = [
    {
        "name": "SBI Large Cap Fund (Bluechip)",
        "category": "Large Cap Equity",
        "risk": "Moderate",
        "coverage": "Exit load, expense ratio, SIP minimums, AUM, fund manager",
    },
    {
        "name": "SBI Flexicap Fund",
        "category": "Flexicap Equity",
        "risk": "Moderate–High",
        "coverage": "Investment mandate, exit load, expense ratio, NAV history",
    },
    {
        "name": "SBI ELSS Tax Saver Fund",
        "category": "ELSS / Tax Saving",
        "risk": "High",
        "coverage": "Lock-in period, Section 80C benefits, exit load, expense ratio",
    },
    {
        "name": "SBI Small Cap Fund",
        "category": "Small Cap Equity",
        "risk": "Very High",
        "coverage": "Exit load structure, minimum SIP, expense ratio, redemption rules",
    },
    {
        "name": "SBI Midcap Fund",
        "category": "Mid Cap Equity",
        "risk": "High",
        "coverage": "Exit load, expense ratio, SIP amount, benchmark",
    },
    {
        "name": "SBI Focused Equity Fund",
        "category": "Focused Equity",
        "risk": "High",
        "coverage": "Portfolio concentration, exit load, expense ratio",
    },
    {
        "name": "SBI Liquid Fund",
        "category": "Debt / Liquid",
        "risk": "Low",
        "coverage": "Graded exit load, expense ratio, redemption timelines",
    },
    {
        "name": "SBI Contra Fund",
        "category": "Contra Equity",
        "risk": "High",
        "coverage": "Contrarian strategy, exit load, expense ratio",
    },
]

_RISK_COLORS = {
    "Low":          "#28a745",
    "Moderate":     "#C9A84C",
    "Moderate–High":"#fd7e14",
    "High":         "#dc3545",
    "Very High":    "#a71d2a",
}

with tab1:
    st.markdown("### Smart-Sync Mutual Fund FAQ")
    st.caption(
        "Ask factual questions about SBI Mutual Fund schemes and fees. "
        "Facts only — no investment advice."
    )

    with st.expander("📋 Supported Mutual Funds", expanded=False):
        cards_html = '<div class="fund-grid">'
        for f in _SUPPORTED_FUNDS:
            risk_color = _RISK_COLORS.get(f["risk"], "#9A9080")
            cards_html += f"""
            <div class="fund-card">
              <div class="fund-name">{f['name']}</div>
              <div class="fund-meta">
                <span class="fund-tag">{f['category']}</span>
                <span class="fund-tag" style="border-color:{risk_color};color:{risk_color};">
                  {f['risk']} Risk
                </span>
              </div>
              <div class="fund-coverage">📌 {f['coverage']}</div>
            </div>"""
        cards_html += "</div>"
        st.markdown(cards_html, unsafe_allow_html=True)

    if not st.session_state["chat_history"]:
        st.info(
            "**Try these compound questions:**\n"
            "- What is the exit load for SBI ELSS and how is the expense ratio calculated?\n"
            "- Can I redeem SBI Bluechip within 6 months and what fees apply?\n"
            "- What is the minimum SIP for SBI Small Cap and what are the fee components?"
        )

    # Display conversation history
    for entry in st.session_state["chat_history"]:
        with st.chat_message("user"):
            st.write(entry["content"])
        with st.chat_message("assistant"):
            response = entry["response"]
            if response.refused:
                st.warning(f"⚠ {response.refusal_msg}")
            elif response.bullets:
                for b in response.bullets:
                    st.markdown(f"- {b}")
            else:
                st.write(response.prose)
            if response.sources:
                links = " · ".join(f"[{_source_label(src)}]({src})" for src in response.sources)
                st.markdown(f"**Sources :** {links}")
            st.caption(f"Last updated from sources: {response.last_updated}")

    user_question = st.chat_input("Ask a factual question about SBI Mutual Funds...")
    if user_question:
        # Show the question immediately so the user can see it while waiting
        with st.chat_message("user"):
            st.write(user_question)
        with st.chat_message("assistant"):
            with st.spinner("Thinking... this may take a moment ✨"):
                faq_query(user_question, st.session_state)
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Review Pulse & Voice Agent
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Review Pulse & Voice Agent")

    # ── Review Pipeline section ──────────────────────────────────────────────
    st.markdown("#### Weekly Review Pulse")
    uploaded_file = st.file_uploader("Upload reviews CSV", type="csv")

    if uploaded_file and st.button("▶ Run Pipeline"):
        with st.spinner("Processing reviews..."):
            try:
                result = run_pipeline(uploaded_file, st.session_state)
                st.success("Pipeline complete!")

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.subheader("Top Themes")
                    for theme in result["top_3"]:
                        st.markdown(f"- {theme}")
                with col2:
                    st.subheader("User Quotes")
                    for q in result["quotes"]:
                        st.markdown(f"*\"{q['quote']}\"*  — Rating: {q['rating']}/5")
                with col3:
                    st.subheader("Weekly Pulse")
                    st.write(result["pulse"])
                    st.caption(f"Word count: {result['word_count']}")

                if result.get("action_ideas"):
                    st.markdown("#### Action Ideas")
                    for idea in result["action_ideas"]:
                        st.markdown(f"- {idea}")

                st.markdown("#### Fee Context")
                for bullet in result["fee_bullets"]:
                    st.markdown(f"- {bullet}")
                for src in result["fee_sources"]:
                    st.caption(f"Source: {src}")
                st.caption(f"Last checked: {result['fee_checked']}")
            except Exception as exc:
                st.error(f"Pipeline error: {exc}")

    # ── Voice Agent section ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Voice Appointment Booking")

    pulse_ready = st.session_state.get("pulse_generated", False)
    top_theme   = st.session_state.get("top_theme", "")

    if pulse_ready:
        st.success(f"✓ Pulse generated. Top theme this week: **{top_theme}**")
        start_call = st.button("▶ Start Call", key="start_call_btn")
    else:
        st.warning("⚠ Generate a Weekly Pulse first. Upload a reviews CSV above.")
        start_call = False

    if start_call:
        if "voice_agent" not in st.session_state:
            st.session_state["voice_agent"] = VoiceAgent(
                session=st.session_state,
                calendar_path="data/mock_calendar.json",
            )
            st.session_state["voice_turn"] = 0
            greeting_text, greeting_audio = st.session_state["voice_agent"].get_greeting()
            st.session_state["greeting_text"]  = greeting_text
            st.session_state["greeting_audio"] = greeting_audio

    if "voice_agent" in st.session_state:
        st.markdown(f"**Agent:** {st.session_state.get('greeting_text', '')}")
        if st.session_state.get("greeting_audio"):
            st.audio(st.session_state["greeting_audio"], format="audio/mp3")

        agent = st.session_state["voice_agent"]
        turn  = st.session_state.get("voice_turn", 0)

        user_input = st.text_input(
            "Your response:",
            key=f"voice_input_{turn}",
        )

        if user_input:
            response_text, response_audio = agent.step(user_input)
            st.markdown(f"**Agent:** {response_text}")
            if response_audio:
                st.audio(response_audio, format="audio/mp3")
            st.session_state["voice_turn"] = turn + 1

            if agent.state in ("BOOKED", "WAITLIST"):
                code = st.session_state.get("booking_code", "N/A")
                st.success(f"✓ Appointment booked! Code: **{code}**")
                st.info("Check the Approval Center tab to review and approve calendar, notes, and email.")

# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — HITL Approval Center
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### HITL Approval Center")
    st.caption("Review and approve all AI-generated actions before they execute.")

    pending_count = sum(
        1 for a in st.session_state["mcp_queue"] if a["status"] == "pending"
    )
    if pending_count > 0:
        st.warning(f"⚠ {pending_count} action(s) awaiting your approval")

    mcp_client = MCPClient(mode=MCP_MODE)
    render_hitl(session=st.session_state, mcp_client=mcp_client)

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dsa-footer">
  <div class="dsa-footer-grid">
    <div class="dsa-footer-brand">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
        <div class="dsa-logo-icon" style="width:30px;height:30px;font-size:16px;">📊</div>
        <div style="font-size:0.95rem;font-weight:800;color:var(--text-1);">Investor Ops & Intelligence Suite by Dalal Street Advisors</div>
      </div>
      <p>AI-powered mutual fund intelligence platform. RAG-driven FAQ, weekly review pulse, voice appointment booking, and human-in-the-loop approvals — all in one place.</p>
      <div style="margin-top:14px;font-size:0.72rem;color:var(--text-3);">AI Bootcamp Capstone · 2026</div>
    </div>
    <div class="dsa-footer-col">
      <h4>Features</h4>
      <a href="#">Smart-Sync FAQ</a>
      <a href="#">Review Pulse</a>
      <a href="#">Voice Booking</a>
      <a href="#">Approval Center</a>
      <a href="#">NAV Tracker</a>
    </div>
    <div class="dsa-footer-col">
      <h4>Funds Covered</h4>
      <a href="#">SBI Large Cap</a>
      <a href="#">SBI ELSS</a>
      <a href="#">SBI Small Cap</a>
      <a href="#">SBI Flexicap</a>
      <a href="#">SBI Midcap</a>
    </div>
    <div class="dsa-footer-col">
      <h4>Technology</h4>
      <a href="#">Claude Sonnet 4.6</a>
      <a href="#">ChromaDB RAG</a>
      <a href="#">MCP Protocol</a>
      <a href="#">Sentence Transformers</a>
      <a href="#">Streamlit</a>
    </div>
  </div>
  <div class="dsa-footer-bottom">
    <div class="dsa-footer-copy">
      Facts only — no investment advice. Data sourced from SBI Mutual Fund and INDMoney public pages.
      Powered by <strong style="color:var(--gold-dim);">Claude Sonnet</strong> +
      <strong style="color:var(--gold-dim);">ChromaDB</strong>.
      Past NAV figures do not indicate future performance.
    </div>
    <div class="dsa-footer-right">
      <span>AMFI</span> Registered · ARN data from sbimf.com<br>
      <span>Claude</span> · <span>Anthropic</span> · AI Bootcamp 2026
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
