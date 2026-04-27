"""Central eval runner — collects results from all phase evals and saves to data/eval_results.json.

Usage:
    python scripts/run_all_evals.py           # quick checks only (no LLM API calls)
    python scripts/run_all_evals.py --full    # includes live LLM evals (slower)
"""
import json
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import load_env
load_env()

RESULTS_PATH = ROOT / "data" / "eval_results.json"


# ── Normalise each eval's raw output to {check, passed, note} ────────────────

def _norm(raw: list[dict]) -> list[dict]:
    out = []
    for r in raw:
        label = r.get("check") or r.get("query") or r.get("id") or "?"
        out.append({
            "check":  str(label),
            "passed": bool(r.get("passed", False)),
            "note":   str(r.get("note", r.get("result", ""))),
        })
    return out


# ── Individual phase runners ─────────────────────────────────────────────────

def _run_phase(name: str, fn, *args) -> dict:
    t0 = time.time()
    try:
        raw     = fn(*args)
        results = _norm(raw if isinstance(raw, list) else [])
    except Exception:
        results = [{"check": name, "passed": False, "note": traceback.format_exc(limit=2)}]
    elapsed = round(time.time() - t0, 2)
    passed  = sum(1 for r in results if r["passed"])
    return {
        "name":    name,
        "passed":  passed,
        "total":   len(results),
        "elapsed": elapsed,
        "checks":  results,
    }


def run_quick() -> dict:
    """Run all evals that don't need live LLM API calls (~5 seconds)."""
    phases = {}

    # Phase 1 — Foundation env checks
    from phase1_foundation.evals.eval_foundation import run as p1
    phases["P1: Foundation"] = _run_phase("P1: Foundation", p1)

    # Phase 3 — Review pipeline structure
    from phase3_review_pillar_b.evals.eval_pipeline import run as p3
    phases["P3: Review Pipeline"] = _run_phase("P3: Review Pipeline", p3)

    # Phase 4 — Voice agent contract
    from phase4_voice_pillar_b.evals.eval_voice import run as p4
    phases["P4: Voice Agent"] = _run_phase("P4: Voice Agent", p4)

    # Phase 5 — RAG safety eval (pattern-based, no LLM)
    from phase5_pillar_a_faq.evals.eval_faq import run_safety_eval
    phases["P5: FAQ Safety"] = _run_phase("P5: FAQ Safety", run_safety_eval)

    # Phase 6 — Voice + Pulse integration
    from phase6_pillar_b_voice.evals.eval_integration import run as p6
    phases["P6: Voice Integration"] = _run_phase("P6: Voice Integration", p6)

    # Phase 7 — HITL approval gate
    from phase7_pillar_c_hitl.evals.eval_hitl import run as p7
    phases["P7: HITL Approvals"] = _run_phase("P7: HITL Approvals", p7)

    return phases


def _norm_rag(rag_result: dict) -> list[dict]:
    """Flatten RAG eval dict → [{check, passed, note}] for each question × metric."""
    rows = []
    for r in rag_result.get("results", []):
        rows.append({
            "check":  f"Faithful: {r['id']} — {r.get('question','')[:40]}",
            "passed": bool(r.get("faithful")),
            "note":   f"sources={r.get('sources',[])}",
        })
        rows.append({
            "check":  f"Relevant: {r['id']} — {r.get('question','')[:40]}",
            "passed": r.get("relevant") is True,
            "note":   r.get("reason", ""),
        })
    return rows


def _norm_ux(ux_result: dict) -> list[dict]:
    """Flatten UX eval dict → [{check, passed, note}]."""
    label_map = {
        "pulse_word_count":  "UX: Pulse ≤250 words",
        "pulse_actions":     "UX: Exactly 3 action ideas",
        "theme_in_greeting": "UX: Top theme in voice greeting",
        "pii_redacted":      "UX: PII replaced with [REDACTED]",
        "state_persistence": "UX: Booking code in Notes (M3→M2)",
    }
    return [
        {
            "check":  label_map.get(k, k),
            "passed": bool(v.get("passed")),
            "note":   str(v.get("value", "")),
        }
        for k, v in ux_result.items()
    ]


