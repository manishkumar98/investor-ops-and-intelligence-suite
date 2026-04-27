"""Live eval: fee-completeness across all supported funds.

Checks that for any fee-related compound question the pipeline returns:
  - exit load value
  - expense ratio value
  - lock-in / redemption terms
  - at least one sbimf.com source (M2 official factsheet)
  - at least one indmoney.com source  (M1 FAQ page)

Run:
    python -m phase5_pillar_a_faq.evals.eval_fee_completeness
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]   # evals/ → phase5/ → project root
sys.path.insert(0, str(ROOT))

import os
os.chdir(ROOT)   # ensure relative paths (data/, chroma) resolve correctly

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")
if not os.getenv("ANTHROPIC_API_KEY"):
    raise EnvironmentError("ANTHROPIC_API_KEY not found — check .env")

# Pre-warm local embedder (skip broken OpenAI quota)
import phase2_corpus_pillar_a.embedder as _emb
_emb._openai_failed = True
_emb.get_embeddings(["warmup"])

from phase5_pillar_a_faq.faq_engine import query

# ── Test matrix ──────────────────────────────────────────────────────────────
# One fee question per fund. Expected values come from the ingested raw files.
FUND_FEE_TESTS = [
    {
        "fund":           "SBI ELSS Tax Saver Fund",
        "question":       "What is the exit load for the ELSS fund and why was I charged it?",
        "expected_exit":  "0%",
        "expected_er":    "0.99%",
        "has_lockin":     True,
    },
    {
        "fund":           "SBI Large Cap Fund",
        "question":       "What fees does SBI Large Cap Fund charge and can I redeem early?",
        "expected_exit":  "0.2%",
        "expected_er":    "0.84%",
        "has_lockin":     False,
    },
    {
        "fund":           "SBI Small Cap Fund",
        "question":       "What are the fee components for SBI Small Cap Fund?",
        "expected_exit":  "1.0%",
        "expected_er":    "0.79%",
        "has_lockin":     False,
    },
    {
        "fund":           "SBI Flexicap Fund",
        "question":       "What is the exit load and expense ratio for SBI Flexicap Fund?",
        "expected_exit":  None,
        "expected_er":    None,
        "has_lockin":     False,
        "known_data_gap": "sbimf page scraped as nav boilerplate only — indmoney source sufficient",
        "skip_source_sbimf": True,  # sbimf citation not expected for this fund
    },
    {
        "fund":           "SBI Midcap Fund",
        "question":       "What fees apply to SBI Midcap Fund and is there a lock-in period?",
        "expected_exit":  None,
        "expected_er":    None,
        "has_lockin":     False,
    },
]

# ── Checkers ─────────────────────────────────────────────────────────────────

def _full_text(r) -> str:
    return " ".join(r.bullets).lower() if r.bullets else (r.prose or "").lower()


def check_mentions(text: str, *keywords) -> bool:
    return all(kw.lower() in text for kw in keywords)


def check_sources(sources: list[str]) -> dict:
    has_sbimf    = any("sbimf.com"    in s for s in sources)
    has_indmoney = any("indmoney.com" in s for s in sources)
    return {"sbimf": has_sbimf, "indmoney": has_indmoney}


# ── Runner ───────────────────────────────────────────────────────────────────

def run() -> list[dict]:
    """Run fee completeness checks across all funds. Returns list[{check, passed, note}]."""
    results = []
    for test in FUND_FEE_TESTS:
        try:
            session = {}
            r = query(test["question"], session)
            text = _full_text(r)
            src  = check_sources(r.sources)

            checks = {
                "exit_load_mentioned":     check_mentions(text, "exit load"),
                "expense_ratio_mentioned": check_mentions(text, "expense ratio"),
                "lock_in_mentioned":       check_mentions(text, "lock") if test["has_lockin"] else True,
                "min_3_bullets":           len(r.bullets) >= 3,
                "source_indmoney":         src["indmoney"],
            }
            if not test.get("skip_source_sbimf"):
                checks["source_sbimf"] = src["sbimf"]
            if test["expected_exit"]:
                checks["exit_value_correct"] = test["expected_exit"] in text
            if test["expected_er"]:
                checks["er_value_correct"] = test["expected_er"] in text

            all_pass = all(checks.values())
            failed   = [k for k, v in checks.items() if not v]
            note     = f"{len(r.bullets)} bullets, {len(r.sources)} sources"
            if test.get("known_data_gap"):
                note += f" | ⚠ data gap: {test['known_data_gap']}"
            if failed:
                note += f" | failed: {', '.join(failed)}"
            results.append({"check": test["fund"], "passed": all_pass, "note": note})
        except Exception as exc:
            results.append({"check": test["fund"], "passed": False, "note": str(exc)})
    return results


def _print_results(results: list[dict]) -> int:
    print("\n" + "=" * 70)
    print("Fee Completeness Eval — all supported funds")
    print("=" * 70)
    for r in results:
        icon = "✅" if r["passed"] else "❌"
        print(f"{icon}  {r['check']:<35}  {r['note']}")
    passed = sum(1 for r in results if r["passed"])
    print(f"\nResult: {passed}/{len(results)} funds passed all checks\n")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(_print_results(run()))
