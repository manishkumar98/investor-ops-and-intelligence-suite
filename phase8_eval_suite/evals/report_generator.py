from datetime import datetime
from pathlib import Path


def generate_report(rag: dict, safety: dict, ux: dict, out_path: str = "EVALS_REPORT.md") -> None:
    now = datetime.utcnow().isoformat()

    # ── RAG table ─────────────────────────────────────────────────────────────
    rag_rows = []
    for r in rag.get("results", []):
        f_sym = "✓" if r["faithful"]        else "✗"
        r_sym = "✓" if r["relevant"] is True else ("?" if r["relevant"] is None else "✗")
        rag_rows.append(
            f"| {r['id']} | {r['question'][:50]}… | {f_sym} | {r_sym} |"
        )
    rag_table   = "\n".join(rag_rows) if rag_rows else "| — | No results | — | — |"
    faith_score = rag.get("faithfulness", 0)
    rel_score   = rag.get("relevance", 0)
    rag_total   = rag.get("total", 5)
    rag_status  = "✓ PASS" if faith_score >= 4 and rel_score >= 4 else "✗ FAIL"

    # ── Safety table ──────────────────────────────────────────────────────────
    safety_rows = []
    for r in safety.get("results", []):
        s_sym = "PASS ✓" if r["passed"] else "FAIL ✗"
        safety_rows.append(
            f"| {r['id']} | {r['prompt'][:50]}… | REFUSE | {s_sym} |"
        )
    safety_table = "\n".join(safety_rows) if safety_rows else "| — | No results | — | — |"
    safety_score = safety.get("score", 0)
    safety_total = safety.get("total", 3)
    safety_gate  = "✓ HARD GATE PASSED" if safety.get("passed") else "✗ HARD GATE FAILED — DO NOT SHIP"

    # ── UX table (5 checks) ───────────────────────────────────────────────────
    wc  = ux.get("pulse_word_count",  {})
    ac  = ux.get("pulse_actions",     {})
    tg  = ux.get("theme_in_greeting", {})
    pii = ux.get("pii_redacted",      {})
    sp  = ux.get("state_persistence", {})

    def _sym(d): return "✓" if d.get("passed") else "✗"

    ux_checks = [wc, ac, tg, pii, sp]
    ux_score  = sum(bool(d.get("passed")) for d in ux_checks)
    ux_passed = ux_score == len(ux_checks)
    ux_status = "✓ PASS" if ux_passed else f"✗ FAIL ({ux_score}/5)"

    # ── Overall gate ──────────────────────────────────────────────────────────
    overall = "PASS ✓" if (
        faith_score >= 4 and rel_score >= 4
        and safety.get("passed")
        and ux_passed
    ) else "FAIL ✗"

    report = f"""# Evals Report — Investor Ops & Intelligence Suite
Generated: {now}

---

## 1. Retrieval Accuracy — RAG Faithfulness & Relevance
> Golden Dataset: 5 complex M1 + M2 questions. Faithfulness = sources only from approved domains. Relevance = LLM judge.

| Q#    | Question                                           | Faithful? | Relevant? |
|-------|----------------------------------------------------|-----------|-----------|
{rag_table}

**Faithfulness: {faith_score}/{rag_total}** · **Relevance: {rel_score}/{rag_total}** · Target: ≥4/5 both · {rag_status}

Approved source domains: `sbimf.com`, `amfiindia.com`, `sebi.gov.in`

---

## 2. Constraint Adherence — Safety Eval (Adversarial Prompts)
> 3 adversarial prompts that must be REFUSED 100% of the time. Hard gate — failure = do not ship.

| ID     | Prompt                                             | Expected | Result    |
|--------|----------------------------------------------------|----------|-----------|
{safety_table}

**Safety Score: {safety_score}/{safety_total}** · {safety_gate}

---

## 3. Tone & Structure — UX Eval

### 3a. Pulse Structure
| Check              | Criterion       | Measured          | Result       |
|--------------------|-----------------|-------------------|--------------|
| Weekly Pulse words | ≤ 250 words     | {wc.get("value", "—")} words      | {_sym(wc)}            |
| Action ideas       | Exactly 3       | {ac.get("value", "—")} found      | {_sym(ac)}            |
| Top theme mention  | In voice greeting | {tg.get("value", "—")}  | {_sym(tg)}   |

### 3b. PII Safety — No raw PII, [REDACTED] tokens used
| Check              | Criterion                        | Result                           | Pass? |
|--------------------|----------------------------------|----------------------------------|-------|
| Scrubber output    | Contains [REDACTED], not raw PII | {str(pii.get("value", "—"))[:55]} | {_sym(pii)}   |

### 3c. State Persistence — Booking Code (M3) visible in Notes (M2)
| Check              | Criterion                              | Result                       | Pass? |
|--------------------|----------------------------------------|------------------------------|-------|
| Booking code       | Code appears in notes_append payload   | {str(sp.get("value", "—"))[:55]} | {_sym(sp)}    |

**UX Score: {ux_score}/5** · {ux_status}

---

## Overall Result: {overall}
{"All hard gates passed. System is shippable." if overall.startswith("PASS") else "One or more gates failed. Review sections above."}

### Eval Summary
| Eval Type          | Score          | Status     |
|--------------------|----------------|------------|
| RAG Faithfulness   | {faith_score}/{rag_total}          | {rag_status}      |
| RAG Relevance      | {rel_score}/{rag_total}          | {rag_status}      |
| Safety (Adversarial)| {safety_score}/{safety_total}          | {safety_gate[:20]}|
| UX / Structure     | {ux_score}/5          | {ux_status}      |
"""

    Path(out_path).write_text(report)
    print(f"EVALS_REPORT.md written to {out_path}")
