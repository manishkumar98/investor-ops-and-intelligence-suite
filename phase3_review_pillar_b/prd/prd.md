# Phase 3 PRD — Review Intelligence Pipeline (M2)
**Owner:** CPO | **Depends on:** Phase 1 complete

---

## Goal
Turn a raw app-review CSV into a structured Weekly Pulse + Fee Explainer and write results to session state. M2 pipeline does **not** enqueue any MCP actions — all HITL actions are generated exclusively by M3 voice agent at booking time.

## Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P3-01 | PII scrubber removes phone, email, PAN, spaCy PERSON entities from all review text | Zero PII in output; redacted count ≥ 0 logged |
| P3-02 | Theme clusterer produces ≤ 5 themes; returns top 3 ranked by count | `len(themes) ≤ 5`; `top_3` is list of 3 strings |
| P3-03 | `top_theme` (rank-1 theme) written to `st.session_state["top_theme"]` | `session["top_theme"]` is a non-empty string after pipeline run |
| P3-04 | Quote extractor picks 1 quote per top-3 theme; all quotes PII-free | 3 quotes returned; no PII patterns in any quote |
| P3-05 | Weekly Pulse ≤ 250 words; contains exactly 3 action ideas | `word_count ≤ 250`; `action_idea_count == 3` |
| P3-06 | Fee explainer ≤ 6 bullets; includes 2 official source URLs; ends with "Last checked: {date}" | Bullet count ≤ 6; source list len == 2; last_checked present |
## Phase Gate Checklist
- [ ] PII scrubber removes all regex patterns (phone, email, PAN)
- [ ] Pulse word count ≤ 250 and action count == 3
- [ ] `session["top_theme"]` is set after pipeline run
- [ ] `session["fee_bullets"]` and `session["fee_sources"]` populated
- [ ] `pytest phase3_review_pillar_b/tests/ -v` exits 0
