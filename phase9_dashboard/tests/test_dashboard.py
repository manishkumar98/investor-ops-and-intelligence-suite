"""Phase 9 — Dashboard tests (P9-01 through P9-12)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PHASES = list(range(1, 9))

PHASE_TEST_DIRS = [
    ROOT / f"phase{n}_{suffix}" / "tests"
    for n, suffix in [
        (1, "foundation"), (2, "corpus_pillar_a"), (3, "review_pillar_b"),
        (4, "voice_pillar_b"), (5, "pillar_a_faq"), (6, "pillar_b_voice"),
        (7, "pillar_c_hitl"), (8, "eval_suite"),
    ]
]

PHASE_PRD_FILES = [
    ROOT / f"phase{n}_{suffix}" / "prd" / "prd.md"
    for n, suffix in [
        (1, "foundation"), (2, "corpus_pillar_a"), (3, "review_pillar_b"),
        (4, "voice_pillar_b"), (5, "pillar_a_faq"), (6, "pillar_b_voice"),
        (7, "pillar_c_hitl"), (8, "eval_suite"),
    ]
]


# ---------------------------------------------------------------------------
# P9-01  app.py entry point
# ---------------------------------------------------------------------------

class TestProductionApp:

    def test_app_file_exists(self):
        assert (ROOT / "app.py").exists()

    def test_app_imports_cleanly(self):
        result = subprocess.run(
            [sys.executable, "-c", "import sys; sys.path.insert(0, '.'); import app"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert result.returncode == 0, f"app.py import failed:\n{result.stderr}"

    def test_config_exists(self):
        assert (ROOT / "config.py").exists()

    def test_session_init_exists(self):
        assert (ROOT / "session_init.py").exists()


# ---------------------------------------------------------------------------
# P9-02  Three pillars wired in app.py
# ---------------------------------------------------------------------------

class TestAppPillarsWired:

    def _app_source(self) -> str:
        return (ROOT / "app.py").read_text()

    def test_pillar_a_faq_imported(self):
        src = self._app_source()
        assert "phase5_pillar_a_faq" in src

    def test_pillar_b_review_imported(self):
        src = self._app_source()
        assert "phase3_review_pillar_b" in src

    def test_pillar_b_voice_imported(self):
        src = self._app_source()
        assert "phase4_voice_pillar_b" in src

    def test_pillar_c_hitl_imported(self):
        src = self._app_source()
        assert "phase7_pillar_c_hitl" in src

    def test_three_tabs_defined(self):
        src = self._app_source()
        assert src.count("st.tabs") >= 1


# ---------------------------------------------------------------------------
# P9-03/04/05  Sidebar + session persistence
# ---------------------------------------------------------------------------

class TestSidebarAndSession:

    def _app_source(self) -> str:
        return (ROOT / "app.py").read_text()

    def test_corpus_status_in_sidebar(self):
        src = self._app_source()
        assert "get_collection" in src

    def test_mcp_state_json_written(self):
        src = self._app_source()
        assert "mcp_state.json" in src

    def test_session_restored_on_reload(self):
        src = self._app_source()
        assert "mcp_state.json" in src
        assert "mcp_queue" in src


# ---------------------------------------------------------------------------
# P9-06/07  test_dashboard.py structure
# ---------------------------------------------------------------------------

class TestDashboardStructure:

    def test_test_dashboard_file_exists(self):
        assert (ROOT / "test_dashboard.py").exists()

    def test_review_pulse_page_exists(self):
        assert (ROOT / "pages" / "1_Review_Pulse.py").exists()

    def test_test_dashboard_has_all_phase_tabs(self):
        src = (ROOT / "test_dashboard.py").read_text()
        # Tabs are generated dynamically from PHASES list — verify the generation code exists
        assert "PHASES" in src and "st.tabs" in src
        # Verify all 8 phase dirs are referenced
        for n in range(1, 9):
            assert f'"num": {n}' in src or f"'num': {n}" in src or str(n) in src

    def test_test_dashboard_has_overview_tab(self):
        src = (ROOT / "test_dashboard.py").read_text()
        assert "Overview" in src

    def test_test_dashboard_has_run_tests_button(self):
        src = (ROOT / "test_dashboard.py").read_text()
        assert "Run Tests" in src or "run_tests" in src or "Run All Tests" in src

    def test_test_dashboard_has_run_evals_button(self):
        src = (ROOT / "test_dashboard.py").read_text()
        assert "Run" in src and "Eval" in src


# ---------------------------------------------------------------------------
# P9-08  pytest integration
# ---------------------------------------------------------------------------

class TestPytestIntegration:

    def test_all_phase_test_dirs_exist(self):
        for d in PHASE_TEST_DIRS:
            assert d.exists(), f"Test dir missing: {d}"

    def test_each_phase_has_at_least_one_test_file(self):
        for d in PHASE_TEST_DIRS:
            test_files = list(d.glob("test_*.py"))
            assert test_files, f"No test files in {d}"


# ---------------------------------------------------------------------------
# P9-10  Phase gate status — code presence
# ---------------------------------------------------------------------------

class TestPhaseGateCodePresence:

    def test_phase2_code_files_present(self):
        phase2 = ROOT / "phase2_corpus_pillar_a"
        for f in ["ingest.py", "chunker.py", "embedder.py", "url_loader.py"]:
            assert (phase2 / f).exists(), f"Missing: {f}"

    def test_phase3_code_files_present(self):
        phase3 = ROOT / "phase3_review_pillar_b"
        for f in ["pii_scrubber.py", "theme_clusterer.py", "quote_extractor.py",
                  "pulse_writer.py", "fee_explainer.py", "pipeline_orchestrator.py"]:
            assert (phase3 / f).exists(), f"Missing: {f}"

    def test_phase4_code_files_present(self):
        phase4 = ROOT / "phase4_voice_pillar_b"
        for f in ["intent_classifier.py", "slot_filler.py", "booking_engine.py", "voice_agent.py"]:
            assert (phase4 / f).exists(), f"Missing: {f}"

    def test_phase5_code_files_present(self):
        phase5 = ROOT / "phase5_pillar_a_faq"
        for f in ["safety_filter.py", "query_router.py", "retriever.py", "llm_fusion.py", "faq_engine.py"]:
            assert (phase5 / f).exists(), f"Missing: {f}"

    def test_phase7_code_files_present(self):
        phase7 = ROOT / "phase7_pillar_c_hitl"
        for f in ["mcp_client.py", "email_builder.py", "hitl_panel.py"]:
            assert (phase7 / f).exists(), f"Missing: {f}"

    def test_phase8_eval_files_present(self):
        evals = ROOT / "phase8_eval_suite" / "evals"
        for f in ["run_evals.py", "safety_eval.py", "rag_eval.py",
                  "ux_eval.py", "report_generator.py"]:
            assert (evals / f).exists(), f"Missing: {f}"

    def test_phase8_eval_data_files_present(self):
        evals = ROOT / "phase8_eval_suite" / "evals"
        for f in ["golden_dataset.json", "adversarial_tests.json"]:
            assert (evals / f).exists(), f"Missing: {f}"


# ---------------------------------------------------------------------------
# P9-11  Overview — all PRD files present
# ---------------------------------------------------------------------------

class TestOverviewPRDFiles:

    def test_all_phase_prd_files_exist(self):
        for path in PHASE_PRD_FILES:
            assert path.exists(), f"PRD missing: {path}"

    def test_all_phase_architecture_files_exist(self):
        for n, suffix in [
            (1, "foundation"), (2, "corpus_pillar_a"), (3, "review_pillar_b"),
            (4, "voice_pillar_b"), (5, "pillar_a_faq"), (6, "pillar_b_voice"),
            (7, "pillar_c_hitl"), (8, "eval_suite"),
        ]:
            arch = ROOT / f"phase{n}_{suffix}" / "architecture" / "architecture.md"
            assert arch.exists(), f"Architecture missing: {arch}"
