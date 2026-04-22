# Phase 8 Architecture — Evaluation Suite

## Eval Harness Structure

```
evals/run_evals.py
       │
       ├─► RAG Eval
       │     golden_dataset.json (5 Q&A)
       │     For each Q: query → rag_engine.answer()
       │     Check faithfulness (source domain check)
       │     Check relevance (LLM judge or keyword match)
       │     Score: X/5 faithful, X/5 relevant
       │
       ├─► Safety Eval
       │     adversarial_tests.json (3 prompts)
       │     For each prompt: safety_filter.check()
       │     Assert refused=True for all 3
       │     Score: X/3 (must be 3/3 to pass)
       │
       └─► UX / Structure Eval
             Pulse word count ≤ 250
             Pulse action count == 3
             Voice greeting contains top_theme
             Score: X/3 (logic checks)
                    │
                    ▼
             EVALS_REPORT.md
             (auto-generated Markdown table)
```

## EVALS_REPORT.md Template

```markdown
# Evals Report — Investor Ops & Intelligence Suite
Generated: {datetime}

## 1. RAG Faithfulness & Relevance Eval
| Q# | Question | Faithful | Relevant |
|----|----|----|----|
| GD-01 | ... | ✓/✗ | ✓/✗ |
...
Faithfulness: X/5 | Relevance: X/5

## 2. Safety Eval (Adversarial Tests)
| ID | Prompt | Expected | Result |
|----|----|----|-----|
| ADV-01 | ... | REFUSE | PASS ✓ |
Safety Score: X/3

## 3. UX / Structure Eval
| Check | Criterion | Result |
|----|----|-----|
| Pulse Words | ≤ 250 | X words ✓/✗ |
| Action Ideas | == 3 | X found ✓/✗ |
| Theme Mention | in greeting | ✓/✗ |

## Overall: {PASS/FAIL}
```
