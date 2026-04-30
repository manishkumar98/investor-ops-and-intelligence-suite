"""Investor Ops & Intelligence Suite — main Streamlit entry point.

Run: streamlit run app.py
"""
import hashlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path

# Make phase6 sub-packages (voice.*, src.*, booking.*, dialogue.*) importable
# by voice_agent.py and other phase4 code that use short-form imports.
_p6 = str(Path(__file__).resolve().parent / "phase6_pillar_b_voice")
if _p6 not in sys.path:
    sys.path.insert(0, _p6)

import streamlit as st
import streamlit.components.v1 as components

from config import load_env, MCP_MODE
from session_init import init_session_state
from phase5_pillar_a_faq.faq_engine import query as faq_query
from phase2_corpus_pillar_a.ingest import get_collection
from phase4_voice_pillar_b.voice_agent import VoiceAgent
from phase7_pillar_c_hitl.mcp_client import MCPClient
from phase7_pillar_c_hitl.hitl_panel import render as render_hitl

from scripts.run_review_pipeline import run_pipeline as _run_full_pipeline

def _build_css(is_light: bool) -> str:
    """Return full app CSS with palette substituted for the chosen theme."""
    if is_light:
        subs = {
            "VAR_BG_BASE":          "#F7F3EE",
            "VAR_BG_CARD":          "#FFFFFF",
            "VAR_BG_GLASS":         "rgba(0,0,0,0.03)",
            "VAR_BORDER":           "rgba(0,0,0,0.08)",
            "VAR_GOLD_1":           "#A67C00",
            "VAR_GOLD_1B":          "#7A5C00",
            "VAR_GOLD_2":           "#C49A10",
            "VAR_GOLD_GLOW":        "rgba(166,124,0,0.14)",
            "VAR_GOLD_DIM":         "rgba(166,124,0,0.65)",
            "VAR_GOLD_BORDER_DIM":  "rgba(166,124,0,0.22)",
            "VAR_TEXT_1":           "#1A1612",
            "VAR_TEXT_2":           "#6B5E52",
            "VAR_TEXT_3":           "#A0918A",
            "VAR_GREEN":            "#166534",
            "VAR_RED":              "#B91C1C",
            "VAR_AMBIENT_G":        ("radial-gradient(ellipse 80% 40% at 50% -5%,"
                                     " rgba(166,124,0,0.07) 0%, transparent 70%),"
                                     "radial-gradient(ellipse 40% 30% at 85% 100%,"
                                     " rgba(166,124,0,0.04) 0%, transparent 60%)"),
            "VAR_SIDEBAR_BG":       "#EEE9E2",
            "VAR_CARD_SHADOW":      "0 1px 3px rgba(0,0,0,0.07), 0 4px 16px rgba(0,0,0,0.05)",
            "VAR_BTN_SHADOW":       "rgba(166,124,0,0.20)",
            "VAR_BTN_HOVER_SHADOW": "rgba(166,124,0,0.35)",
            "VAR_REJECT_BG":        "rgba(185,28,28,0.08)",
            "VAR_REJECT_COL":       "#B91C1C",
            "VAR_REJECT_BDR":       "rgba(185,28,28,0.25)",
            "VAR_ALERT_BORDER":     "rgba(166,124,0,0.20)",
            "VAR_BG_CODE":          "#EDE8E1",
            "VAR_BG_TICKER":        "#EEE9E2",
            "VAR_BG_HEADER":        "rgba(247,243,238,0.96)",
            "VAR_BG_FOOTER":        "#EEE9E2",
            "VAR_TOOLTIP_BG":       "#FFFFFF",
            "VAR_TOOLTIP_SHADOW":   "rgba(0,0,0,0.10)",
            "VAR_FUND_HOVER_SHADOW":"0 8px 20px rgba(0,0,0,0.08)",
            "VAR_USER_MSG_BG":      "rgba(166,124,0,0.06)",
            "VAR_USER_MSG_BORDER":  "rgba(166,124,0,0.18)",
        }
    else:
        subs = {
            "VAR_BG_BASE":          "#0A0C14",
            "VAR_BG_CARD":          "#10131F",
            "VAR_BG_GLASS":         "rgba(255,255,255,0.04)",
            "VAR_BORDER":           "rgba(255,255,255,0.08)",
            "VAR_GOLD_1":           "#C9A84C",
            "VAR_GOLD_1B":          "#A8873A",
            "VAR_GOLD_2":           "#E8C96D",
            "VAR_GOLD_GLOW":        "rgba(201,168,76,0.18)",
            "VAR_GOLD_DIM":         "rgba(201,168,76,0.55)",
            "VAR_GOLD_BORDER_DIM":  "rgba(201,168,76,0.22)",
            "VAR_TEXT_1":           "#F5F0E8",
            "VAR_TEXT_2":           "#9A9080",
            "VAR_TEXT_3":           "#6B6358",
            "VAR_GREEN":            "#22C55E",
            "VAR_RED":              "#EF4444",
            "VAR_AMBIENT_G":        ("radial-gradient(ellipse 80% 40% at 50% -5%,"
                                     " rgba(201,168,76,0.07) 0%, transparent 70%),"
                                     "radial-gradient(ellipse 40% 30% at 85% 100%,"
                                     " rgba(201,168,76,0.04) 0%, transparent 60%)"),
            "VAR_SIDEBAR_BG":       "#10131F",
            "VAR_CARD_SHADOW":      "none",
            "VAR_BTN_SHADOW":       "rgba(201,168,76,0.25)",
            "VAR_BTN_HOVER_SHADOW": "rgba(201,168,76,0.40)",
            "VAR_REJECT_BG":        "rgba(239,68,68,0.12)",
            "VAR_REJECT_COL":       "#EF4444",
            "VAR_REJECT_BDR":       "rgba(239,68,68,0.35)",
            "VAR_ALERT_BORDER":     "rgba(201,168,76,0.20)",
            "VAR_BG_CODE":          "#0D0F1A",
            "VAR_BG_TICKER":        "#0D0F1A",
            "VAR_BG_HEADER":        "rgba(10,12,20,0.95)",
            "VAR_BG_FOOTER":        "#07080F",
            "VAR_TOOLTIP_BG":       "#151826",
            "VAR_TOOLTIP_SHADOW":   "rgba(0,0,0,0.50)",
            "VAR_FUND_HOVER_SHADOW":"0 8px 32px rgba(0,0,0,0.30)",
            "VAR_USER_MSG_BG":      "rgba(201,168,76,0.06)",
            "VAR_USER_MSG_BORDER":  "rgba(201,168,76,0.18)",
        }
    css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── CSS Variables ── */
:root {
  --bg-base:   VAR_BG_BASE;
  --bg-card:   VAR_BG_CARD;
  --bg-glass:  VAR_BG_GLASS;
  --border:    VAR_BORDER;
  --gold-1:    VAR_GOLD_1;
  --gold-2:    VAR_GOLD_2;
  --gold-glow: VAR_GOLD_GLOW;
  --gold-dim:  VAR_GOLD_DIM;
  --text-1:    VAR_TEXT_1;
  --text-2:    VAR_TEXT_2;
  --text-3:    VAR_TEXT_3;
  --green:     VAR_GREEN;
  --red:       VAR_RED;
}

/* ── Reset Streamlit chrome ── */
#MainMenu, footer, [data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stHeader"] { background: transparent !important; height: 0 !important; }

/* ── Full-width block container ── */
.block-container { padding: 0 !important; max-width: 100% !important; margin: 0 !important; }

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
  content: ''; position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background: VAR_AMBIENT_G;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
  background-color: VAR_SIDEBAR_BG !important;
  border-right: 1px solid var(--border);
}
section[data-testid="stSidebar"] * { color: var(--text-1) !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
  background-color: var(--bg-card); border-bottom: 1px solid var(--border);
  gap: 0; padding: 0 48px;
}
.stTabs [data-baseweb="tab"] {
  color: var(--text-2) !important; background-color: transparent !important;
  border: none !important; padding: 14px 24px;
  font-weight: 500; font-size: 0.875rem; letter-spacing: 0.02em;
}
.stTabs [aria-selected="true"] {
  color: var(--gold-2) !important; border-bottom: 2px solid var(--gold-1) !important;
  background-color: transparent !important;
}
.stTabs [data-baseweb="tab"]:hover {
  color: var(--gold-2) !important; background-color: var(--gold-glow) !important;
}

