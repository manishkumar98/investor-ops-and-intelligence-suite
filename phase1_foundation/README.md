# Phase 1 — Foundation & Infrastructure

**Status:** Complete | **Gate:** Must pass before any pillar work begins

## What this phase does

Sets up the shared runtime that every pillar depends on: environment loading, Streamlit session schema, ChromaDB collection creation, mock calendar data, and the MCP client stub. Nothing user-facing is built here — this is pure infrastructure.

## Files

| File | Purpose |
|---|---|
| `prd/prd.md` | Requirements (P1-01 → P1-08) and acceptance criteria |
| `architecture/architecture.md` | System design and dependency wiring |
| `tests/test_foundation.py` | Unit tests for all 8 requirements |
| `evals/eval_foundation.py` | Environment health checks (no LLM calls) |

## Shared modules (root level)

| File | Purpose |
|---|---|
| `config.py` | Loads `.env`, defines `SESSION_KEYS`, `CHROMA_PERSIST_DIR`, `MCP_MODE` |
| `session_init.py` | Idempotent `init_session(st.session_state)` — call on every page load |

## Running tests

```bash
pytest phase1_foundation/tests/ -v
```

## Running evals

```bash
python phase1_foundation/evals/eval_foundation.py
```

Checks env vars, data files, directory structure, and write permissions. No API key needed.

## Phase gate

All 8 requirements (P1-01 → P1-08) must pass before Phase 2 begins:
- `.env` loaded with all required keys
- `st.session_state` initialised with full schema
- ChromaDB `PersistentClient` created
- Both `mf_faq_corpus` and `fee_corpus` collections open
- `data/mock_calendar.json` readable with ≥ 4 slots
- `data/` directory writable
- `MCP_MODE` drives mock vs live client
