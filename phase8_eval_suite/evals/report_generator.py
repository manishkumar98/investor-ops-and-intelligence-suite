from datetime import datetime
from pathlib import Path


def generate_report(rag: dict, safety: dict, ux: dict, out_path: str = "EVALS_REPORT.md") -> None:
    now = datetime.utcnow().isoformat()

    # RAG table rows
    rag_rows = []
    for r in rag.get("results", []):
        f_sym = "✓" if r["faithful"]       else "✗"
        r_sym = "✓" if r["relevant"] is True else ("?" if r["relevant"] is None else "✗")
        rag_rows.append(
            f"| {r['id']} | {r['question'][:45]}... | {f_sym} | {r_sym} |"
        )
    rag_table = "\n".join(rag_rows)
    faith_score = rag.get("faithfulness", 0)
    rel_score   = rag.get("relevance", 0)
    rag_total   = rag.get("total", 5)
    rag_status  = "✓" if faith_score >= 4 and rel_score >= 4 else "✗"

    # Safety table rows
    safety_rows = []
    for r in safety.get("results", []):
        s_sym = "PASS ✓" if r["passed"] else "FAIL ✗"
        safety_rows.append(
            f"| {r['id']} | {r['prompt'][:45]}... | REFUSE | {s_sym} |"
        )
    safety_table = "\n".join(safety_rows)
    safety_score = safety.get("score", 0)
    safety_total = safety.get("total", 3)
    safety_gate  = "✓ HARD GATE PASSED" if safety.get("passed") else "✗ HARD GATE FAILED — DO NOT SHIP"

    # UX table rows
    wc    = ux.get("pulse_word_count",   {})
    ac    = ux.get("pulse_actions",      {})
    tg    = ux.get("theme_in_greeting",  {})
    wc_sym = "✓" if wc.get("passed") else "✗"
    ac_sym = "✓" if ac.get("passed") else "✗"
    tg_sym = "✓" if tg.get("passed") else "✗"
    ux_passed = wc.get("passed") and ac.get("passed") and tg.get("passed")
    ux_score  = sum([bool(wc.get("passed")), bool(ac.get("passed")), bool(tg.get("passed"))])
    ux_status = "✓" if ux_passed else "✗"

    overall = "PASS ✓" if (faith_score >= 4 and rel_score >= 4 and safety.get("passed") and ux_passed) else "FAIL ✗"

    report = f"""# Evals Report — Investor Ops & Intelligence Suite
Generated: {now}

## 1. RAG Faithfulness & Relevance Eval
| Q# | Question (abbreviated) | Faithful? | Relevant? |
|----|------------------------|-----------|-----------|
{rag_table}

Faithfulness: {faith_score}/{rag_total} {rag_status}  |  Relevance: {rel_score}/{rag_total} {rag_status}  (target: ≥4/5 both)

## 2. Safety Eval (Adversarial Tests)
| ID     | Prompt (abbreviated)                    | Expected | Result  |
|--------|-----------------------------------------|----------|---------|
{safety_table}

Safety Score: {safety_score}/{safety_total}  ({safety_gate})

## 3. UX / Structure Eval
| Check         | Criterion | Result |
|---------------|-----------|--------|
| Pulse Words   | ≤ 250     | {wc.get("value", 0)} words {wc_sym} |
| Action Ideas  | == 3      | {ac.get("value", 0)} found {ac_sym} |
| Theme Mention | In greeting | {tg_sym} detected |

UX Score: {ux_score}/3 {ux_status}

## Overall: {overall}
{"All hard gates passed. System is shippable." if overall.startswith("PASS") else "One or more gates failed. Review above."}
"""

    Path(out_path).write_text(report)
    print(f"EVALS_REPORT.md written to {out_path}")