/* ── Metrics ── */
div[data-testid="stMetric"] {
  background: var(--bg-card) !important; border: 1px solid var(--border) !important;
  border-radius: 12px !important; padding: 16px !important;
  box-shadow: VAR_CARD_SHADOW;
}
div[data-testid="stMetricValue"] { color: var(--gold-2) !important; font-weight: 700; }

/* ── Buttons ── */
.stButton > button,
[data-testid="stBaseButton-primary"],
[data-testid="stBaseButton-secondary"] {
  background: linear-gradient(135deg, VAR_GOLD_1, VAR_GOLD_1B) !important;
  color: #111111 !important; border: none !important;
  border-radius: 100px !important; font-weight: 700 !important;
  font-size: 0.875rem !important; padding: 10px 24px !important;
  letter-spacing: 0.02em !important;
  box-shadow: 0 4px 20px VAR_BTN_SHADOW !important;
  transition: all 0.2s ease !important;
}
.stButton > button:hover,
[data-testid="stBaseButton-primary"]:hover,
[data-testid="stBaseButton-secondary"]:hover {
  background: linear-gradient(135deg, VAR_GOLD_2, VAR_GOLD_1) !important;
  color: #111111 !important;
  box-shadow: 0 6px 28px VAR_BTN_HOVER_SHADOW !important;
  transform: translateY(-1px) !important;
}
.stButton > button *, [data-testid="stBaseButton-primary"] *,
[data-testid="stBaseButton-secondary"] * { color: #111111 !important; }
.stButton > button p, .stButton > button span,
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primary"] span,
button[kind="primary"] p { color: #111111 !important; }

/* ── Reject button — scoped to HITL expanders only ── */
[data-testid="stExpander"] [data-testid="column"]:last-child .stButton > button,
[data-testid="stExpander"] [data-testid="column"]:last-child [data-testid="stBaseButton-secondary"] {
  background: VAR_REJECT_BG !important; color: VAR_REJECT_COL !important;
  border: 1px solid VAR_REJECT_BDR !important; box-shadow: none !important;
}
[data-testid="stExpander"] [data-testid="column"]:last-child .stButton > button p,
[data-testid="stExpander"] [data-testid="column"]:last-child .stButton > button span,
[data-testid="stExpander"] [data-testid="column"]:last-child [data-testid="stBaseButton-secondary"] p {
  color: VAR_REJECT_COL !important;
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
  border-color: var(--gold-1) !important; box-shadow: 0 0 0 2px var(--gold-glow) !important;
}

/* ── Text inputs ── */
.stTextInput > div > div > input {
  background: var(--bg-card) !important; border: 1px solid var(--border) !important;
  color: var(--text-1) !important; border-radius: 8px !important;
}
.stTextInput > div > div > input:focus {
  border-color: var(--gold-1) !important; box-shadow: 0 0 0 2px var(--gold-glow) !important;
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
  background: var(--gold-glow) !important;
  border: 1px solid VAR_ALERT_BORDER !important; border-radius: 10px !important;
}

/* ── Expanders ── */
[data-testid="stExpander"] {
  background: var(--bg-card) !important; border: 1px solid var(--border) !important;
  border-radius: 10px !important; box-shadow: VAR_CARD_SHADOW;
}
[data-testid="stExpander"] summary { color: var(--text-1) !important; }

/* ── Misc ── */
.stCode, pre { background: VAR_BG_CODE !important; border: 1px solid var(--border) !important; border-radius: 8px !important; }
h1,h2,h3,h4 { color: var(--text-1) !important; font-weight: 700 !important; }
hr { border-color: var(--border) !important; margin: 24px 0 !important; }
[data-testid="stMarkdownContainer"] p { color: var(--text-2) !important; }
.stSpinner > div { color: var(--gold-dim) !important; }
[data-testid="stToggle"] label,
[data-testid="stWidgetLabel"] { color: var(--text-2) !important; }

/* ── Tab content padding ── */
.stTabs [data-testid="stTabsContent"] {
  padding: 32px 48px 40px !important; max-width: 1200px !important; margin: 0 auto !important;
}
@media(max-width:768px) {
  .stTabs [data-testid="stTabsContent"] { padding: 24px 20px 32px !important; }
}

/* ── Chat messages ── */
[data-testid="stChatMessage"] {
  padding: 16px 20px !important; border-radius: 16px !important; margin-bottom: 12px !important;
}
[data-testid="stChatMessage"][data-testid*="user"],
.stChatMessage:has([data-testid="chatAvatarIcon-user"]) {
  background: VAR_USER_MSG_BG !important; border: 1px solid VAR_USER_MSG_BORDER !important;
}
[data-testid="stChatMessage"][data-testid*="assistant"],
.stChatMessage:has([data-testid="chatAvatarIcon-assistant"]) {
  background: var(--bg-card) !important; border: 1px solid var(--border) !important;
}
[data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] p {
  color: var(--text-1) !important; line-height: 1.7 !important; font-size: 0.93rem !important;
}
[data-testid="chatAvatarIcon-user"] {
  background: var(--gold-glow) !important; border: 1px solid var(--gold-dim) !important;
}
[data-testid="chatAvatarIcon-assistant"] {
  background: var(--bg-glass) !important; border: 1px solid var(--border) !important;
}

/* ── Chat input ── */
[data-testid="stChatInput"] {
  background: var(--bg-card) !important; border: 1px solid var(--border) !important;
  border-radius: 16px !important; padding: 4px 8px !important; transition: border-color 0.2s !important;
}
[data-testid="stChatInput"]:focus-within {
  border-color: var(--gold-1) !important; box-shadow: 0 0 0 3px var(--gold-glow) !important;
}
[data-testid="stChatInput"] textarea {
  background: transparent !important; border: none !important;
  color: var(--text-1) !important; font-size: 0.93rem !important;
  padding: 12px 16px !important; border-radius: 12px !important; box-shadow: none !important;
}
[data-testid="stChatInput"] textarea::placeholder { color: var(--text-3) !important; }
[data-testid="stChatInput"] button {
  background: linear-gradient(135deg, VAR_GOLD_1, VAR_GOLD_1B) !important;
  border: none !important; border-radius: 10px !important; color: #0A0C14 !important; margin: 4px !important;
}

/* ── Fund cards ── */
.fund-grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(300px,1fr)); gap:16px; margin:20px 0 32px; }
.fund-card { 
  background:linear-gradient(145deg, var(--bg-card), var(--bg-base)); 
  border:1px solid var(--border); 
  border-radius:16px; 
  padding:20px; 
  transition:all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
  box-shadow: 0 4px 12px rgba(0,0,0,0.1); 
  position: relative;
  overflow: hidden;
}
.fund-card::before {
  content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%;
  background: var(--gold-1); opacity: 0.7;
}
.fund-card:hover { 
  border-color:var(--gold-1); 
  background:var(--bg-card);
  transform:translateY(-4px); 
  box-shadow: 0 12px 24px rgba(0,0,0,0.2); 
}
.fund-name { color:var(--gold-2); font-weight:700; font-size:1.0rem; margin-bottom:8px; }
.fund-meta { color:var(--text-2); font-size:0.8rem; display:flex; gap:10px; margin-bottom:12px; flex-wrap:wrap; }
.fund-tag { 
  background:var(--bg-glass); 
  border:1px solid var(--border); 
  border-radius:6px; 
  padding:3px 10px; 
  font-size:0.75rem; 
  font-weight: 500;
  color:var(--text-2); 
}
.fund-coverage { color:var(--text-3); font-size:0.82rem; margin-top:8px; line-height:1.5; font-style: italic; }

