# Phase 1 Architecture — Foundation & Infrastructure

## What This Phase Does

Phase 1 is the foundation that every other phase depends on. It does not build any visible feature — it sets up the plumbing that makes everything else possible. Think of it like wiring a house before any appliances are installed: no lights yet, but without it nothing can turn on.

Specifically, Phase 1 creates three things:
1. **`config.py`** — reads all environment variables (API keys, settings) from the `.env` file, validates that required ones are present, and exposes them as constants. Every other file imports from here.
2. **`session_init.py`** — defines the 11 shared session keys that all three pillars use to communicate. Initializes them with safe default values at app startup.
3. **Empty `__init__.py` files** — makes `pillar_a/`, `pillar_b/`, `pillar_c/`, and `evals/` importable as Python packages, which is required by the test files.

If Phase 1 is wrong, everything else breaks silently. A missing API key, a misnamed session key, or a wrong default value will cause failures that are hard to trace back to their source. Getting Phase 1 right first eliminates a whole class of bugs.

---

## Component Diagram

```
app.py  /  test_dashboard.py
       │
       ▼
┌─────────────────────────────────────────────────┐
│  config.py                                      │
│  load_dotenv()  →  os.environ                   │
│                                                 │
│  Required vars:                                 │
│    ANTHROPIC_API_KEY                            │
│    OPENAI_API_KEY                               │
│    CHROMA_PERSIST_DIR   (default: ./data/chroma)│
│    MCP_MODE             (default: mock)         │
│    MCP_SERVER_URL       (default: localhost:3000)│
└──────────────┬──────────────────────────────────┘
               │
       ┌───────┴────────┐
       ▼                ▼
┌────────────┐   ┌───────────────────────────────┐
│  ChromaDB  │   │  SessionState (session_init.py)│
│  init.py   │   │                               │
│            │   │  weekly_pulse:    str | None   │
│  client =  │   │  top_theme:       str | None   │
│  Persistent│   │  top_3_themes:    list[str]    │
│  Client()  │   │  fee_bullets:     list[str]    │
│            │   │  fee_sources:     list[str]    │
│  ┌───────┐ │   │  booking_code:    str | None   │
│  │mf_faq │ │   │  booking_detail:  dict | None  │
│  │corpus │ │   │  mcp_queue:       list[dict]   │
│  └───────┘ │   │  chat_history:    list[dict]   │
│  ┌───────┐ │   │  pulse_generated: bool         │
│  │ fee   │ │   │  call_completed:  bool         │
│  │corpus │ │   └───────────────────────────────┘
│  └───────┘ │
└────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  MCPClient (pillar_c/mcp_client.py)  │
│  mode = os.getenv("MCP_MODE","mock") │
│  mock: in-process dict store         │
│  live:  POST to MCP_SERVER_URL       │
└──────────────────────────────────────┘
```

---

## File Responsibilities

| File | Responsibility |
|---|---|
| `config.py` | `load_env()` — validate and expose all env vars |
| `session_init.py` | `init_session_state(state)` — idempotent schema init |
| `pillar_a/ingest.py` | `get_chroma_client()`, `get_collection(name)` |
| `pillar_c/mcp_client.py` | `MCPClient` class with mock/live modes |
| `data/mock_calendar.json` | Static slot list for voice agent |

---

## Prerequisites

Before starting Phase 1:
- Python 3.11+ must be installed (`python --version` should show 3.11.x or higher)
- `pip install -r requirements.txt` must complete without errors
- A `.env` file must be created by copying `.env.example` and filling in real API keys

---

## Credentials Required

These are the environment variables this phase reads and validates. They live in the `.env` file and are never hardcoded anywhere in the source.

| Env Var | Required? | Purpose | Where to Get |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | All LLM calls — `claude-sonnet-4-6` | console.anthropic.com → API Keys |
| `OPENAI_API_KEY` | Yes | Embeddings (`text-embedding-3-small`) + TTS (`tts-1`) + ASR (`whisper-1`) | platform.openai.com → API Keys |
| `CHROMA_PERSIST_DIR` | No | Path to ChromaDB storage on disk. Default: `./data/chroma` | Set in `.env` |
| `MCP_MODE` | No | `mock` (default, no HTTP calls) or `live` (calls real MCP server) | Set in `.env` |
| `MCP_SERVER_URL` | No | Live MCP endpoint. Default: `http://localhost:3000` | Set in `.env` |
| `PRODUCT_NAME` | No | Display name shown in the UI. Default: `INDMoney Advisor Suite` | Set in `.env` |
| `SECURE_BASE_URL` | No | Base URL for booking links. Default: `https://app.example.com` | Set in `.env` |
| `ROUTER_MODE` | No | `keyword` (default, no LLM call) or `llm` (1-shot Claude classification) | Set in `.env` |

`load_env()` in `config.py` must raise a clear `EnvironmentError` if `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` are missing. The error message must list exactly which keys are absent. Failing fast here prevents cryptic errors 10 layers deep when a later phase tries to use a `None` key.

---

## Tools & Libraries

| Package | Version | Purpose | Install |
|---|---|---|---|
| `python-dotenv` | >=1.0.0 | `load_dotenv(ROOT/.env)` — loads `.env` file into `os.environ` | Already in `requirements.txt` |
| `chromadb` | >=0.5.0 | `PersistentClient(path=CHROMA_PERSIST_DIR)` — vector DB client | Already in `requirements.txt` |
| `pathlib` | stdlib | `Path(__file__).resolve().parent` — resolves project root path | No install needed |
| `os` | stdlib | `os.getenv("KEY", default)` — reads env vars | No install needed |

