# Phase 1 Architecture — Foundation & Infrastructure

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

## File Responsibilities

| File | Responsibility |
|---|---|
| `config.py` | `load_env()` — validate and expose all env vars |
| `session_init.py` | `init_session_state(state)` — idempotent schema init |
| `pillar_a/ingest.py` | `get_chroma_client()`, `get_collection(name)` |
| `pillar_c/mcp_client.py` | `MCPClient` class with mock/live modes |
| `data/mock_calendar.json` | Static slot list for voice agent |