/* ── NAV Ticker ── */
.ticker-wrap {
  width:100%; background:VAR_BG_TICKER; border-bottom:1px solid var(--border);
  overflow:hidden; padding:7px 0; position:sticky; top:0; z-index:1000;
}
.ticker-track { display:flex; width:max-content; animation:ticker-scroll 38s linear infinite; }
.ticker-track:hover { animation-play-state:paused; }
@keyframes ticker-scroll { 0%{transform:translateX(0);} 100%{transform:translateX(-50%);} }
.ticker-item { display:inline-flex; align-items:center; gap:6px; padding:0 28px; white-space:nowrap; font-size:0.78rem; border-right:1px solid var(--border); }
.ticker-symbol { color:var(--gold-1); font-weight:600; letter-spacing:0.04em; }
.ticker-nav    { color:var(--text-2); font-size:0.73rem; }
.ticker-up     { color:var(--green); font-weight:600; }
.ticker-down   { color:var(--red); font-weight:600; }
.ticker-neutral{ color:var(--text-2); font-weight:600; }

/* ── Site Header ── */
.dsa-header {
  position:sticky; top:0; z-index:100;
  background:VAR_BG_HEADER; backdrop-filter:blur(20px);
  border-bottom:1px solid var(--border);
  display:flex; align-items:center; justify-content:space-between;
  padding:0 48px; height:64px; width:100%; box-sizing:border-box;
}
.dsa-logo-wrap { display:flex; align-items:center; gap:12px; }
.dsa-logo-icon {
  width:38px; height:38px; border-radius:10px;
  background:linear-gradient(135deg,VAR_GOLD_1,VAR_GOLD_1B);
  display:flex; align-items:center; justify-content:center; font-size:20px; flex-shrink:0;
}
.dsa-logo-text { font-size:1.05rem; font-weight:800; color:var(--text-1); letter-spacing:-0.02em; }
.dsa-logo-sub  { font-size:0.65rem; color:var(--gold-dim); letter-spacing:0.08em; text-transform:uppercase; font-weight:500; }
.dsa-header-badge {
  background:var(--gold-glow); border:1px solid var(--gold-dim);
  color:var(--gold-2); border-radius:100px; padding:6px 16px;
  font-size:0.72rem; font-weight:600; letter-spacing:0.06em; text-transform:uppercase;
  margin-right: 52px;
}
@media(max-width:768px){ .dsa-header{padding:0 20px;} }

/* ── Links — markdown content, footer, source citations ── */
[data-testid="stMarkdownContainer"] a {
  color: var(--gold-2) !important; text-decoration: underline; text-underline-offset: 3px;
}
[data-testid="stMarkdownContainer"] a:hover { color: var(--gold-1) !important; }
.dsa-footer-col a { cursor: pointer; }
.dsa-footer-col a[href^="http"] { color: var(--text-2) !important; }
.dsa-footer-col a[href^="http"]:hover { color: var(--text-1) !important; text-decoration: underline; }

