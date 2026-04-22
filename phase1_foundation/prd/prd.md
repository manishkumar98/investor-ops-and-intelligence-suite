# Phase 1 PRD — Foundation & Infrastructure
**Owner:** CPO | **Status:** Gate 0 — Must pass before any pillar work begins

---

## Goal
Stand up the shared runtime that every pillar depends on: environment variables, session state schema, vector DB collections, mock calendar, and the MCP client stub. Nothing visible to end-users is built here.

## Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| P1-01 | `.env` loaded on startup with all required keys | App starts; missing key raises `EnvironmentError` with the key name |
| P1-02 | `st.session_state` initialised with full schema on first load | All 11 keys present with correct default types after init |
| P1-03 | ChromaDB `PersistentClient` created at `CHROMA_PERSIST_DIR` | Client created; directory exists on disk |
| P1-04 | `mf_faq_corpus` collection created/opened | `collection.count()` returns an integer (may be 0) |
| P1-05 | `fee_corpus` collection created/opened | Same as above |
| P1-06 | `mock_calendar.json` readable with ≥ 4 slots | `data/mock_calendar.json` parses; `available_slots` has ≥ 4 entries |
| P1-07 | `MCP_MODE` env var drives mock vs live client | `MCPClient(mode="mock")` instantiates without external call |
| P1-08 | `data/` directory writable for state persistence fallback | File write to `data/mcp_state.json` succeeds |

## Phase Gate Checklist
- [ ] All 8 requirements pass
- [ ] `pytest phase1_foundation/tests/ -v` exits 0
- [ ] No hard-coded API keys in any file
