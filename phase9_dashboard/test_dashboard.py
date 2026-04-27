"""Phase 9 — Internal Developer / Test Dashboard.

Run: streamlit run test_dashboard.py

One tab per phase (Phase 1–8) + Overview tab.
Each tab shows: PRD summary, Run Tests button, test results, phase gate status.
Overview tab shows all-phase status table + Run All Evals button.
"""
import json
import subprocess
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="Dev Dashboard — Phase 9",
    page_icon="🔬",
    layout="wide",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.badge-green  { background:#14532d;color:#4ade80;padding:3px 10px;border-radius:10px;font-size:0.78rem; }
.badge-yellow { background:#713f12;color:#fbbf24;padding:3px 10px;border-radius:10px;font-size:0.78rem; }
.badge-red    { background:#7f1d1d;color:#f87171;padding:3px 10px;border-radius:10px;font-size:0.78rem; }
.prd-block    { background:#1e293b;border-left:3px solid #334155;padding:12px 16px;border-radius:6px; }
.result-box   { background:#0f172a;border:1px solid #334155;border-radius:6px;
                padding:12px;font-family:monospace;font-size:0.78rem;white-space:pre-wrap;
                max-height:300px;overflow-y:auto; }
</style>
""", unsafe_allow_html=True)

# ── Phase definitions ─────────────────────────────────────────────────────────
PHASES = [
    {
        "num": 1, "name": "Foundation",
        "dir": "phase1_foundation",
        "test_path": "phase1_foundation/tests/",
        "eval_path": None,
        "prd_file": "phase1_foundation/prd/prd.md",
        "code_modules": ["config.py", "session_init.py"],
    },
    {
        "num": 2, "name": "Corpus — Pillar A",
        "dir": "phase2_corpus_pillar_a",
        "test_path": "phase2_corpus_pillar_a/tests/",
        "eval_path": None,
        "prd_file": "phase2_corpus_pillar_a/prd/prd.md",
        "code_modules": ["ingest.py", "chunker.py", "embedder.py", "url_loader.py"],
    },
    {
        "num": 3, "name": "Review Pipeline — Pillar B",
        "dir": "phase3_review_pillar_b",
        "test_path": "phase3_review_pillar_b/tests/",
        "eval_path": None,
        "prd_file": "phase3_review_pillar_b/prd/prd.md",
        "code_modules": ["pii_scrubber.py", "theme_clusterer.py", "quote_extractor.py",
                         "pulse_writer.py", "fee_explainer.py", "pipeline_orchestrator.py"],
    },
    {
        "num": 4, "name": "Voice Agent — Pillar B",
        "dir": "phase4_voice_pillar_b",
        "test_path": "phase4_voice_pillar_b/tests/",
        "eval_path": None,
        "prd_file": "phase4_voice_pillar_b/prd/prd.md",
        "code_modules": ["intent_classifier.py", "slot_filler.py", "booking_engine.py", "voice_agent.py"],
    },
    {
        "num": 5, "name": "FAQ Engine — Pillar A",
        "dir": "phase5_pillar_a_faq",
        "test_path": "phase5_pillar_a_faq/tests/",
        "eval_path": None,
        "prd_file": "phase5_pillar_a_faq/prd/prd.md",
        "code_modules": ["safety_filter.py", "query_router.py", "retriever.py",
                         "llm_fusion.py", "faq_engine.py"],
    },
    {
        "num": 6, "name": "Voice Integration",
        "dir": "phase6_pillar_b_voice",
        "test_path": "phase6_pillar_b_voice/tests/",
        "eval_path": "phase6_pillar_b_voice/evals/eval_integration.py",
        "prd_file": "phase6_pillar_b_voice/prd/prd.md",
        "code_modules": [],
    },
    {
        "num": 7, "name": "HITL Approval — Pillar C",
        "dir": "phase7_pillar_c_hitl",
        "test_path": "phase7_pillar_c_hitl/tests/",
        "eval_path": None,
        "prd_file": "phase7_pillar_c_hitl/prd/prd.md",
        "code_modules": ["mcp_client.py", "email_builder.py", "hitl_panel.py"],
    },
    {
        "num": 8, "name": "Eval Suite",
        "dir": "phase8_eval_suite",
        "test_path": "phase8_eval_suite/tests/",
        "eval_path": "phase8_eval_suite/evals/run_evals.py",
        "prd_file": "phase8_eval_suite/prd/prd.md",
        "code_modules": ["evals/run_evals.py", "evals/safety_eval.py",
                         "evals/rag_eval.py", "evals/ux_eval.py"],
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_pytest(test_path: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short", "-q",
         "--json-report", "--json-report-file=-"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    passed = failed = 0
    for line in result.stdout.splitlines():
        if " passed" in line:
            try:
                passed = int(line.strip().split(" passed")[0].split()[-1])
            except ValueError:
                pass
        if " failed" in line:
            try:
                failed = int(line.strip().split(" failed")[0].split()[-1])
            except ValueError:
                pass
    return {
        "stdout":   result.stdout,
        "stderr":   result.stderr,
        "returncode": result.returncode,
        "passed":   passed,
        "failed":   failed,
    }


def _run_eval(eval_path: str) -> dict:
    result = subprocess.run(
        [sys.executable, eval_path],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    return {
        "stdout":     result.stdout,
        "stderr":     result.stderr,
        "returncode": result.returncode,
    }


def _read_prd_summary(prd_file: str, max_lines: int = 20) -> str:
    path = ROOT / prd_file
    if not path.exists():
        return "_PRD file not found._"
    lines = path.read_text().splitlines()
    return "\n".join(lines[:max_lines])


def _gate_badge(passed: int, failed: int, ran: bool) -> str:
    if not ran:
        return '<span class="badge-yellow">🟡 Not Run</span>'
    if failed == 0 and passed > 0:
        return '<span class="badge-green">🟢 Complete</span>'
    if passed == 0:
        return '<span class="badge-red">🔴 Failing</span>'
    return '<span class="badge-yellow">🟡 Partial</span>'


def _code_files_status(phase_dir: str, modules: list[str]) -> list[dict]:
    rows = []
    for m in modules:
        p = ROOT / phase_dir / m
        rows.append({"file": m, "exists": p.exists()})
    return rows


# ── Session keys ──────────────────────────────────────────────────────────────
for ph in PHASES:
    k = f"p{ph['num']}_result"
    if k not in st.session_state:
        st.session_state[k] = None
    ek = f"p{ph['num']}_eval"
    if ek not in st.session_state:
        st.session_state[ek] = None

# ── Title ─────────────────────────────────────────────────────────────────────
st.title("🔬 Phase 9 — Internal Developer Dashboard")
st.caption("Run tests, check eval scores, and verify phase gate status for each build phase.")
st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_labels = ["📋 Overview"] + [f"Phase {p['num']}" for p in PHASES]
tabs = st.tabs(tab_labels)

# ════════════════════════════════════════════════════════════════════════════
# OVERVIEW TAB
# ════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.markdown("### System Overview — All Phases")

    if st.button("🚀 Run All Tests", type="primary", key="run_all"):
        results = {}
        prog = st.progress(0, text="Running tests across all phases…")
        for i, ph in enumerate(PHASES):
            r = _run_pytest(ph["test_path"])
            st.session_state[f"p{ph['num']}_result"] = r
            results[ph["num"]] = r
            prog.progress((i + 1) / len(PHASES), text=f"Phase {ph['num']} done")
        prog.empty()
        st.rerun()

    col_run_evals, _ = st.columns([1, 3])
    with col_run_evals:
        if st.button("📊 Run All Evals", key="run_all_evals"):
            eval_path = ROOT / "phase8_eval_suite" / "evals" / "run_evals.py"
            with st.spinner("Running full eval suite…"):
                r = _run_eval(str(eval_path))
            st.session_state["p8_eval"] = r
            if r["returncode"] == 0:
                st.success("✅ All evals passed")
            else:
                st.warning("⚠ Some evals failed — see Phase 8 tab")

    st.markdown("---")

    # Summary table
    table_data = []
    for ph in PHASES:
        result = st.session_state.get(f"p{ph['num']}_result")
        passed = result["passed"] if result else 0
        failed = result["failed"] if result else 0
        ran = result is not None

        code_files = _code_files_status(ph["dir"], ph["code_modules"])
        files_ok = sum(1 for f in code_files if f["exists"])
        files_total = len(code_files)

        table_data.append({
            "Phase": f"Phase {ph['num']}",
            "Name": ph["name"],
            "Code Files": f"{files_ok}/{files_total}" if files_total else "N/A",
            "Tests": f"{passed}✅ {failed}❌" if ran else "—",
            "Status": ("🟢 Pass" if ran and failed == 0 and passed > 0
                       else "🔴 Fail" if ran and failed > 0
                       else "⚪ Not Run"),
        })

    import pandas as pd
    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # EVALS_REPORT.md if present
    report = ROOT / "EVALS_REPORT.md"
    if report.exists():
        with st.expander("📄 Last EVALS_REPORT.md"):
            st.markdown(report.read_text())


# ════════════════════════════════════════════════════════════════════════════
# PHASE TABS (1–8)
# ════════════════════════════════════════════════════════════════════════════
for tab, ph in zip(tabs[1:], PHASES):
    with tab:
        st.markdown(f"### Phase {ph['num']} — {ph['name']}")

        col_left, col_right = st.columns([2, 1])

        with col_left:
            # PRD summary
            st.markdown("**PRD Summary**")
            prd_text = _read_prd_summary(ph["prd_file"])
            st.markdown(
                f'<div class="prd-block"><pre style="color:#94a3b8;font-size:0.8rem;'
                f'white-space:pre-wrap">{prd_text}</pre></div>',
                unsafe_allow_html=True,
            )

        with col_right:
            # Code files status
            st.markdown("**Code Files**")
            for f in _code_files_status(ph["dir"], ph["code_modules"]):
                icon = "✅" if f["exists"] else "❌"
                st.caption(f"{icon} {f['file']}")

            if not ph["code_modules"]:
                st.caption("_(wiring only — no phase-specific code)_")

        st.markdown("---")

        # Test runner
        btn_col, status_col = st.columns([1, 3])
        with btn_col:
            if st.button(f"▶ Run Tests", key=f"run_p{ph['num']}"):
                with st.spinner(f"Running pytest {ph['test_path']}…"):
                    r = _run_pytest(ph["test_path"])
                st.session_state[f"p{ph['num']}_result"] = r

        result = st.session_state.get(f"p{ph['num']}_result")
        with status_col:
            if result:
                badge = _gate_badge(result["passed"], result["failed"], ran=True)
                st.markdown(
                    f'{badge} &nbsp; **{result["passed"]} passed** / {result["failed"]} failed',
                    unsafe_allow_html=True,
                )

        if result:
            with st.expander("📋 Test Output", expanded=(result["failed"] > 0)):
                st.markdown(
                    f'<div class="result-box">{result["stdout"]}</div>',
                    unsafe_allow_html=True,
                )
                if result["stderr"]:
                    st.caption("stderr:")
                    st.markdown(
                        f'<div class="result-box">{result["stderr"][:2000]}</div>',
                        unsafe_allow_html=True,
                    )

        # Eval runner (only phases that have eval scripts)
        if ph["eval_path"]:
            st.markdown("---")
            if st.button(f"📊 Run Eval", key=f"eval_p{ph['num']}"):
                eval_full = str(ROOT / ph["eval_path"])
                with st.spinner("Running eval…"):
                    er = _run_eval(eval_full)
                st.session_state[f"p{ph['num']}_eval"] = er

            eval_result = st.session_state.get(f"p{ph['num']}_eval")
            if eval_result:
                if eval_result["returncode"] == 0:
                    st.success("✅ Eval passed")
                else:
                    st.warning("⚠ Eval issues detected")
                with st.expander("📋 Eval Output"):
                    st.markdown(
                        f'<div class="result-box">{eval_result["stdout"]}</div>',
                        unsafe_allow_html=True,
                    )