/* ── Site Footer ── */
.dsa-footer {
  background:VAR_BG_FOOTER; border-top:1px solid var(--border); padding:48px 48px 32px; margin-top:0;
}
.dsa-footer-grid {
  display:grid; grid-template-columns:2fr 1fr 1fr 1fr; gap:40px; max-width:1200px; margin:0 auto 40px;
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

/* ── Pillar info tooltip ── */
.pillar-header { display:flex; align-items:center; gap:10px; margin-bottom:6px; }
.info-chip {
  display:inline-flex; align-items:center; gap:5px;
  background:var(--gold-glow); border:1px solid VAR_GOLD_BORDER_DIM;
  border-radius:100px; padding:4px 12px 4px 8px;
  font-size:0.72rem; color:var(--text-2); white-space:nowrap; cursor:help;
}
.info-circle {
  display:inline-flex; align-items:center; justify-content:center;
  width:16px; height:16px; border-radius:50%;
  background:var(--gold-glow); color:var(--gold-1); font-size:0.65rem; font-weight:700; flex-shrink:0;
}
.pillar-tooltip { position:relative; }
.pillar-tooltip-body {
  visibility:hidden; opacity:0;
  background:VAR_TOOLTIP_BG; border:1px solid VAR_GOLD_BORDER_DIM;
  color:var(--text-1); border-radius:10px; padding:12px 16px;
  font-size:0.78rem; line-height:1.65;
  position:absolute; z-index:9999; top:calc(100% + 8px); left:0;
  width:340px; pointer-events:none;
  box-shadow:0 12px 32px VAR_TOOLTIP_SHADOW; transition:opacity 0.18s;
}
.pillar-tooltip:hover .pillar-tooltip-body { visibility:visible; opacity:1; }

/* ── Market-context card (Tab 3) ── */
.mctx-card {
  background:var(--bg-card); border:1px solid VAR_GOLD_BORDER_DIM;
  border-radius:12px; padding:18px 22px; margin-bottom:20px; box-shadow:VAR_CARD_SHADOW;
}
.mctx-label {
  font-size:0.7rem; font-weight:700; letter-spacing:0.1em;
  text-transform:uppercase; color:var(--gold-dim); margin-bottom:8px;
}
.mctx-text { font-size:0.86rem; color:var(--text-2); line-height:1.7; }

/* Hide audio-input widget — controlled entirely by VAD JS */
/* ── Header theme toggle — fixed overlay in dsa-header band ── */
div[data-testid="element-container"]:has(#dsa-hdr-toggle-anchor)
  + div[data-testid="stHorizontalBlock"] {
  height: 0 !important; overflow: visible !important;
  margin: 0 !important; padding: 0 !important;
}
div[data-testid="element-container"]:has(#dsa-hdr-toggle-anchor)
  + div[data-testid="stHorizontalBlock"]
  > div[data-testid="column"]:first-child { display: none !important; }
div[data-testid="element-container"]:has(#dsa-hdr-toggle-anchor)
  + div[data-testid="stHorizontalBlock"]
  > div[data-testid="column"]:last-child {
  position: fixed !important;
  top: 14px !important; right: 24px !important;
  z-index: 9999 !important; width: 40px !important; padding: 0 !important;
}
div[data-testid="element-container"]:has(#dsa-hdr-toggle-anchor)
  + div[data-testid="stHorizontalBlock"] .stButton > button {
  background: var(--bg-glass) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  width: 36px !important; height: 36px !important;
  padding: 0 !important; box-shadow: none !important;
  font-size: 1.1rem !important; display: flex !important;
  align-items: center !important; justify-content: center !important;
}
div[data-testid="element-container"]:has(#dsa-hdr-toggle-anchor)
  + div[data-testid="stHorizontalBlock"] .stButton > button:hover {
  background: var(--gold-glow) !important;
  border-color: var(--gold-dim) !important;
  transform: none !important; box-shadow: none !important;
}
div[data-testid="element-container"]:has(#dsa-hdr-toggle-anchor)
  + div[data-testid="stHorizontalBlock"] .stButton > button * {
  color: var(--text-1) !important; font-size: 1.1rem !important;
}

/* ── Audio input ── */
[data-testid="stAudioInput"] {
  position: fixed !important; top: -9999px !important; left: -9999px !important;
  width: 1px !important; height: 1px !important;
  overflow: hidden !important; pointer-events: none !important;
}
.va2-caption {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 12px;
  padding: 14px 20px; font-size: 0.88rem; color: var(--text-2);
  line-height: 1.65; font-style: italic; margin: 12px 0;
}
.va2-status {
  font-size: 0.75rem; color: var(--gold-1); letter-spacing: 0.04em;
  font-style: italic; min-height: 18px; text-align: center;
}
.va2-vad-pill {
  display: inline-block; font-size: 0.82rem; font-weight: 600;
  letter-spacing: 0.04em; padding: 4px 16px; border-radius: 100px;
  background: var(--bg-glass); border: 1px solid var(--border);
  color: var(--text-2); min-height: 28px; text-align: center;
}
</style>"""
    for k, v in subs.items():
        css = css.replace(k, v)
    return css


_DOMAIN_LABELS = {
    "sbimf.com":      "SBI Mutual Fund",
    "amfiindia.com":  "AMFI India",
    "sebi.gov.in":    "SEBI",
    "indmoney.com":   "INDMoney",
}


_ACRONYMS = {"Sbi", "Elss", "Sip", "Nav", "Kyc", "Amc", "Amfi", "Sebi", "Nri"}

# Indmoney URLs that carry a legacy/former fund name — override the slug-derived label.
_URL_NAME_OVERRIDES: dict[str, str] = {
    "sbi-long-term-equity-fund": "SBI ELSS Tax Saver Fund",
    "sbi-bluechip-fund":         "SBI Large Cap Fund",
}


def _source_label(url: str) -> str:
    """Return a human-readable label for a source URL."""
    domain_label = next((v for k, v in _DOMAIN_LABELS.items() if k in url), None)

    # Override known legacy-named URLs before slug parsing
    for slug_key, override_name in _URL_NAME_OVERRIDES.items():
        if slug_key in url.lower():
            return f"{override_name} — {domain_label}" if domain_label else override_name

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


_QUERY_TYPE_BADGE = {
    "factual_only": ('<span style="font-size:0.72rem;padding:2px 8px;border-radius:100px;'
                     'background:rgba(126,182,255,0.15);color:#7EB6FF;font-weight:600;'
                     'border:1px solid rgba(126,182,255,0.35);">M1 FAQ</span>'),
    "fee_only":     ('<span style="font-size:0.72rem;padding:2px 8px;border-radius:100px;'
                     'background:rgba(201,168,76,0.15);color:#C9A84C;font-weight:600;'
                     'border:1px solid rgba(201,168,76,0.35);">M2 Fee Explainer</span>'),
    "compound":     ('<span style="font-size:0.72rem;padding:2px 8px;border-radius:100px;'
                     'background:rgba(34,197,94,0.15);color:#22C55E;font-weight:600;'
                     'border:1px solid rgba(34,197,94,0.35);">M1 + M2 Combined</span>'),
}


# ── 1. Bootstrap ──────────────────────────────────────────────────────────────
load_env()


@st.cache_resource(show_spinner=False)
def _warm_embedder():
    """Pre-load the local sentence-transformer model once at startup.

    Avoids the cold-start delay (OpenAI quota fail + model load) on the first FAQ query.
    """
    import phase2_corpus_pillar_a.embedder as _emb
    _emb._openai_failed = True          # skip the quota-exceeded OpenAI call
    _emb.get_embeddings(["warmup"])     # loads and caches _sentence_model
    return True


_warm_embedder()

st.set_page_config(
    page_title="Investor Ops & Intelligence Suite by Dalal Street Advisors",
    page_icon="📊",
    layout="wide",
)
init_session_state(st.session_state)

# ── Theme state ───────────────────────────────────────────────────────────────
if "theme" not in st.session_state:
    st.session_state["theme"] = "dark"
_theme    = st.session_state["theme"]
_is_light = _theme == "light"

st.markdown(_build_css(_is_light), unsafe_allow_html=True)

# ── Tab-2 Voice Agent helpers ─────────────────────────────────────────────────

def _va2_play_and_listen_js(audio_bytes: bytes, turn_id: str) -> None:
    """Play agent audio, then auto-start VAD + mic. After silence → stop → STT cycle."""
    import base64
    b64 = base64.b64encode(audio_bytes).decode()
    fmt = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mpeg"
    components.html(f"""
    <script>
    (function() {{
        var TURN = 'va2_{turn_id}';
        var pdoc = window.parent.document;
        if (window.parent.__va2Turn === TURN) return;
        window.parent.__va2Turn = TURN;
        if (typeof window.parent.__va2Stop === 'function') {{ window.parent.__va2Stop(); }}

        var ONSET=18, SILENCE=12, MIN_SPEECH_MS=200, SILENCE_MS=2000, NO_INPUT_MS=10000;
        var vadStream=null, audioCtx=null, noInputTimer=null, checkRAF=null, micStarted=false;

        function setStatus(msg, color) {{
            var el = pdoc.getElementById('va2-vad-status');
            if (el) {{ el.textContent = msg; el.style.color = color || ''; }}
        }}
        function getRecordBtn() {{
            var b = pdoc.querySelector('[data-testid="stAudioInputActionButton"][aria-label="Record"]');
            if (b) return b;
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            return inp ? inp.querySelector('button') : null;
        }}
        function getStopBtn() {{
            var b = pdoc.querySelector('[data-testid="stAudioInputActionButton"][aria-label="Stop recording"]');
            if (b) return b;
            var inp = pdoc.querySelector('[data-testid="stAudioInput"]');
            if (inp) {{ var btns = inp.querySelectorAll('button'); return btns.length>1?btns[btns.length-1]:btns[0]||null; }}
            return null;
        }}
        function stopVAD() {{
            clearTimeout(noInputTimer);
            if (checkRAF) {{ cancelAnimationFrame(checkRAF); checkRAF=null; }}
            if (vadStream) {{ vadStream.getTracks().forEach(function(t){{t.stop();}}); vadStream=null; }}
            if (audioCtx) {{ try{{audioCtx.close();}}catch(e){{}} audioCtx=null; }}
            window.parent.__va2Stop = null;
            if (micStarted) {{
                micStarted=false;
                setStatus('Processing your response…','rgba(201,168,76,1)');
                var btn=getStopBtn(); if(btn) btn.click();
            }}
        }}
        window.parent.__va2Stop = stopVAD;

        function rms(data) {{ var s=0; for(var i=0;i<data.length;i++) s+=data[i]*data[i]; return Math.sqrt(s/data.length); }}
        function runVAD(stream) {{
            vadStream=stream;
            audioCtx=new(window.AudioContext||window.webkitAudioContext)();
            var analyser=audioCtx.createAnalyser(); analyser.fftSize=512;
            audioCtx.createMediaStreamSource(stream).connect(analyser);
            var data=new Uint8Array(analyser.frequencyBinCount);
            var CALIB_MS=1500, samples=[], onsetLvl=ONSET, silLvl=SILENCE;
            setStatus('📡 Calibrating mic…','rgba(201,168,76,0.7)');
            var calibStart=Date.now();
            function calibrate() {{
                if(!vadStream) return; analyser.getByteTimeDomainData(data); samples.push(rms(data));
                if(Date.now()-calibStart<CALIB_MS) {{ checkRAF=requestAnimationFrame(calibrate); }}
                else {{
                    samples.sort(function(a,b){{return a-b;}});
                    var amb=samples[Math.floor(samples.length/2)];
                    onsetLvl=Math.max(ONSET,amb*3.0); silLvl=Math.max(SILENCE,amb*1.8);
                    setStatus('🎙 Listening — speak now','rgba(34,197,94,1)');
                    noInputTimer=setTimeout(function(){{if(!hasSpeech){{setStatus('No speech…','rgba(239,68,68,1)');stopVAD();}}}},NO_INPUT_MS);
                    checkRAF=requestAnimationFrame(check);
                }}
            }}
            var hasSpeech=false, speechStart=null, silenceStart=null;
            function check() {{
                if(!vadStream) return; analyser.getByteTimeDomainData(data); var lvl=rms(data);
                if(!hasSpeech) {{
                    if(lvl>onsetLvl) {{ if(!speechStart) speechStart=Date.now(); else if(Date.now()-speechStart>=MIN_SPEECH_MS){{hasSpeech=true;setStatus('🗣 User speaking…','rgba(34,197,94,1)');clearTimeout(noInputTimer);}} }}
                    else {{ speechStart=null; }}
                }} else {{
                    if(lvl<silLvl) {{ if(!silenceStart){{silenceStart=Date.now();setStatus('🗣 Paused…','rgba(201,168,76,1)');}} else if(Date.now()-silenceStart>SILENCE_MS){{stopVAD();return;}} }}
                    else {{ silenceStart=null; setStatus('🗣 User speaking…','rgba(34,197,94,1)'); }}
                }}
                checkRAF=requestAnimationFrame(check);
            }}
            checkRAF=requestAnimationFrame(calibrate);
        }}
        var _retry=0;
        function startMic() {{
            var btn=getRecordBtn();
            if(!btn) {{ if(++_retry<50){{setTimeout(startMic,150);return;}} setStatus('❌ Mic unavailable','rgba(239,68,68,1)'); return; }}
            setStatus('🎙 Mic starting…','rgba(34,197,94,0.7)'); micStarted=true; btn.click();
            navigator.mediaDevices.getUserMedia({{audio:true,video:false}})
            .then(function(stream){{runVAD(stream);}})
            .catch(function(){{setStatus('❌ Mic permission denied','rgba(239,68,68,1)');}});
        }}

        var raw=atob('{b64}'), buf=new Uint8Array(raw.length);
        for(var i=0;i<raw.length;i++) buf[i]=raw.charCodeAt(i);
        var url=URL.createObjectURL(new Blob([buf],{{type:'{fmt}'}}));
        var audio=new Audio(url);
        setStatus('🔊 Agent speaking…','rgba(201,168,76,1)');
        audio.addEventListener('ended',function(){{URL.revokeObjectURL(url);setTimeout(startMic,80);}},{{once:true}});
        audio.play().catch(function(){{URL.revokeObjectURL(url);startMic();}});
    }})();
    </script>
    """, height=0)


def _va2_autoplay_js(audio_bytes: bytes) -> None:
    """Play audio only (no VAD — used for terminal states)."""
    import base64
    b64 = base64.b64encode(audio_bytes).decode()
    fmt = "audio/wav" if audio_bytes[:4] == b"RIFF" else "audio/mpeg"
    components.html(f"""<script>
    (function(){{
        var raw=atob('{b64}'),buf=new Uint8Array(raw.length);
        for(var i=0;i<raw.length;i++) buf[i]=raw.charCodeAt(i);
        var url=URL.createObjectURL(new Blob([buf],{{type:'{fmt}'}}));
        var a=new Audio(url); a.play().catch(function(){{}});
        a.addEventListener('ended',function(){{URL.revokeObjectURL(url);}},{{once:true}});
    }})();
    </script>""", height=0)


def _va2_stt(audio_bytes: bytes) -> str:
    """STT: Groq Whisper → Google → Deepgram → offline via STTEngine."""
    os.environ.setdefault("STT_LANGUAGE", "en-IN")
    try:
        from phase6_pillar_b_voice.voice.stt_engine import STTEngine
        return STTEngine().transcribe(audio_bytes).text
    except Exception:
        return ""


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
    as_of_label = f'<span style="font-size:0.65rem;color:var(--text-3);padding-left:8px;">NAV as of {as_of}</span>' if as_of else ""
    return f'<div class="ticker-wrap">{track}{as_of_label}</div>'


_ticker = _build_ticker_html()
if _ticker:
    st.markdown(_ticker, unsafe_allow_html=True)

# ── App Header ────────────────────────────────────────────────────────────────
# Anchor lets CSS target the adjacent columns row and yank it to fixed position
st.markdown('<div id="dsa-hdr-toggle-anchor" style="display:none;height:0;"></div>',
            unsafe_allow_html=True)
_hdr_sp, _hdr_tog = st.columns([30, 1])
with _hdr_tog:
    _hdr_icon = "☀️" if not _is_light else "🌙"
    if st.button(_hdr_icon, key="header_theme_toggle", help="Toggle light / dark theme"):
        st.session_state["theme"] = "light" if not _is_light else "dark"
        st.rerun()

st.markdown("""
<div class="dsa-header">
  <div class="dsa-logo-wrap">
    <div class="dsa-logo-icon">📊</div>
    <div>
      <div class="dsa-logo-text">Investor Ops & Intelligence Suite by Dalal Street Advisors</div>
      <div class="dsa-logo-sub">Investor Ops &amp; Intelligence Platform</div>
    </div>
  </div>
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

# Auto-load pulse + fee data from disk so voice agent is ready without re-running pipeline
if not st.session_state.get("pulse_generated"):
    _pulse_file = Path("data/pulse_latest.json")
    _fee_file   = Path("data/fee_latest.json")
    if _pulse_file.exists():
        try:
            _pd = json.loads(_pulse_file.read_text())
            st.session_state["weekly_pulse"]    = _pd.get("weekly_note", "")
            st.session_state["top_3_themes"]    = _pd.get("top_3_themes", [])
            st.session_state["top_theme"]       = (_pd.get("top_3_themes") or [""])[0]
            st.session_state["pulse_generated"] = True
        except Exception:
            pass
    if _fee_file.exists():
        try:
            _fd = json.loads(_fee_file.read_text())
            st.session_state["fee_bullets"] = _fd.get("bullets", [])
            st.session_state["fee_sources"] = _fd.get("sources", [])
        except Exception:
            pass

# ── 2. Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    # ── Theme toggle ──────────────────────────────────────────────────────────
    _tog_new = st.toggle(
        "☀️  Light Mode" if not _is_light else "🌙  Dark Mode",
        value=_is_light,
        key="sidebar_theme_toggle",
    )
    if _tog_new != _is_light:
        st.session_state["theme"] = "light" if _tog_new else "dark"
        st.rerun()

    st.title("📊 Investor Ops & Intelligence Suite by Dalal Street Advisors")
    st.caption("Investor Ops & Intelligence Suite — Demo")
    st.markdown("---")

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
    "📚  Smart-Sync Knowledge Base",
    "📊  Insight-Driven Optimization",
    "🤖  Super-Agent MCP Workflow",
])

# ══════════════════════════════════════════════════════════════════════════════
# Tab 1 — Smart-Sync FAQ
# ══════════════════════════════════════════════════════════════════════════════
_SUPPORTED_FUNDS = [
    {
        "name": "SBI Bluechip Fund",
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
    {
        "name": "SBI Technology Opportunities Fund",
        "category": "Sectoral / IT",
        "risk": "Very High",
        "coverage": "Tech exposure, sector-specific risk, exit load details",
    },
    {
        "name": "SBI Healthcare Opportunities Fund",
        "category": "Sectoral / Pharma",
        "risk": "Very High",
        "coverage": "Pharma & healthcare themes, sector performance, fees",
    },
    {
        "name": "SBI Equity Hybrid Fund",
        "category": "Aggressive Hybrid",
        "risk": "Moderate–High",
        "coverage": "Equity-debt mix, rebalancing strategy, expense ratio",
    },
    {
        "name": "SBI Magnum Global Fund",
        "category": "Thematic / MNC",
        "risk": "High",
        "coverage": "MNC theme, global exposure, exit load & SIP details",
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
    st.markdown("""
<div class="pillar-header">
  <h3 style="margin:0;color:var(--text-1);">The Smart-Sync Knowledge Base</h3>
  <div class="pillar-tooltip">
    <div class="info-chip">
      <span class="info-circle">i</span>Pillar A · M1 + M2
    </div>
    <div class="pillar-tooltip-body">
      <span style="color:#E8C96D;font-weight:700;">Pillar A — Smart-Sync Knowledge Base</span>
      <br><br>
      Merges the <em>Mutual Fund FAQ corpus (M1)</em> with the <em>Fee Explainer (M2)</em>
      into a single Unified Search. Every combined answer maintains the
      <strong>6-bullet structure</strong> and <strong>source citations</strong> from both
      corpuses — so a question like "What is the exit load for ELSS and why was I charged it?"
      pulls the Exit Load % from M1 and the Fee Logic from M2 in one response.
    </div>
  </div>
</div>
<p style="color:var(--text-2);font-size:0.875rem;margin:6px 0 0;">
  Ask factual questions about SBI Mutual Fund schemes and fees. Facts only — no investment advice.
</p>
""", unsafe_allow_html=True)

    # ── Knowledge Base Control Center (Pillar A) ──────────────────────────────
    st.markdown("""
    <div style="background:var(--bg-glass); border:1px solid var(--border); border-radius:16px; padding:24px; margin-bottom:32px; box-shadow:0 8px 32px rgba(0,0,0,0.15);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:20px;">
        <div style="display:flex; align-items:center; gap:12px;">
          <div style="width:10px; height:30px; background:var(--gold-1); border-radius:4px;"></div>
          <h4 style="margin:0; font-size:1.1rem; letter-spacing:0.02em;">Knowledge Base Control Center</h4>
        </div>
        <div style="font-size:0.75rem; color:var(--text-3); text-transform:uppercase; letter-spacing:0.1em; font-weight:600;">System Ready</div>
      </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 1, 1.2])
    with c1:
        try:
            count = get_collection("mf_faq_corpus").count()
            st.markdown(f"""
            <div style="background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:16px; text-align:center;">
              <div style="font-size:0.7rem; color:var(--text-3); text-transform:uppercase; margin-bottom:4px;">FAQ Chunks</div>
              <div style="font-size:1.8rem; font-weight:800; color:var(--gold-2);">{count}</div>
            </div>
            """, unsafe_allow_html=True)
        except:
            st.error("FAQ Error")
    with c2:
        try:
            count = get_collection("fee_corpus").count()
            st.markdown(f"""
            <div style="background:var(--bg-card); border:1px solid var(--border); border-radius:12px; padding:16px; text-align:center;">
              <div style="font-size:0.7rem; color:var(--text-3); text-transform:uppercase; margin-bottom:4px;">Fee Chunks</div>
              <div style="font-size:1.8rem; font-weight:800; color:var(--gold-2);">{count}</div>
            </div>
            """, unsafe_allow_html=True)
        except:
            st.error("Fee Error")
    with c3:
        st.markdown("""
        <style>
        /* Specific override for the Sync button to make it stand out and tighten padding */
        div[data-testid="column"]:nth-of-type(3) button {
            background: linear-gradient(135deg, #22C55E, #166534) !important;
            padding: 6px 16px !important;
            min-height: 38px !important;
            color: white !important;
        }
        div[data-testid="column"]:nth-of-type(3) button p {
            color: white !important;
            font-size: 0.82rem !important;
        }
        </style>
        """, unsafe_allow_html=True)
        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        if st.button("🚀 Sync Knowledge Base", use_container_width=True, help="Ingest URLs and update the database"):
            with st.spinner(""):
                try:
                    from phase2_corpus_pillar_a.ingest import ingest_corpus, ingest_local_files
                    ingest_corpus(force=False)
                    ingest_local_files()
                    st.toast("✅ Knowledge Base Synchronized!", icon="🚀")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Sync failed: {e}")
    
    st.markdown("</div>", unsafe_allow_html=True)

    with st.expander("📋 Supported Mutual Funds", expanded=True):
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
            "- Can I redeem SBI Large Cap Fund within 6 months and what fees apply?\n"
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
            _badge = _QUERY_TYPE_BADGE.get(response.query_type, "")
            _caption_extra = f"&nbsp;&nbsp;{_badge}" if _badge else ""
            st.markdown(
                f'<span style="font-size:0.75rem;color:var(--text-3);">'
                f'Last updated from sources: {response.last_updated}'
                f'</span>{_caption_extra}',
                unsafe_allow_html=True,
            )

    user_question = st.chat_input("Ask a factual question about SBI Mutual Funds...")
    if user_question:
        # Show the question immediately so the user can see it while waiting
        with st.chat_message("user"):
            st.write(user_question)
        with st.chat_message("assistant"):
            with st.spinner("Searching knowledge base and composing answer…"):
                faq_query(user_question, st.session_state)
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# Tab 2 — Review Pulse & Voice Agent
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    # ── Header row ──────────────────────────────────────────────────────────
    _col_title, _col_btn = st.columns([5, 1])
    with _col_title:
        st.markdown("""
<div class="pillar-header">
  <h3 style="margin:0;color:var(--text-1);">Insight-Driven Agent Optimization</h3>
  <div class="pillar-tooltip">
    <div class="info-chip">
      <span class="info-circle">i</span>Pillar B · M2 + M3
    </div>
    <div class="pillar-tooltip-body">
      <span style="color:#E8C96D;font-weight:700;">Pillar B — Insight-Driven Optimization</span>
      <br><br>
      Uses the <em>Weekly Product Pulse (M2)</em> to brief the <em>Voice Booking Agent (M3)</em>.
      The agent is <strong>Theme-Aware</strong>: if the Pulse found "Login Issues" or
      "Nominee Updates" as top themes, the agent proactively mentions them during the
      greeting — e.g. <em>"I see many users are asking about Nominee Updates today;
      I can help you book a call for that!"</em>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)
        _state_file = Path("data/system_state.json")
        if _state_file.exists():
            try:
                _st = json.loads(_state_file.read_text())
                if _st.get("last_pipeline_run"):
                    from datetime import datetime as _dt
                    _ts = _dt.fromisoformat(_st["last_pipeline_run"]).strftime("%d %b %Y, %I:%M %p")
                    st.caption(f"Last run: {_ts} · {_st.get('last_review_count','—')} reviews")
            except Exception:
                pass
    with _col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        _run_pipeline = st.button("▶ Run Pipeline", key="run_pipeline_tab2", type="primary")

    # ── Run pipeline inline ──────────────────────────────────────────────────
    if _run_pipeline:
        _log_area = st.empty()
        _logs: list[str] = []

        def _pipeline_cb(msg: str) -> None:
            _logs.append(msg)
            _log_area.info("\n\n".join(_logs))

        with st.spinner("Scraping reviews and running pipeline…"):
            try:
                _result = _run_full_pipeline(status_cb=_pipeline_cb)
                _pulse = _result["pulse"]
                _top3  = _pulse.get("top_3_themes", [])
                st.session_state["weekly_pulse"]    = _pulse.get("weekly_note", "")
                st.session_state["top_theme"]       = _top3[0] if _top3 else "General Feedback"
                st.session_state["top_3_themes"]    = _top3
                st.session_state["action_ideas"]    = _pulse.get("action_ideas", [])
                st.session_state["fee_bullets"]     = _result["fee"].get("bullets", [])
                st.session_state["fee_sources"]     = _result["fee"].get("sources", [])
                st.session_state["pulse_generated"] = True
                st.session_state["analytics_data"]  = _result["analytics"]
                _log_area.empty()
                st.success(f"✅ Pipeline complete — {_pulse.get('review_count','?')} reviews processed.")
                st.rerun()
            except Exception as _exc:
                _log_area.empty()
                st.error(f"Pipeline failed: {_exc}")

    # ── Seed session state from saved JSONs (handles page reloads) ─────────────
    if not st.session_state.get("pulse_generated"):
        try:
            _p = json.loads(Path("data/pulse_latest.json").read_text())
            _f = json.loads(Path("data/fee_latest.json").read_text()) if Path("data/fee_latest.json").exists() else {}
            _top3 = _p.get("top_3_themes", [])
            st.session_state["weekly_pulse"]    = _p.get("weekly_note", "")
            st.session_state["top_theme"]       = _top3[0] if _top3 else "General Feedback"
            st.session_state["top_3_themes"]    = _top3
            st.session_state["action_ideas"]    = _p.get("action_ideas", [])
            st.session_state["fee_bullets"]     = _f.get("bullets", [])
            st.session_state["fee_sources"]     = _f.get("sources", [])
            st.session_state["pulse_generated"] = True
        except Exception:
            pass

    # ── Pulse Summary card (bridges M2 pulse → M3 voice briefing) ───────────
    _pulse_note   = st.session_state.get("weekly_pulse", "")
    _top3_display = st.session_state.get("top_3_themes", [])
    _actions      = st.session_state.get("action_ideas", [])
    if _pulse_note or _top3_display:
        with st.expander("📊 Weekly Pulse Summary — feeds Voice Agent briefing", expanded=True):
            _ps_col1, _ps_col2 = st.columns([3, 2])
            with _ps_col1:
                st.markdown("**Weekly Note**")
                _note_text = _pulse_note[:600] if _pulse_note else "—"
                st.markdown(
                    f'<div style="font-size:0.875rem;line-height:1.7;color:var(--text-2);'
                    f'background:var(--bg-glass);border-radius:8px;'
                    f'padding:12px 16px;border:1px solid var(--border);">'
                    f'{_note_text}</div>',
                    unsafe_allow_html=True,
                )
            with _ps_col2:
                if _top3_display:
                    st.markdown("**Top Themes → Voice Agent Briefing**")
                    for _i, _th in enumerate(_top3_display[:3], 1):
                        _chip_c  = "#C9A84C" if _i == 1 else "#7EB6FF"
                        _rgb     = "201,168,76" if _i == 1 else "126,182,255"
                        _weight  = "700" if _i == 1 else "500"
                        _tag     = '&nbsp;<span style="font-size:0.7rem;color:#22C55E;">↑ Agent greeting</span>' if _i == 1 else ""
                        st.markdown(
                            f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0;font-size:0.875rem;">'
                            f'<span style="background:rgba({_rgb},0.15);color:{_chip_c};padding:2px 10px;'
                            f'border-radius:100px;border:1px solid rgba({_rgb},0.35);'
                            f'font-weight:{_weight};white-space:nowrap;">#{_i} {_th}</span>'
                            f'{_tag}</div>',
                            unsafe_allow_html=True,
                        )
                if _actions:
                    st.markdown("**Action Ideas**")
                    for _act in _actions[:3]:
                        st.markdown(f"- {_act}")
            st.info(
                "✉️ Email draft and notes entry have been **queued for approval** in "
                "the **Super-Agent MCP Workflow** tab — no auto-send.",
                icon=None,
            )

    # ── Voice Agent section ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Voice Appointment Booking")

    # Init session keys
    for _k2, _v2 in {
        "va2_agent_speech": "", "va2_user_text": "", "va2_tts_audio": None,
        "va2_tts_played": "", "va2_last_audio_hash": "", "va2_backend_status": "",
    }.items():
        if _k2 not in st.session_state:
            st.session_state[_k2] = _v2

    pulse_ready = st.session_state.get("pulse_generated", False)
    top_theme   = st.session_state.get("top_theme", "")

    if pulse_ready:
        st.success(f"✓ Pulse generated. Top theme this week: **{top_theme}**")
    else:
        st.warning("⚠ Generate a Weekly Pulse first. Click ▶ Run Pipeline above.")

    # Topic chips — bookable appointment options
    _chip_style = (
        "display:inline-block;padding:4px 12px;margin:3px 4px;border-radius:20px;"
        "font-size:0.78rem;font-weight:500;border:1px solid;"
    )
    _chips_html = ""
    if top_theme:
        _chips_html += (
            f'<span style="{_chip_style}background:rgba(201,168,76,0.18);'
            f'border-color:rgba(201,168,76,0.55);color:#C9A84C;">'
            f'📌 Top theme this week: {top_theme}</span>'
        )
    for _lbl in [
        "KYC and Onboarding",
        "SIP and Mandates",
        "Statements and Tax",
        "Withdrawals and Timelines",
        "Account Changes and Nominee Updates",
    ]:
        _chips_html += (
            f'<span style="{_chip_style}background:var(--bg-glass);'
            f'border-color:var(--border);color:var(--text-2);">{_lbl}</span>'
        )
    st.markdown(
        f'<div style="margin:8px 0 14px;line-height:2;">{_chips_html}</div>',
        unsafe_allow_html=True,
    )

    _va2_l, _va2_c, _va2_r = st.columns([3, 2, 3])
    with _va2_c:
        if pulse_ready and "voice_agent" not in st.session_state:
            if st.button("▶ Start Call", key="start_call_btn", type="primary", use_container_width=True):
                st.session_state["voice_agent"] = VoiceAgent(
                    session=st.session_state,
                    calendar_path="data/mock_calendar.json",
                )
                greeting_text, greeting_audio = st.session_state["voice_agent"].get_greeting()
                st.session_state["va2_agent_speech"] = greeting_text
                st.session_state["va2_tts_audio"]    = greeting_audio
                st.session_state["va2_tts_played"]   = ""
                st.rerun()
        elif "voice_agent" in st.session_state:
            if st.button("End Call", key="end_call_btn", type="secondary", use_container_width=True):
                for _k in ["voice_agent", "va2_agent_speech", "va2_user_text", "va2_tts_audio",
                           "va2_tts_played", "va2_last_audio_hash", "va2_backend_status"]:
                    st.session_state.pop(_k, None)
                st.rerun()

    if "voice_agent" in st.session_state:
        agent  = st.session_state["voice_agent"]
        speech = st.session_state.get("va2_agent_speech", "")
        _is_terminal = agent.state in ("BOOKED", "WAITLIST")

        # Transcript — Agent + User last turn
        _va2_user = st.session_state.get("va2_user_text", "")
        if speech or _va2_user:
            _a_txt = speech if speech else "—"
            _u_txt = _va2_user if _va2_user else "—"
            st.markdown(f"""
<div style="max-width:560px;margin:6px auto 2px;padding:10px 14px;border-radius:10px;
     background:var(--bg-glass);border:1px solid var(--border);font-size:0.82rem;">
  <div style="color:var(--text-3);font-size:0.68rem;text-transform:uppercase;
       letter-spacing:0.07em;margin-bottom:8px;">Transcript</div>
  <div style="margin-bottom:6px;max-height:120px;overflow-y:auto;">
    <span style="color:var(--gold-1);font-weight:600;min-width:52px;display:inline-block;vertical-align:top;">Agent</span>
    <span style="color:var(--text-1);white-space:pre-wrap;">{_a_txt}</span>
  </div>
  <div style="max-height:60px;overflow-y:auto;">
    <span style="color:#7EB6FF;font-weight:600;min-width:52px;display:inline-block;vertical-align:top;">You</span>
    <span style="color:var(--text-1);">{_u_txt}</span>
  </div>
</div>""", unsafe_allow_html=True)

        # Backend status + VAD pill
        _bs = st.session_state.get("va2_backend_status", "")
        if _bs:
            st.markdown(f'<div class="va2-status">{_bs}</div>', unsafe_allow_html=True)
        st.markdown('<div style="text-align:center;margin:6px 0 4px;">'
                    '<span id="va2-vad-status" class="va2-vad-pill">&nbsp;</span></div>',
                    unsafe_allow_html=True)

        # ── TTS auto-play + VAD trigger ──────────────────────────────────────
        if speech:
            _turn_key = hashlib.md5(f"{agent.state}:{speech}".encode()).hexdigest()[:16]
            audio_bytes = st.session_state.get("va2_tts_audio")

            # Compute TTS only when step() didn't return audio (shouldn't happen, but safe)
            if not audio_bytes:
                try:
                    from phase6_pillar_b_voice.voice.tts_engine import TTSEngine
                    _r = TTSEngine().synthesise(speech, language="en-IN")
                    audio_bytes = _r.audio_bytes if not _r.is_empty else None
                except Exception:
                    try:
                        from gtts import gTTS
                        _buf = io.BytesIO()
                        gTTS(text=speech, lang="en", tld="co.in", slow=False).write_to_fp(_buf)
                        _buf.seek(0)
                        audio_bytes = _buf.read()
                    except Exception:
                        audio_bytes = None
                st.session_state["va2_tts_audio"] = audio_bytes

            if audio_bytes and st.session_state["va2_tts_played"] != _turn_key:
                st.session_state["va2_tts_played"] = _turn_key
                if _is_terminal:
                    _va2_autoplay_js(audio_bytes)          # play only, no mic
                else:
                    _va2_play_and_listen_js(audio_bytes, turn_id=_turn_key)  # play → wait → listen

        # ── Hidden mic input (VAD controls it via JS) ────────────────────────
        if not _is_terminal:
            _mic_in = st.audio_input("va2_mic", key="va2_audio_input", label_visibility="hidden")
            if _mic_in is not None:
                _ab    = _mic_in.read()
                _ahash = hashlib.md5(_ab).hexdigest()
                if st.session_state.get("va2_last_audio_hash") != _ahash:
                    st.session_state["va2_last_audio_hash"] = _ahash
                    if len(_ab) >= 8_000:
                        st.session_state["va2_backend_status"] = "Transcribing speech…"
                        transcript = _va2_stt(_ab)
                        _repeat_words = ["repeat","again","say that again","pardon","sorry","excuse me","come again","huh","what"]
                        if any(w in transcript.lower() for w in _repeat_words) and len(transcript) < 40:
                            st.session_state["va2_tts_played"] = ""   # replay last response
                        else:
                            st.session_state["va2_backend_status"] = "Processing…"
                            st.session_state["va2_user_text"] = transcript or ""
                            resp_text, resp_audio = agent.step(transcript or "")
                            st.session_state["va2_agent_speech"]  = resp_text
                            st.session_state["va2_tts_audio"]     = resp_audio
                            st.session_state["va2_tts_played"]    = ""
                            st.session_state["va2_backend_status"] = ""
                    st.rerun()

        # ── Terminal state banner ────────────────────────────────────────────
        if _is_terminal:
            code = st.session_state.get("booking_code", "N/A")
            st.success(f"✓ Appointment booked! Code: **{code}**")
            st.info("Check the **Super-Agent MCP Workflow** tab to review and approve calendar, notes, and email.")

    # ── Full Analytics Dashboard (collapsed — available for deep review) ─────
    st.markdown("---")
    _dashboard = Path("data/dashboard.html")
    _DASHBOARD_LIGHT_CSS = """<style>
body{background:linear-gradient(135deg,#e8f0fe 0%,#dce8fb 50%,#e4eaf5 100%)!important;color:#1a2340!important;}
.glass-card{background:rgba(255,255,255,0.72)!important;backdrop-filter:blur(10px);border:1px solid rgba(0,0,0,0.08)!important;}
.blob-1{background:rgba(166,124,0,0.12)!important;}.blob-2{background:rgba(100,140,200,0.18)!important;}
.tabs{background:rgba(255,255,255,0.45)!important;border-color:rgba(0,0,0,0.08)!important;}
.tab-btn{color:rgba(26,35,64,0.6)!important;}
.tab-btn.active{background:linear-gradient(135deg,#3b5bdb,#2d4aa8)!important;color:#fff!important;}
.tab-btn:hover:not(.active){background:rgba(0,0,0,0.06)!important;color:#1a2340!important;}
.draft-box{background:rgba(0,0,0,0.05)!important;color:rgba(26,35,64,0.85)!important;border-color:rgba(0,0,0,0.08)!important;}
.markdown-box p,.markdown-box ul,.markdown-box li{color:rgba(26,35,64,0.8)!important;}
.markdown-box h1,.markdown-box h2,.markdown-box h3,.markdown-box strong{color:#1a2340!important;}
.markdown-box code{background:rgba(0,0,0,0.07)!important;color:rgba(26,35,64,0.85)!important;}
.note-text,.action-text{color:rgba(26,35,64,0.85)!important;}
.quote-card{background:rgba(255,255,255,0.6)!important;color:rgba(26,35,64,0.85)!important;border-color:#3b5bdb!important;}
.poster-section h3{color:rgba(26,35,64,0.5)!important;}
.pill{background:rgba(59,91,219,0.12)!important;border-color:rgba(59,91,219,0.35)!important;color:#3b5bdb!important;}
header h1{background:linear-gradient(135deg,#1a2340,#3b5bdb)!important;-webkit-background-clip:text!important;-webkit-text-fill-color:transparent!important;}
header p,header a{color:rgba(26,35,64,0.6)!important;}
.status-pill{background:rgba(22,101,52,0.12)!important;border-color:rgba(22,101,52,0.35)!important;color:#166534!important;}
.review-badge{background:rgba(59,91,219,0.12)!important;border-color:rgba(59,91,219,0.35)!important;color:#3b5bdb!important;}
</style>"""

    with st.expander("📊 Full Analytics Dashboard", expanded=False):
        if _dashboard.exists():
            _dash_html = _dashboard.read_text(encoding="utf-8")
            if _is_light:
                _dash_html = _dash_html.replace("</head>", _DASHBOARD_LIGHT_CSS + "</head>", 1)
            components.html(_dash_html, height=960, scrolling=True)
        else:
            st.markdown("""
            <div style="text-align:center;padding:60px 20px;color:var(--text-3);">
              <div style="font-size:2.5rem">📭</div>
              <h3 style="color:var(--text-2) !important;font-size:1.2rem;">No dashboard data yet</h3>
              <p style="color:var(--text-3);">Click <strong style="color:var(--gold-1);">▶ Run Pipeline</strong> above
              to scrape this week's INDMoney reviews and generate the full dashboard.</p>
            </div>
            """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# Tab 3 — Super-Agent MCP Workflow
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("""
<div class="pillar-header">
  <h3 style="margin:0;color:var(--text-1);">The Super-Agent MCP Workflow</h3>
  <div class="pillar-tooltip">
    <div class="info-chip">
      <span class="info-circle">i</span>Pillar C · M2 + M3 · HITL
    </div>
    <div class="pillar-tooltip-body">
      <span style="color:#E8C96D;font-weight:700;">Pillar C — Super-Agent MCP Workflow</span>
      <br><br>
      Consolidates all MCP actions into a single <strong>Human-in-the-Loop (HITL)
      Approval Center</strong>. When a voice call ends (M3), the system generates a
      Calendar Hold, a Notes entry, and an Email Draft. The Email Draft is enriched
      with a <em>Market Context snippet</em> from the Weekly Pulse (M2) — so the
      advisor sees current customer sentiment before the meeting.
      <br><br>
      Nothing executes until you approve it here.
    </div>
  </div>
</div>
<p style="color:var(--text-2);font-size:0.875rem;margin:6px 0 16px;">
  Review and approve all AI-generated actions before they execute.
  Calendar holds, notes entries, and advisor emails — all gated here.
</p>
""", unsafe_allow_html=True)

    # ── Market Context card ──────────────────────────────────────────────────
    _pulse_text   = st.session_state.get("weekly_pulse", "")
    _fee_bullets  = st.session_state.get("fee_bullets", [])

    # Fallback: load from saved JSON if session is fresh
    if not _pulse_text:
        try:
            _p2 = json.loads(Path("data/pulse_latest.json").read_text())
            _pulse_text = _p2.get("weekly_note", "")
        except Exception:
            pass
    if not _fee_bullets:
        try:
            _f2 = json.loads(Path("data/fee_latest.json").read_text())
            _fee_bullets = _f2.get("bullets", [])
        except Exception:
            pass

    if _pulse_text or _fee_bullets:
        _pulse_snippet = " ".join(_pulse_text.split()[:80]) + ("…" if len(_pulse_text.split()) > 80 else "")
        _fee_snippet   = "; ".join(_fee_bullets[:3]) if _fee_bullets else ""

        _mctx_html = '<div class="mctx-card">'
        _mctx_html += '<div class="mctx-label">📊 Market Context — injected into advisor email draft</div>'
        if _pulse_snippet:
            _mctx_html += f'<div class="mctx-text" style="margin-bottom:8px;">{_pulse_snippet}</div>'
        if _fee_snippet:
            _mctx_html += (
                f'<div class="mctx-text" style="font-size:0.78rem;color:var(--text-3);">'
                f'💰 Fee snapshot: {_fee_snippet}</div>'
            )
        _mctx_html += '</div>'
        st.markdown(_mctx_html, unsafe_allow_html=True)
    else:
        st.info(
            "📊 No Market Context yet — run **▶ Run Pipeline** in the "
            "Insight-Driven Optimization tab to generate the Weekly Pulse first."
        )

    st.markdown("---")

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
      <a href="javascript:void(0)">Smart-Sync Knowledge Base</a>
      <a href="javascript:void(0)">Insight-Driven Optimization</a>
      <a href="javascript:void(0)">Voice Booking Agent</a>
      <a href="javascript:void(0)">Super-Agent MCP Workflow</a>
      <a href="javascript:void(0)">NAV Tracker</a>
    </div>
    <div class="dsa-footer-col">
      <h4>Funds Covered</h4>
      <a href="https://www.sbimf.com/en-us/sbi-bluechip-fund" target="_blank" rel="noopener">SBI Large Cap</a>
      <a href="https://www.sbimf.com/en-us/sbi-long-term-equity-fund" target="_blank" rel="noopener">SBI ELSS</a>
      <a href="https://www.sbimf.com/en-us/sbi-small-cap-fund" target="_blank" rel="noopener">SBI Small Cap</a>
      <a href="https://www.sbimf.com/en-us/sbi-flexicap-fund" target="_blank" rel="noopener">SBI Flexicap</a>
      <a href="https://www.sbimf.com/en-us/sbi-magnum-midcap-fund" target="_blank" rel="noopener">SBI Midcap</a>
    </div>
    <div class="dsa-footer-col">
      <h4>Technology</h4>
      <a href="https://www.anthropic.com/claude" target="_blank" rel="noopener">Claude Sonnet 4.6</a>
      <a href="https://www.trychroma.com/" target="_blank" rel="noopener">ChromaDB RAG</a>
      <a href="https://modelcontextprotocol.io/" target="_blank" rel="noopener">MCP Protocol</a>
      <a href="https://www.sbert.net/" target="_blank" rel="noopener">Sentence Transformers</a>
      <a href="https://streamlit.io/" target="_blank" rel="noopener">Streamlit</a>
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
