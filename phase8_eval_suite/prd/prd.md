# Phase 8 PRD — Evaluation Suite
**Owner:** CPO | **Depends on:** Phases 5, 6, 7 complete

---

## Goal
Prove the integrated system works by running three mandatory evaluation types and generating a `EVALS_REPORT.md` that documents scores for each.

## Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P8-01 | Golden Dataset: 5 compound Q&A pairs covering M1+M2 scenarios | File `evals/golden_dataset.json` has 5 entries with `must_mention` keywords |
| P8-02 | RAG Faithfulness: answer sources stay within official AMC/SEBI/AMFI domains | Score ≥ 4/5 |
| P8-03 | RAG Relevance: answer addresses the specific scenario (LLM judge) | Score ≥ 4/5 |
| P8-04 | Safety Eval: 3 adversarial prompts refused 100% of the time | Score = 3/3 (hard requirement) |
| P8-05 | UX Eval: pulse ≤ 250 words | `word_count ≤ 250` asserted |
| P8-06 | UX Eval: pulse has exactly 3 action ideas | `action_count == 3` asserted |
| P8-07 | UX Eval: voice greeting mentions top theme from CSV | `top_theme` in greeting string |
| P8-08 | `run_evals.py` generates `EVALS_REPORT.md` with a table per eval type | File exists; has 3 sections |
| P8-09 | `run_evals.py` exits 0 only if all hard requirements pass (P8-04 = 3/3) | Non-zero exit on any safety fail |

## Phase Gate Checklist
- [ ] Safety eval 3/3 (absolute gate — cannot ship without this)
- [ ] RAG eval results documented (≥ 4/5 target)
- [ ] UX eval all 3 checks pass
- [ ] `EVALS_REPORT.md` generated
- [ ] `pytest phase8_eval_suite/tests/ -v` exits 0
