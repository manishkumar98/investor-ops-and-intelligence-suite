"""Master eval runner — produces EVALS_REPORT.md and exits 0 or 1."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from config import load_env
load_env()

from .safety_eval import run_safety_eval
from .ux_eval import run_ux_eval
from .rag_eval import run_rag_eval
from .report_generator import generate_report

from session_init import init_session_state
from phase3_review_pillar_b.pipeline_orchestrator import run_pipeline
from phase4_voice_pillar_b.voice_agent import VoiceAgent


def main() -> int:
    print("\n" + "=" * 60)
    print("Running Full Eval Suite — Investor Ops & Intelligence Suite")
    print("=" * 60)

    # ── Safety eval (hard gate — must be 3/3) ──────────────────────────────
    print("\n[1/3] Safety Eval...")
    safety_result = run_safety_eval()
    print(f"  Safety Score: {safety_result['score']}/{safety_result['total']}")

    # ── UX eval (requires populated session) ───────────────────────────────
    print("\n[2/3] UX / Structure Eval...")
    session: dict = {}
    init_session_state(session)

    try:
        run_pipeline("data/reviews_sample.csv", session)
        agent = VoiceAgent(session=session, calendar_path="data/mock_calendar.json")
    except Exception as exc:
        print(f"  WARNING: Could not populate session for UX eval: {exc}")
        agent = None

    ux_result = run_ux_eval(session, agent)
    ux_score  = sum(1 for v in ux_result.values() if v.get("passed"))
    ux_total  = len(ux_result)
    print(f"  UX Score: {ux_score}/{ux_total}")
    for check_key, check_val in ux_result.items():
        icon = "✓" if check_val.get("passed") else "✗"
        print(f"    {icon} {check_key}: {check_val.get('value', '')}")

    # ── RAG eval (requires live corpus) ────────────────────────────────────
    print("\n[3/3] RAG Faithfulness & Relevance Eval...")
    try:
        rag_result = run_rag_eval()
    except Exception as exc:
        print(f"  WARNING: RAG eval failed (corpus not loaded?): {exc}")
        rag_result = {"results": [], "faithfulness": 0, "relevance": 0, "total": 5}
    print(f"  Faithfulness: {rag_result['faithfulness']}/{rag_result['total']}")
    print(f"  Relevance:    {rag_result['relevance']}/{rag_result['total']}")

    # ── Generate report ────────────────────────────────────────────────────
    print("\nGenerating EVALS_REPORT.md...")
    generate_report(rag_result, safety_result, ux_result, str(ROOT / "EVALS_REPORT.md"))

    # ── Hard gate: safety must be 3/3 ──────────────────────────────────────
    if not safety_result["passed"]:
        print("\nFAIL: Safety eval failed. Do not ship.")
        return 1

    print("\nPASS: All hard gates passed. System is shippable.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
