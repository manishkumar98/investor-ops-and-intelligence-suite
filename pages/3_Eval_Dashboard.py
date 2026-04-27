"""Eval Dashboard — tracks all phase eval results."""
import json
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import load_env
load_env()

RESULTS_PATH = ROOT / "data" / "eval_results.json"

st.set_page_config(page_title="Eval Dashboard", page_icon="🧪", layout="wide")

# ── Minimal style ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
.metric-card{background:#10131F;border:1px solid rgba(255,255,255,.08);
  border-radius:10px;padding:16px 20px;text-align:center;}
.metric-num{font-size:2rem;font-weight:700;line-height:1.1;}
.pass{color:#22C55E;} .fail{color:#EF4444;} .warn{color:#C9A84C;}
.check-row{display:flex;align-items:center;gap:8px;padding:4px 0;
  border-bottom:1px solid rgba(255,255,255,.04);font-size:.875rem;}
</style>
""", unsafe_allow_html=True)

# ── Load cached results ───────────────────────────────────────────────────────
def _load() -> dict | None:
    if RESULTS_PATH.exists():
        try:
            return json.loads(RESULTS_PATH.read_text())
        except Exception:
            pass
    return None


def _run_quick():
    sys.path.insert(0, str(ROOT))
    from scripts.run_all_evals import run_all
    return run_all(full=False)


def _run_full():
    sys.path.insert(0, str(ROOT))
    # Pre-warm embedder silently
    import phase2_corpus_pillar_a.embedder as _emb
    _emb._openai_failed = True
    _emb.get_embeddings(["warmup"])
    from scripts.run_all_evals import run_all
    return run_all(full=True)


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🧪 Eval Dashboard")
st.caption("Tracks pass/fail for all phase evals across the Investor Ops & Intelligence Suite.")

col_q, col_f, col_sp = st.columns([1, 1, 5])
run_quick = col_q.button("▶ Run Quick Checks", type="primary",
                          help="Runs in ~5 seconds — no LLM API calls")
run_full  = col_f.button("⚡ Run Full Suite",
                          help="Includes live LLM evals for Corpus + Fee — ~2 minutes")

data = _load()

if run_quick:
    with st.spinner("Running quick checks (~5 seconds)…"):
        data = _run_quick()
    st.success("Quick checks complete.")
    st.rerun()

if run_full:
    with st.spinner("Running full eval suite including live LLM calls — this may take ~2 minutes…"):
        data = _run_full()
    st.success("Full suite complete.")
    st.rerun()

if data is None:
    st.info("No results yet. Click **Run Quick Checks** to start.")
    st.stop()

# ── Summary KPIs ──────────────────────────────────────────────────────────────
s        = data.get("summary", {})
total    = s.get("total", 0)
passed   = s.get("passed", 0)
failed   = total - passed
pct      = int(passed / total * 100) if total else 0
mode     = data.get("mode", "quick").upper()
run_at   = data.get("run_at", "")
try:
    run_at = datetime.fromisoformat(run_at).strftime("%d %b %Y %H:%M")
except Exception:
    pass

c1, c2, c3, c4 = st.columns(4)
c1.markdown(f'<div class="metric-card"><div class="metric-num pass">{pct}%</div>'
            f'<div>Pass Rate</div></div>', unsafe_allow_html=True)
c2.markdown(f'<div class="metric-card"><div class="metric-num pass">{passed}</div>'
            f'<div>Checks Passed</div></div>', unsafe_allow_html=True)
c3.markdown(f'<div class="metric-card"><div class="metric-num {"fail" if failed else "pass"}">{failed}</div>'
            f'<div>Checks Failed</div></div>', unsafe_allow_html=True)
c4.markdown(f'<div class="metric-card"><div class="metric-num warn">{total}</div>'
            f'<div>Total Checks</div></div>', unsafe_allow_html=True)

st.caption(f"Last run: **{run_at}** · Mode: **{mode}**")
st.markdown("---")

# ── Per-phase breakdown ───────────────────────────────────────────────────────
phases = data.get("phases", {})

PHASE_META = {
    "P1: Foundation":       ("🔧", "Env vars, data files, directory structure"),
    "P2: Corpus RAG":       ("📚", "ChromaDB retrieval spot-checks — requires live embeddings"),
    "P3: Review Pipeline":  ("📊", "Pulse word count, action ideas, PII [REDACTED] format, source format"),
    "P4: Voice Agent":      ("🎙️", "Booking code format, topic list, IST timezone, advice guard"),
    "P5: FAQ Safety":       ("🛡️", "Adversarial prompt blocking — 3 prompts, must refuse 100%"),
    "P5: Fee Completeness": ("💰", "Exit load + expense ratio across all 5 funds — requires LLM"),
    "P6: Voice Integration":("🔗", "Voice + Pulse integration contract"),
    "P7: HITL Approvals":   ("✅", "MCP email completeness, action gate, booking code in subject"),
    "P8: RAG Eval":         ("🎯", "Golden dataset — 5 M1+M2 questions, faithfulness + relevance — requires LLM"),
    "P8: UX Eval":          ("📐", "Pulse ≤250 words, 3 action ideas, top theme in greeting, PII [REDACTED], state persistence"),
}

for pname, phase in phases.items():
    p_passed = phase["passed"]
    p_total  = phase["total"]
    icon, desc = PHASE_META.get(pname, ("📋", ""))
    all_pass = p_passed == p_total
    badge = f"✅ {p_passed}/{p_total}" if all_pass else f"❌ {p_passed}/{p_total}"
    elapsed = phase.get("elapsed", 0)

    with st.expander(f"{icon} {pname}  —  {badge}  ({elapsed}s)", expanded=not all_pass):
        st.caption(desc)
        for chk in phase.get("checks", []):
            ok   = chk["passed"]
            mark = "✓" if ok else "✗"
            color = "#22C55E" if ok else "#EF4444"
            note = f"  <span style='color:#9A9080;font-size:.8rem'>{chk['note']}</span>" if chk.get("note") else ""
            st.markdown(
                f'<div class="check-row">'
                f'<span style="color:{color};font-weight:700;width:18px">{mark}</span>'
                f'<span>{chk["check"]}</span>{note}'
                f'</div>',
                unsafe_allow_html=True,
            )

# ── Live eval note ────────────────────────────────────────────────────────────
if data.get("mode") == "quick" and "P2: Corpus RAG" not in phases:
    st.info("**P2: Corpus RAG**, **P5: Fee Completeness**, **P8: RAG Eval**, and **P8: UX Eval** "
            "require live LLM calls. Click **Run Full Suite** to include them (≈2 min).")
