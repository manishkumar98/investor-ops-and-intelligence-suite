# Phase 5 — Pillar A: Smart-Sync FAQ Engine

**Status:** Complete | **Depends on:** Phase 2 (corpus loaded)

## What this phase does

Delivers the user-facing FAQ chatbot. Takes a natural language question, runs it through a safety gate, routes it to the right ChromaDB collection(s), retrieves grounded context, and fuses it into a cited answer via Claude. Refuses all advice, comparison, return-prediction, and PII queries before any LLM call.

## Files

| File | Purpose |
|---|---|
| `safety_filter.py` | Regex pre-filter: blocks advice/comparison/PII queries before retrieval |
| `query_router.py` | Classifies query into `factual_only`, `fee_only`, or `compound`; keyword mode (default) or LLM mode (`ROUTER_MODE=llm`) |
| `retriever.py` | Embeds query; retrieves Top-4 from `mf_faq_corpus` and/or Top-2 from `fee_corpus`; discards chunks with distance > 1.2 |
| `llm_fusion.py` | Calls `claude-sonnet-4-6` with retrieved context; returns `FaqResponse` with `bullets`, `prose`, `sources`, `last_updated` |
| `faq_engine.py` | Orchestrates the full pipeline: safety → route → retrieve → fuse; appends to `session["chat_history"]` |
| `prd/prd.md` | Requirements (P5-01 → P5-12) and acceptance criteria |
| `architecture/architecture.md` | Pipeline design and data flow |
| `tests/test_faq_engine.py` | Unit + mock tests for all 12 requirements |
| `evals/eval_faq.py` | Golden dataset (5 queries) + adversarial safety tests (3 patterns) |

## Query routing

| Query type | Collections queried | Example |
|---|---|---|
| `factual_only` | `mf_faq_corpus` (Top-4) | "What is the NAV of SBI Small Cap Fund?" |
| `fee_only` | `fee_corpus` (Top-2) | "What is the expense ratio for SBI ELSS?" |
| `compound` | Both collections | "What is the exit load and benchmark for SBI Flexicap?" |

## Response format

- **Compound** queries → 6 numbered bullets, each self-contained on one line
- **Simple** queries → ≤ 3 sentences
- Every response → ≥ 1 source URL from allowed domains
- Refused queries → `FaqResponse(refused=True, refusal_msg=...)`

## Allowed source domains

`sbimf.com` · `amfiindia.com` · `sebi.gov.in` · `indmoney.com` · `camsonline.com` · `mfcentral.com`

## Running tests

```bash
pytest phase5_pillar_a_faq/tests/ -v
```

## Running evals

```bash
python phase5_pillar_a_faq/evals/eval_faq.py
```

## Phase gate

- Safety filter blocks all 3 adversarial patterns (100% refusal rate)
- Compound query retrieves from both collections
- Source URL present in every non-refused response
- `pytest phase5_pillar_a_faq/tests/ -v` exits 0
