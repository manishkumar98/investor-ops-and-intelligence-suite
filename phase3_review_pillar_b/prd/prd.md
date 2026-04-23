# Phase 3 PRD — Review Intelligence Pipeline (M2)
**Owner:** CPO | **Depends on:** Phase 1 complete

---

## Goal
Turn a raw app-review CSV into a structured Weekly Pulse + Fee Explainer, write both to session state, and enqueue approval-gated MCP actions.

## Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P3-01 | PII scrubber removes phone, email, PAN, spaCy PERSON entities from all review text | Zero PII in output; redacted count ≥ 0 logged |
| P3-02 | Theme clusterer produces ≤ 5 themes; returns top 3 ranked by count | `len(themes) ≤ 5`; `top_3` is list of 3 strings |
| P3-03 | `top_theme` (rank-1 theme) written to `st.session_state["top_theme"]` | `session["top_theme"]` is a non-empty string after pipeline run |
| P3-04 | Quote extractor picks 1 quote per top-3 theme; all quotes PII-free | 3 quotes returned; no PII patterns in any quote |
| P3-05 | Weekly Pulse ≤ 250 words; contains exactly 3 action ideas | `word_count ≤ 250`; `action_idea_count == 3` |
| P3-06 | Fee explainer ≤ 6 bullets; includes 2 official source URLs; ends with "Last checked: {date}" | Bullet count ≤ 6; source list len == 2; last_checked present |
| P3-07 | Notes-append MCP action enqueued with `status = "pending"` | `mcp_queue` has ≥ 1 item with `type == "notes_append"` |
| P3-08 | Email-draft MCP action enqueued with `status = "pending"` | `mcp_queue` has ≥ 1 item with `type == "email_draft"` |

## Phase Gate Checklist
- [ ] PII scrubber removes all regex patterns (phone, email, PAN)
- [ ] Pulse word count ≤ 250 and action count == 3
- [ ] `session["top_theme"]` is set after pipeline run
- [ ] MCP queue has 2 pending items post-run
- [ ] `pytest phase3_review_pipeline/tests/ -v` exits 0