def run_live() -> dict:
    """Run evals that require live embeddings / LLM calls (~90 seconds)."""
    phases = {}

    # Pre-warm local embedder (avoids 10-second cold-start per eval)
    import phase2_corpus_pillar_a.embedder as _emb
    _emb._openai_failed = True
    _emb.get_embeddings(["warmup"])

    # Phase 2 — Corpus retrieval spot-check
    from phase2_corpus_pillar_a.evals.eval_corpus import run as p2
    phases["P2: Corpus RAG"] = _run_phase("P2: Corpus RAG", p2, False)

    # Phase 5 — Fee completeness across all funds (live Claude calls)
    from phase5_pillar_a_faq.evals.eval_fee_completeness import run as p5fee
    phases["P5: Fee Completeness"] = _run_phase("P5: Fee Completeness", p5fee)

    # Phase 8 — RAG golden dataset (5 questions × faithfulness + relevance)
    try:
        from phase8_eval_suite.evals.rag_eval import run_rag_eval
        t0  = time.time()
        raw = run_rag_eval()
        phases["P8: RAG Eval"] = {
            "name":    "P8: RAG Eval",
            "passed":  raw["faithfulness"] + raw["relevance"],
            "total":   raw["total"] * 2,
            "elapsed": round(time.time() - t0, 2),
            "checks":  _norm_rag(raw),
        }
    except Exception:
        phases["P8: RAG Eval"] = {
            "name": "P8: RAG Eval", "passed": 0, "total": 10, "elapsed": 0,
            "checks": [{"check": "P8 RAG", "passed": False,
                        "note": traceback.format_exc(limit=2)}],
        }

    # Phase 8 — UX / Structure eval (loaded from saved pulse; no pipeline re-run)
    try:
        import json as _json
        from pathlib import Path as _Path
        from session_init import init_session_state
        from phase4_voice_pillar_b.voice_agent import VoiceAgent
        from phase8_eval_suite.evals.ux_eval import run_ux_eval

        _sess: dict = {}
        init_session_state(_sess)
        _pulse_file = ROOT / "data" / "pulse_latest.json"
        if _pulse_file.exists():
            _p = _json.loads(_pulse_file.read_text())
            _top3 = _p.get("top_3_themes", [])
            _sess["weekly_pulse"]  = _p.get("weekly_note", "")
            _sess["top_theme"]     = _top3[0] if _top3 else ""
            _sess["action_ideas"]  = _p.get("action_ideas", [])
        _agent = None
        if _sess.get("top_theme"):
            try:
                _agent = VoiceAgent(session=_sess,
                                    calendar_path=str(ROOT / "data" / "mock_calendar.json"))
            except Exception:
                pass
        t0  = time.time()
        raw = run_ux_eval(_sess, _agent)
        phases["P8: UX Eval"] = {
            "name":    "P8: UX Eval",
            "passed":  sum(bool(v.get("passed")) for v in raw.values()),
            "total":   len(raw),
            "elapsed": round(time.time() - t0, 2),
            "checks":  _norm_ux(raw),
        }
    except Exception:
        phases["P8: UX Eval"] = {
            "name": "P8: UX Eval", "passed": 0, "total": 5, "elapsed": 0,
            "checks": [{"check": "P8 UX", "passed": False,
                        "note": traceback.format_exc(limit=2)}],
        }

    return phases


def run_all(full: bool = False) -> dict:
    snapshot = {
        "run_at":  datetime.now().isoformat(timespec="seconds"),
        "mode":    "full" if full else "quick",
        "phases":  {},
    }
    snapshot["phases"].update(run_quick())
    if full:
        snapshot["phases"].update(run_live())

    # Summary
    all_checks = [c for p in snapshot["phases"].values() for c in p["checks"]]
    snapshot["summary"] = {
        "total":  len(all_checks),
        "passed": sum(1 for c in all_checks if c["passed"]),
    }

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(snapshot, indent=2))
    return snapshot


if __name__ == "__main__":
    full = "--full" in sys.argv
    print(f"\nRunning {'full' if full else 'quick'} eval suite…")
    snap = run_all(full=full)
    s = snap["summary"]
    print(f"\n{'='*55}")
    print(f"  {'FULL' if full else 'QUICK'} EVAL SUITE — {snap['run_at']}")
    print(f"  Overall: {s['passed']}/{s['total']} checks passed")
    print(f"{'='*55}")
    for pname, p in snap["phases"].items():
        icon = "✅" if p["passed"] == p["total"] else "❌"
        print(f"  {icon}  {pname:<30} {p['passed']}/{p['total']}  ({p['elapsed']}s)")
    print(f"\nResults saved → {RESULTS_PATH}\n")
    sys.exit(0 if s["passed"] == s["total"] else 1)
