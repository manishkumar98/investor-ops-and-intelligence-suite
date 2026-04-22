# Phase 9 PRD — Unified Dashboard (Production) + Internal Test Dashboard
**Owner:** CPO | **Depends on:** All phases complete

---

## Goal
Deliver two Streamlit apps: (1) `app.py` — the end-user Ops Dashboard with three pillars; (2) `test_dashboard.py` — an internal developer dashboard to test each phase independently and verify integration.

---

## Production Dashboard (`app.py`) Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P9-01 | Single entry point: `streamlit run app.py` | One URL; all three pillars accessible |
| P9-02 | Three tabs: Smart-Sync FAQ, Review Pulse & Voice, Approval Center | All three tabs render without errors |
| P9-03 | Sidebar shows system status: corpus loaded, pulse status, MCP pending count | Status updates when actions taken |
| P9-04 | Session state persisted to `data/mcp_state.json` as fallback on each action | File written after approve/reject |
| P9-05 | App recovers session from `data/mcp_state.json` on reload if session lost | Pending actions visible after Streamlit rerun |

---

## Internal Test Dashboard (`test_dashboard.py`) Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P9-06 | One tab per phase (Phase 1–9) + Overview tab | 10 tabs total |
| P9-07 | Each phase tab: shows PRD summary, "Run Tests" button, results, interactive demo | All elements present per tab |
| P9-08 | "Run Tests" button runs `pytest` on that phase folder via subprocess | Captures stdout/stderr; shows pass/fail count |
| P9-09 | "Run Eval" button runs that phase's eval script via subprocess | Shows eval results table |
| P9-10 | Phase gate status badge (🔴 Not Started / 🟡 In Progress / 🟢 Complete) | Badge updates when tests all pass |
| P9-11 | Overview tab shows all 9 phase statuses in a summary table | Summary table with phase name + status |
| P9-12 | "Run All Evals" button on Overview runs all eval scripts | Outputs combined report |

## Phase Gate Checklist
- [ ] `streamlit run app.py` starts without error
- [ ] `streamlit run test_dashboard.py` starts without error
- [ ] All 9 phase tabs render
- [ ] Overview summary table shows correct statuses
- [ ] `pytest phase9_dashboard/tests/ -v` exits 0
