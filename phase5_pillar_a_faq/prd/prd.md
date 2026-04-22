# Phase 5 PRD — Pillar A: Smart-Sync FAQ Engine
**Owner:** CPO | **Depends on:** Phase 2 (corpus loaded)

---

## Goal
Deliver a unified search UI that answers compound questions spanning fund facts (M1 corpus) AND fee logic (M2 corpus) — with source citation and a 6-bullet structure — while refusing all advice/PII queries 100% of the time.

## Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P5-01 | Safety pre-filter blocks advice, comparison, return-prediction, PII queries **before** retrieval | Blocked query returns `refused=True`; no LLM call made |
| P5-02 | Query router classifies query into `factual_only \| fee_only \| compound \| adversarial` | Classifier returns one of the 4 valid types |
| P5-03 | `factual_only` queries retrieve Top-4 from `mf_faq_corpus` only | `mf_faq_corpus.query()` called; `fee_corpus.query()` NOT called |
| P5-04 | `fee_only` queries retrieve Top-4 from `fee_corpus` only | Inverse of P5-03 |
| P5-05 | `compound` queries retrieve Top-4 from `mf_faq_corpus` + Top-2 from `fee_corpus` in parallel | Both `.query()` calls made; results merged & deduplicated |
| P5-06 | Chunks with cosine distance > 0.75 discarded before LLM fusion | Only chunks ≤ 0.75 distance passed to LLM |
| P5-07 | Compound answer formatted in exactly 6 bullets | `len(response.bullets) == 6` |
| P5-08 | Simple factual answer ≤ 3 sentences | Sentence count ≤ 3 |
| P5-09 | Every response includes ≥ 1 deduplicated source URL | `len(response.sources) >= 1` |
| P5-10 | Every response includes `"Last updated from sources: {date}"` | String present in rendered output |
| P5-11 | UI shows welcome line + 3 example compound questions on load | 3 examples visible before any query |
| P5-12 | Chat history appended to `session["chat_history"]` after each exchange | History grows by 2 entries (user + assistant) per query |

## Phase Gate Checklist
- [ ] Safety filter blocks all 3 adversarial patterns from Phase 8 golden tests
- [ ] Compound query retrieves from both collections
- [ ] Source URL present in every non-refused response
- [ ] `pytest phase5_pillar_a_faq/tests/ -v` exits 0