---

## Inputs

- `.env` file on disk (created by developer from `.env.example`)
- `data/mock_calendar.json` — static file that already exists in the repository; the voice agent reads it in Phase 4

---

## Step-by-Step Build Order

Build these files in this exact order. Each file is small and self-contained.

**1. `config.py`** — The first file to write. It must:
- Call `load_dotenv()` pointing to `ROOT/.env`
- Read and validate `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` — raise `EnvironmentError` if either is missing
- Read optional vars with their defaults: `CHROMA_PERSIST_DIR`, `MCP_MODE`, `MCP_SERVER_URL`, `PRODUCT_NAME`, `SECURE_BASE_URL`, `ROUTER_MODE`
- Validate `MCP_MODE` is one of `{"mock", "live"}` — default to `"mock"` with a `warnings.warn()` if an invalid value is given
- Export `SESSION_KEYS` dict with all 11 keys and their default values (see below)

```python
# config.py — key exports
SESSION_KEYS = {
    "weekly_pulse":    None,
    "top_theme":       None,
    "top_3_themes":    [],
    "fee_bullets":     [],
    "fee_sources":     [],
    "booking_code":    None,
    "booking_detail":  None,
    "mcp_queue":       [],
    "chat_history":    [],
    "pulse_generated": False,
    "call_completed":  False,
}
```

**2. `session_init.py`** — Defines one function:

```python
def init_session_state(state: dict) -> dict:
    """Idempotent: sets keys only if not already present."""
    for key, default in SESSION_KEYS.items():
        if key not in state:
            # Use a fresh copy for mutable defaults (lists, dicts)
            state[key] = default.copy() if isinstance(default, (list, dict)) else default
    return state
```

The "only if not already present" rule is critical. Streamlit reruns `app.py` on every user interaction. If `init_session_state` overwrote existing values, the app would reset its state every time the user clicks a button.

**3. `pillar_a/__init__.py`** — Empty file. Creates the `pillar_a` Python package.

**4. `pillar_b/__init__.py`** — Empty file. Creates the `pillar_b` Python package.

**5. `pillar_c/__init__.py`** — Empty file. Creates the `pillar_c` Python package.

**6. `evals/__init__.py`** — Empty file. Creates the `evals` Python package.

**7. `.env.example`** — Template file showing all env vars without real values:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
CHROMA_PERSIST_DIR=./data/chroma
MCP_MODE=mock
MCP_SERVER_URL=http://localhost:3000
PRODUCT_NAME=INDMoney Advisor Suite
SECURE_BASE_URL=https://app.example.com
ROUTER_MODE=keyword
```

---

## Outputs & Downstream Dependencies

Everything built in Phase 1 is consumed by every subsequent phase.

| Output | Consumed By |
|---|---|
| `config.py::SESSION_KEYS` | `session_init.py` (uses to define schema); `app.py` (imports for key reference) |
| `config.py::load_env()` | Called once at the top of `app.py`; also called in every phase's test fixture |
| `config.py::CHROMA_PERSIST_DIR` | Phase 2 ingest (`PersistentClient(path=...)`), Phase 5 retriever |
| `config.py::MCP_MODE` | Phase 7 `MCPClient.__init__()` |
| `config.py::ROUTER_MODE` | Phase 5 `query_router.py` |
| `config.py::SECURE_BASE_URL` | Phase 4 `voice_agent.py` BOOKED state (builds secure link) |
| `session_init.py::init_session_state()` | `app.py` startup; all phase test fixtures use it to create a clean session dict |
| `pillar_*/evals/__init__.py` files | Test files use `sys.path.insert(0, ROOT)` + these enable `from pillar_a.faq_engine import query` |
| `data/mock_calendar.json` | Phase 4 `booking_engine.py` — loads this to find available slots |

---

## Error Cases

**Missing `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`:**
`load_env()` must raise:
```
EnvironmentError: Missing required environment variables: ANTHROPIC_API_KEY, OPENAI_API_KEY
Please copy .env.example to .env and fill in your API keys.
```
Do not let the app start with missing keys — the error would surface as a confusing `NoneType` error much later.

**`CHROMA_PERSIST_DIR` path not writable:**
ChromaDB's `PersistentClient` will raise `PermissionError`. Catch it and re-raise with:
```
PermissionError: Cannot write to ChromaDB at {path}. Check that the directory exists and is writable.
```

**`MCP_MODE` has an unrecognised value:**
If `.env` contains `MCP_MODE=something_else`, default to `"mock"` and log:
```
Warning: Unrecognised MCP_MODE="something_else". Defaulting to "mock".
```

**`init_session_state` called with a non-dict `state`:**
Raise `TypeError("init_session_state expects a dict-like object")`. This catches cases where a developer passes `st.session_state` before Streamlit is running (e.g., in unit tests without a Streamlit context).

---

## Phase Gate

The following commands must all pass before moving to Phase 2:

```bash
pytest phase1_foundation/tests/test_foundation.py -v
# Expected: 10 tests pass
# Tests cover: load_env with valid keys, load_env with missing keys (raises),
#              init_session_state idempotency, session key count == 11,
#              MCP_MODE validation, CHROMA_PERSIST_DIR default value

python phase1_foundation/evals/eval_foundation.py
# Expected: 8/8 checks pass
# Checks: SESSION_KEYS has correct 11 keys, all defaults are correct types,
#         load_env succeeds with .env present, ChromaDB client initialises
```
