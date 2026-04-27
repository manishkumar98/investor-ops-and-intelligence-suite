# Architecture Document
## Investor Ops & Intelligence Suite
**Version:** 2.0 (As-Built)
**Date:** April 27, 2026
**Author:** Chief Technology Officer
**Status:** Reflects actual implemented system — source of truth is the code

---

## How to Read This Document

This document describes how the Investor Ops & Intelligence Suite is actually built — what each component does, how they connect, and where to find the code. It is written for both technical developers and non-technical stakeholders.

For non-technical readers: focus on the plain-language paragraphs. Code blocks and diagrams are for the engineering team.

For developers: every section ends with exact function signatures, actual module paths, and technology choices as implemented. If this document conflicts with the code, **the code wins** — file a correction.

---

## 1. System Overview

### What is this system?

The Investor Ops & Intelligence Suite is an AI-powered operations platform built for INDMoney. It brings together three separate AI tools into a single unified dashboard: a mutual fund FAQ chatbot, a weekly intelligence report from app reviews, and a voice agent that books advisor appointments — with a human-in-the-loop approval gate on all outbound actions.

### Core Design Principles

**State flows in one direction.** The review pulse is generated first, then informs the voice agent greeting, then informs the advisor email. Data never flows backward.

**All external actions are approval-gated.** The system prepares calendar holds, notes entries, email drafts, and sheet rows — but executes none of them without a human clicking Approve in Tab 3.

**Zero PII at every layer.** Review text is scrubbed (regex + spaCy) before any AI sees it. The voice agent blocks PII input. The compliance guard blocks PII in agent output.

**Single UI surface.** One Streamlit app (`streamlit run app.py`) with three tabs. No separate logins, no separate deployments.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     UNIFIED DASHBOARD (Streamlit)                   │
│             Single Entry Point · app.py · Port 8501                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │  Tab 1           │  │  Tab 2           │  │  Tab 3             │ │
│  │  Smart-Sync KB   │  │  Insight-Driven  │  │  Super-Agent MCP   │ │
│  │  (Pillar A)      │  │  (Pillar B)      │  │  Workflow (HITL)   │ │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬───────────┘ │
└───────────┼─────────────────────┼─────────────────────┼─────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       SHARED SESSION STATE                          │
│  weekly_pulse · top_theme · top_3_themes · fee_bullets · fee_sources│
│  booking_code · booking_detail · mcp_queue · chat_history           │
│  pulse_generated · call_completed · analytics_data · action_ideas   │
└──────┬──────────────────────┬──────────────────────┬────────────────┘
       │                      │                      │
       ▼                      ▼                      ▼
┌──────────────┐  ┌───────────────────────┐  ┌─────────────────────────┐
│  FAQ Engine  │  │  Review + Voice       │  │  MCP Gateway (HITL)     │
│  (RAG+LLM)   │  │  Pipeline             │  │  ┌─────────────────────┐│
│  ChromaDB    │  │  Claude / Groq / TTS  │  │  │ 📅 Calendar Hold    ││
│  claude-     │  │  FSM Voice Agent      │  │  │ 📝 Notes/Doc Entry  ││
│  sonnet-4-6  │  │  8-state FSM          │  │  │ ✉️ Email Draft      ││
└──────────────┘  └───────────────────────┘  │  │ 📊 Google Sheet     ││
                                             │  └─────────────────────┘│
                                             │  Approve / Reject UI    │
                                             └─────────────────────────┘
```

---

## 3. Component Breakdown

### 3.1 UI Layer — Unified Dashboard (`app.py`)

A single Streamlit application (1,447 lines) providing three tabs, a themed sidebar, a NAV ticker, and a light/dark theme toggle.

| Component | Technology | What it does |
|---|---|---|
| Tab 1 — Smart-Sync KB | Streamlit chat + markdown | User types a question → structured FAQ answer with sources |
| Tab 2 — Insight-Driven | Streamlit + audio widget | Run Pipeline button → scrape reviews → voice agent |
| Tab 3 — Super-Agent MCP | Streamlit approval panel | Lists all pending MCP actions; Approve/Reject buttons |
| Theme Toggle | CSS custom properties | Light (Ivory & Amber) / Dark (Charcoal & Gold) — persists in session |
| NAV Ticker | HTML ticker from nav_snapshot.json | Live-style fund price display across page top |
| Sidebar | Streamlit sidebar | System status, API key status, last pipeline run timestamp |

**Key functions in app.py:**
- `_build_css(is_light: bool) → str` — generates full theme CSS via VAR_ placeholder substitution
- `_warm_embedder()` — cache-resource to pre-load sentence-transformers model at startup
- `_va2_stt()` — routes to STTEngine, falls back to Groq Whisper, then Google Speech
- `_va2_play_and_listen_js()` — browser-side VAD + mic capture + STT pipeline in JavaScript

---

### 3.2 Pillar A — Smart-Sync Knowledge Base

**Module path:** `phase5_pillar_a_faq/`

A user types a question about SBI Mutual Funds. The system finds relevant official documents, extracts relevant passages, and uses Claude to produce a structured answer with source citations.

#### Data Flow

```
User Query
    │
    ▼
┌─────────────────────┐
│  Safety Pre-Filter  │  4 regex patterns — runs BEFORE any LLM call
│  safety_filter.py   │  Blocks: advice, predictions, comparisons, PII
└────────┬────────────┘
         │ safe query only
         ▼
┌─────────────────────┐
│  Query Router       │  Keyword-based (default) or LLM-based (ROUTER_MODE=llm)
│  query_router.py    │  → "factual_only" | "fee_only" | "compound"
└────────┬────────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────────┐
│mf_faq  │ │ fee_corpus │  ChromaDB collections; MAX_DISTANCE = 1.2 (cosine)
│_corpus │ │            │  Top 4 + Top 2 chunks; fund-name reranking applied
└───┬────┘ └─────┬──────┘
    └──────┬──────┘
           ▼
    ┌─────────────┐
    │  LLM Fusion │  claude-sonnet-4-6
    │ llm_fusion  │  compound → 6 bullets / simple → ≤3 sentences
    └─────────────┘
           │
           ▼
      FaqResponse(refused, bullets, prose, sources, last_updated)
```

#### Safety Filter — 4 Blocked Categories (`safety_filter.py`)

```python
# Actual patterns as implemented
BLOCK_PATTERNS = [
    "advice_refusal":      blocks "which/best fund should I invest/buy/sell/redeem"
    "performance_refusal": blocks "return/profit/earn + next/predict/will/expect"
    "comparison_refusal":  blocks "compare/vs/versus + fund/scheme"
    "pii_refusal":         blocks "email/phone/contact/ceo/address"
]
```

Refusal messages include relevant SEBI/fund links. Returns `(False, refusal_msg)` immediately — no AI called.

#### Query Router (`query_router.py`)

Default mode: keyword matching (no LLM call).

```python
FACT_KWS = ["nav", "aum", "lock-in", "exit load", "fund", "elss", "sip",
            "sbi", "large cap", "smallcap", "minimum", "redemption", ...]
FEE_KWS  = ["charge", "expense ratio", "ter", "fee", "fees", "stt", "cost", ...]
# compound if both sets match; fee_only if only FEE_KWS; factual_only otherwise
```

`ROUTER_MODE=llm` in `.env` switches to claude-sonnet-4-6 1-shot classifier for ambiguous queries.

#### Retriever (`retriever.py`)

- Embeds query using OpenAI `text-embedding-3-small` (1536-dim) or `all-MiniLM-L6-v2` (384-dim) fallback
- Retrieves n=4 from `mf_faq_corpus` and/or n=2 from `fee_corpus`
- Deduplicates by chunk_id; drops chunks with cosine distance > **1.2**
- **Fund reranking:** +3 score if fund slug in chunk text; +2 if in chunk URL; drops non-matching chunks when a specific fund is named in query

#### LLM Fusion (`llm_fusion.py`)

Model: `claude-sonnet-4-6`
Output: `FaqResponse` dataclass — `(refused, refusal_msg, bullets, prose, sources, last_updated, query_type)`

System prompt enforces:
- Compound queries → exactly 6 numbered bullet points
- Simple queries → ≤ 3 sentences
- FEE COMPLETENESS rule: always include exit load + expense ratio + lock-in + redemption if fees mentioned
- Source citations from `ALLOWED_DOMAINS` only: `sbimf.com, amfiindia.com, sebi.gov.in, indmoney.com, camsonline.com, mfcentral.com`

#### Corpus Ingestion (`phase2_corpus_pillar_a/ingest.py`)

Run once: `python scripts/ingest_corpus.py`

- Reads pre-scraped `.txt` files from `data/raw/`
- Chunks at ~512 tokens with 64-token overlap
- Stores in two ChromaDB collections: `mf_faq_corpus` and `fee_corpus`
- **Critical:** embedding model dimension is locked after first write; cannot mix 1536-dim and 384-dim in same collection

---

### 3.3 Pillar B — Review Intelligence Pipeline

**Module path:** `phase3_review_pillar_b/`

#### Pipeline Orchestrator (`pipeline_orchestrator.py`)

Entry point: `run_pipeline(csv_source, session) → dict`

```
CSV (review_id, review_text, rating)
        │
        ▼
┌──────────────────────┐
│ Step 1: PII Scrubber │  regex (phone/email/PAN) + spaCy NER (PERSON entities)
│ pii_scrubber.py      │  → clean_reviews list; never stores original PII
└─────────┬────────────┘
          ▼
┌──────────────────────┐
│ Step 2: Theme        │  claude-sonnet-4-6, 2-pass for large datasets
│ Clusterer            │  Pass 1: chunk → per-chunk themes
│ theme_clusterer.py   │  Pass 2: synthesize → {themes(5), top_3, quotes, note, action_ideas}
└─────────┬────────────┘
          ▼
┌──────────────────────┐
│ Step 3: Quote        │  Picks best-rated review per top theme
│ Extractor            │  Re-scrubs each quote (second PII pass)
│ quote_extractor.py   │
└─────────┬────────────┘
          ▼
┌──────────────────────┐
│ Step 4: Pulse Writer │  claude-sonnet-4-6
│ pulse_writer.py      │  ≤250 words + exactly 3 numbered action ideas
│                      │  Retry loop max 3; hard-truncate on failure
└─────────┬────────────┘
          ▼
┌──────────────────────┐
│ Step 5: Fee          │  Maps top_theme → fee scenario
│ Explainer            │  RAG retrieval from fee_corpus (max 4 chunks)
│ fee_explainer.py     │  claude-sonnet-4-6 → ≤6 fee bullets + source URLs
└─────────┬────────────┘
          ▼
┌──────────────────────┐
│ Step 6: Analytics    │  Keyword cloud (with Hindi stopwords), sentiment,
│ theme_clusterer      │  rating distribution, word frequencies
│ generate_analytics() │
└─────────┬────────────┘
          ▼
    Session writes:
    weekly_pulse, top_theme, top_3_themes, action_ideas,
    fee_bullets, fee_sources, pulse_generated, analytics_data
```

**No MCP actions are enqueued by the M2 pipeline.** All 4 MCP actions are generated exclusively by the M3 voice agent on booking completion.

#### Session Outputs Written by Pipeline

| Key | Value | Used by |
|---|---|---|
| `weekly_pulse` | ≤250-word string | Voice agent GREET, advisor email body |
| `top_theme` | "#1 theme label" | Voice agent greeting, fee explainer |
| `top_3_themes` | list of 3 strings | HITL notes card, advisor email |
| `fee_bullets` | list of ≤6 bullets | Advisor email fee section |
| `fee_sources` | list of URL strings | Advisor email sources |
| `pulse_generated` | True | Enables "Start Call" button in Tab 2 |
| `analytics_data` | dict | Dashboard charts |

---

### 3.4 Pillar B — Theme-Aware Voice Agent

**Module path:** `phase4_voice_pillar_b/`

#### VoiceAgent FSM (`voice_agent.py`)

Class: `VoiceAgent(session: dict, calendar_path: str)`

8-state FSM:

| State | What happens | AI used |
|---|---|---|
| GREET | Reads `top_theme`; delivers disclaimer + theme mention | None — scripted |
| INTENT | Classify: book_new / reschedule / cancel / what_to_prepare / check_availability | Groq llama-3.3-70b → Claude Haiku → keyword fallback |
| TOPIC | Map free text to 1 of 6 valid topics | Rule-based + overlap matching |
| TIMEPREF | Parse day + period from user words | Regex only |
| OFFERSLOTS | Paginated slots from mock_calendar.json; 2 per page | Lookup only |
| CONFIRM | Read back: topic + slot + "Is that correct?" | None — scripted |
| BOOKED | Generate NL-XXXX code; enqueue 4 MCP actions; return secure URL | None — scripted |
| WAITLIST | No slots found; generate NL-WXXX code; queue waitlist notes + email | None — scripted |

**6 Valid Topics** (from `dialogue_states.py → TOPIC_LABELS`):
1. `kyc_onboarding` → KYC and Onboarding
2. `sip_mandates` → SIP and Mandates
3. `statements_tax` → Statements and Tax
4. `withdrawals` → Withdrawals and Timelines
5. `account_changes` → Account Changes and Nominee Updates
6. `fee_inquiry` → Fee and Expense Enquiry

**Booking Code Format:**
```
NL-XXXX — 4 characters from safe alphabet (A-Z, 2-9; excludes 0/O/1/I)
NL-WXXX — waitlist entries (3 safe chars after W prefix)
```

**TTS/STT Stack:**
- TTS: Sarvam AI `bulbul:v2` → gTTS (`en`, `co.in`) fallback
- STT: Groq Whisper (browser VAD → audio blob → Groq API) → Google Cloud Speech fallback

**M3 Layers (on every user turn):**
1. PII scrub user input (`pii_scrubber.py`)
2. FSM dispatch
3. Compliance guard on agent output (`compliance_guard.py::check_and_gate()`)
4. Interaction log to `data/logs/voice_interactions.jsonl`

#### On Booking Completion (`_complete_booking`)

Enqueues exactly **4 MCP actions** via `enqueue_action()`:

```python
# 1. Calendar Hold
enqueue_action(session, type="calendar_hold", payload={
    "title": f"Advisor Q&A — {topic_label} — {code}",
    "date": detail["date"], "time": detail["time"],
    "tz": "IST", "topic": topic_key, "booking_code": code,
}, source="m3_voice")

# 2. Notes/Doc Entry — contains BOTH M3 booking data AND M2 pulse context
enqueue_action(session, type="notes_append", payload={
    "doc_title": "Advisor Pre-Bookings",
    "entry": {
        "date": detail["date"], "topic": topic_label,
        "slot": detail["slot"], "booking_code": code,
        "status": "CONFIRMED",
        # M2 context (proves M2↔M3 connection):
        "top_3_themes": session.get("top_3_themes", []),
        "weekly_pulse": session.get("weekly_pulse", "")[:300],
        "fee_scenario": session.get("fee_bullets", [""])[0],
    },
}, source="m3_voice")

# 3. Email Draft — Dear Advisor, with meeting details + market context + fee context
enqueue_action(session, type="email_draft", payload={
    "subject": f"Pre-Booking Alert: {topic_label} — {date} @ {slot}",
    "booking_code": code, "topic_label": topic_label,
    "slot_start_ist": detail["slot"],
    "body": "Dear Advisor,\n\n[MEETING DETAILS]\n[MARKET CONTEXT]\n[FEE CONTEXT]\n...",
}, source="m3_voice")

# 4. Google Sheet Entry
enqueue_action(session, type="sheet_entry", payload={
    "booking_code": code, "topic_key": topic_key,
    "topic_label": topic_label, "slot_start_ist": detail["slot"],
    "date": detail["date"], "status": "CONFIRMED", "call_id": ctx.call_id,
}, source="m3_voice")
```

After enqueueing, a **background thread** dispatches to Google Calendar + Sheets + Gmail via `mcp/mcp_orchestrator.py` (non-blocking; HITL panel actions are the approval-gated path).

---

### 3.5 Pillar C — HITL Approval Center

**Module path:** `phase7_pillar_c_hitl/`

#### `enqueue_action()` (`mcp_client.py`)

The only way to add items to the MCP queue. **Deduplicates** on enqueue:

```python
def enqueue_action(session, type, payload, source) -> str:
    # Remove any existing PENDING action of same type+source before adding
    session["mcp_queue"] = [
        a for a in session["mcp_queue"]
        if not (a["status"] == "pending" and a["type"] == type and a["source"] == source)
    ]
    action = {
        "action_id":  uuid4(),
        "type":       type,    # calendar_hold | notes_append | email_draft | sheet_entry
        "status":     "pending",
        "created_at": utcnow(),
        "source":     source,  # m3_voice (only source as of v2.0)
        "payload":    payload,
    }
    session["mcp_queue"].append(action)
    return action["action_id"]
```

#### HITL Panel (`hitl_panel.py`)

```
render(session, mcp_client)
    │
    ├── "Clear N completed" button → removes approved/rejected entries, persists
    │
    ├── Booking Actions group (source: m3_voice)
    │   ├── 📅 Calendar Hold [expander]
    │   ├── 📝 Notes / Doc Entry [expander] — shows booking code + M2 pulse themes
    │   ├── ✉️ Email Draft [expander] — full scrollable body (no truncation)
    │   └── 📊 Google Sheet Entry [expander]
    │
    └── Each pending action shows:
        ├── Action card (rendered HTML — booking details, themes, email body, etc.)
        ├── [✓ Approve] → MCPClient.execute(action)
        └── [✗ Reject] → status = "rejected"; persist
```

**Notes card — connected view** (when both booking_code AND pulse themes present):
Shows booking code, topic, slot, date, status (M3 data) + Top Themes (M2), fee context, pulse snippet in one card — proving M2↔M3 connection.

**Email card:** Full body rendered in `<pre>` with `max-height:200px; overflow-y:auto` — no character truncation.

**Client confirmation email** (separate from HITL email draft): When advisor approves an `email_draft` from `m3_voice` source, a "Send Confirmation Email to Client" form appears (name, email, phone) — calls `mcp/email_tool.py::send_user_confirmation()` with an HTML confirmation template.

#### `MCPClient.execute()` (`mcp_client.py`)

| Mode | email_draft | notes_append | calendar_hold | sheet_entry |
|---|---|---|---|---|
| **mock** | In-memory dict + mcp_state.json | In-memory dict + mcp_state.json | Acknowledged | Acknowledged |
| **live** | Gmail SMTP (smtp.gmail.com:587, app password) | `mcp/docs_tool::append_notes_sync()` | Acknowledged (background thread already ran) | `mcp/sheets_tool::_append_row_sync()` |

---

### 3.6 MCP Infrastructure (`mcp/`)

#### `mcp_orchestrator.py`

Async dispatch called from background thread at booking time:
1. `create_calendar_hold()` → returns `event_id`
2. `append_booking_notes(event_id)` + `draft_approval_email()` in parallel
3. Results stored in `session["mcp_dispatch"]`

#### `sheets_tool.py`

Google Sheets via `gspread` + service account JSON:
- Sheet: `config.sheet_id`, tab: `config.sheet_tab` ("Advisor Pre-Bookings")
- Headers: `booking_code, topic_key, topic_label, slot_start_ist, slot_end_ist, advisor_id, status, calendar_event_id, email_draft_id, created_at_ist, call_id`
- Functions: `_append_row_sync`, `_get_booking_details_sync`, `_update_status_sync`, `_reschedule_row_sync`

#### `mcp/config.py` — `MCPConfig`

Lazy property bag for env vars: `service_account` (JSON), `calendar_id` (base64-decode support), `sheet_id`, `doc_id`, `gmail_address`, `gmail_app_password`, `advisor_email`, `slot_duration_minutes` (default 30), `hold_expiry_hours` (default 48).

---

### 3.7 Evaluation Suite

**Module path:** `phase8_eval_suite/evals/`

| File | Function | What it checks |
|---|---|---|
| `rag_eval.py` | `run_rag_eval()` | 5 golden questions; faithfulness (sources from ALLOWED_DOMAINS); relevance (claude-sonnet-4-6 as judge) |
| `safety_eval.py` | `run_safety_eval()` | 3 adversarial prompts; all 3 must be refused (hard gate) |
| `ux_eval.py` | `run_ux_eval(session, agent)` | Pulse ≤250 words; 3 action ideas; theme in greeting; PII scrubber; booking_code in notes payload |
| `run_evals.py` | `main()` | Runs all 3; writes EVALS_REPORT.md |
| `report_generator.py` | `generate_report()` | Formats results as Markdown table |

**Golden Questions (GD-01 through GD-05):** SBI ELSS exit load, SBI Large Cap expense ratio, ELSS 3-year lock-in + charges, SBI Small Cap exit load + expense ratio, SBI ELSS minimum SIP + fee components.

**Adversarial Prompts (ADV-01 through ADV-03):** Performance prediction, fund manager PII, investment advice redirect.

---

## 4. Data Flow — End-to-End

```
[Run Pipeline] → PII Scrub → Theme Cluster (2-pass) → Pulse Write → Fee Explain
                                    │
                          session["weekly_pulse"]
                          session["top_theme"]
                          session["fee_bullets"]
                                    │
                                    ▼
                       [Start Call] unlocked (pulse_generated=True)
                                    │
                          VoiceAgent.get_greeting()
                          "I see many users asking about {top_theme}..."
                                    │
                          [8-state FSM booking flow]
                                    │
                          booking_code = NL-XXXX
                                    │
              ┌─────────────────────┼──────────────────────┐
              ▼                     ▼                      ▼                ▼
       [calendar_hold]     [notes_append]          [email_draft]     [sheet_entry]
       booking code         booking code +           Dear Advisor,     booking_code
       topic / slot         M2 top_3_themes          meeting details   topic / slot
                            M2 pulse snippet         market context    call_id
                            M2 fee_scenario          fee context
              │
              └──────────────► [Tab 3: HITL Approval Center]
                                        │
                               Human clicks Approve
                                        │
                               MCPClient.execute()
                               (mock: JSON / live: Google APIs + Gmail)

[User FAQ Query] → Safety Filter → Query Router → Retriever (ChromaDB)
                                                         │
                                               LLM Fusion (claude-sonnet-4-6)
                                                         │
                                            6-bullet Answer + Source Citations
```

---

## 5. Technology Stack

| Layer | Technology | Version | Notes |
|---|---|---|---|
| UI Framework | Streamlit | ≥ 1.40.0 | Single app; native session state |
| LLM | Claude `claude-sonnet-4-6` | Latest | All AI tasks: FAQ, clustering, pulse, fee, intent |
| Embeddings (primary) | OpenAI `text-embedding-3-small` | dim=1536 | Locked before first ingest |
| Embeddings (fallback) | `all-MiniLM-L6-v2` | dim=384 | Used if no OPENAI_API_KEY |
| Vector DB | ChromaDB `PersistentClient` | ≥ 0.5.0 | data/chroma/; 2 collections |
| Intent Classification | Groq `llama-3.3-70b` → Claude Haiku → rules | — | Provider selected by available keys |
| Voice ASR | Groq Whisper → Google Cloud Speech | — | Browser VAD; audio blob → API |
| Voice TTS | Sarvam AI `bulbul:v2` → gTTS | — | SARVAM_API_KEY enables primary |
| Calendar | Google Calendar API | v3 | Service account; `mcp/calendar_tool.py` |
| Sheets | Google Sheets API via gspread | — | Service account; `mcp/sheets_tool.py` |
| Docs/Notes | Google Docs API | — | Service account; `mcp/docs_tool.py` |
| Email (advisor) | Gmail SMTP (smtp.gmail.com:587) | — | App password auth; `mcp_client.py` |
| Email (client) | Gmail SMTP via `mcp/email_tool.py` | — | HTML template confirmation |
| Python Runtime | Python 3.11+ | 3.11+ | Required |

---

## 6. Repository Structure (Actual)

```
investor_ops-and-intelligence_suit/
│
├── app.py                         ← Main entry: streamlit run app.py (1,447 lines)
├── config.py                      ← load_env(), SESSION_KEYS dict, ROUTER_MODE, MCP_MODE
├── session_init.py                ← init_session_state(state) — idempotent, uses SESSION_KEYS
├── requirements.txt
├── .env.example
│
├── pages/
│   ├── 1_Review_Pulse.py          ← Standalone Review Pulse page (embeds dashboard.html)
│   └── 2_Voice_Agent.py           ← Standalone Voice Agent page
│
├── scripts/
│   ├── ingest_corpus.py           ← Build ChromaDB collections (run once)
│   ├── run_review_pipeline.py     ← run_pipeline(status_cb) → scrape + process + save to data/
│   └── email_server.py            ← Standalone email API server
│
├── phase2_corpus_pillar_a/        ← Corpus ingestion
│   ├── ingest.py                  ← ingest_local_files(raw_dir); creates mf_faq_corpus + fee_corpus
│   ├── chunker.py
│   ├── embedder.py
│   └── url_loader.py
│
├── phase3_review_pillar_b/        ← Review Intelligence Pipeline (M2)
│   ├── pipeline_orchestrator.py  ← run_pipeline(csv_source, session) → dict
│   ├── pii_scrubber.py           ← scrub(text) → (clean_text, redaction_count)
│   ├── theme_clusterer.py        ← cluster(reviews); generate_analytics(reviews)
│   ├── quote_extractor.py        ← extract(clean_reviews, themes, top_3)
│   ├── pulse_writer.py           ← write(themes, quotes) — ≤250 words, 3 actions, retry 3x
│   └── fee_explainer.py          ← explain(top_theme, session) → {bullets, sources, checked}
│
├── phase4_voice_pillar_b/         ← Voice Booking Agent (M3)
│   ├── voice_agent.py            ← VoiceAgent(session): 8-state FSM; enqueues 4 MCP actions
│   ├── booking_engine.py         ← generate_booking_code(); match_slots(); book()
│   ├── dialogue_states.py        ← DialogueState enum (16 states); DialogueContext; TOPIC_LABELS
│   ├── intent_classifier.py      ← classify(utterance) — Groq→Claude→rules
│   ├── slot_filler.py            ← extract_topic(utt); extract_time_pref(utt)
│   ├── pii_scrubber.py           ← scrub_pii(text) → PiiResult
│   ├── compliance_guard.py       ← ComplianceGuard().check_and_gate(text)
│   ├── rag_injector.py           ← get_rag_context(query, topic) for what_to_prepare
│   └── waitlist_handler.py       ← create_waitlist_entry(topic, day_pref, time_pref)
│
├── phase5_pillar_a_faq/           ← Smart-Sync FAQ Engine (Pillar A)
│   ├── faq_engine.py             ← query(user_input, session) → FaqResponse
│   ├── safety_filter.py          ← is_safe(query) → (bool, refusal_msg | None)
│   ├── query_router.py           ← route(query) → "factual_only"|"fee_only"|"compound"
│   ├── retriever.py              ← retrieve(query, query_type); fund reranking; MAX_DISTANCE=1.2
│   └── llm_fusion.py             ← fuse(query, chunks, query_type) → FaqResponse
│
├── phase7_pillar_c_hitl/          ← HITL Approval Center (Pillar C)
│   ├── mcp_client.py             ← MCPClient(mode); enqueue_action() with deduplication; execute()
│   └── hitl_panel.py             ← render(session, mcp_client); 4 card types; Clear completed button
│
├── phase8_eval_suite/             ← Evaluation Suite
│   └── evals/
│       ├── rag_eval.py
│       ├── safety_eval.py
│       ├── ux_eval.py
│       ├── run_evals.py
│       ├── report_generator.py
│       ├── golden_dataset.json
│       └── adversarial_tests.json
│
├── mcp/                           ← Google API integrations (live mode)
│   ├── mcp_orchestrator.py       ← dispatch_mcp(payload) — async; calendar→sheets+email parallel
│   ├── calendar_tool.py          ← create_calendar_hold(), cancel_event()
│   ├── sheets_tool.py            ← _append_row_sync(); _update_status_sync(); etc.
│   ├── docs_tool.py              ← append_notes_sync(payload)
│   ├── email_tool.py             ← send_user_confirmation() — HTML client confirmation email
│   ├── config.py                 ← MCPConfig (lazy env var bag)
│   ├── models.py                 ← MCPPayload, ToolResult, MCPResults dataclasses
│   └── mcp_logger.py             ← Writes to data/logs/mcp_ops_log.jsonl
│
├── voice/                         ← TTS/STT engines
│   ├── tts_engine.py             ← TTSEngine().synthesise(text) → TTSResult
│   └── voice_logger.py
│
├── data/
│   ├── chroma/                   ← ChromaDB vector store (mf_faq_corpus + fee_corpus)
│   ├── raw/                      ← Pre-scraped .txt files for corpus ingest
│   ├── logs/                     ← voice_interactions.jsonl, mcp_ops_log.jsonl
│   ├── mock_calendar.json        ← Available advisor slots for demo
│   ├── reviews_sample.csv        ← Sample INDMoney reviews (PII-free)
│   ├── mcp_state.json            ← Persisted MCP queue (auto-generated)
│   ├── system_state.json         ← Last pipeline run timestamp + review count
│   ├── pulse_latest.json         ← Latest pulse output (for session restore on reload)
│   ├── fee_latest.json           ← Latest fee output
│   ├── analytics_latest.json     ← Latest analytics
│   ├── dashboard.html            ← Baked HTML dashboard (generated by pipeline)
│   └── nav_snapshot.json         ← Fund NAV data for ticker
│
├── PRD.md
├── ARCHITECTURE.md               ← This file
├── SOURCE_MANIFEST.md
├── EVALS_REPORT.md
└── README.md
```

---

## 7. Shared Session State

All session keys defined in `config.SESSION_KEYS` (initialized idempotently by `session_init.py`):

| Key | Type | Written by | Read by |
|---|---|---|---|
| `weekly_pulse` | str | `pipeline_orchestrator` | voice_agent GREET; advisor email body |
| `top_theme` | str | `theme_clusterer` | voice_agent greeting; fee_explainer |
| `top_3_themes` | list[str] | `theme_clusterer` | HITL notes card; advisor email |
| `action_ideas` | list[str] | `theme_clusterer` | Tab 2 display |
| `fee_bullets` | list[str] | `fee_explainer` | Advisor email fee section; notes entry |
| `fee_sources` | list[str] | `fee_explainer` | Advisor email sources |
| `booking_code` | str | `booking_engine` | Notes payload; email subject; sheet entry |
| `booking_detail` | dict | `booking_engine` | Email meeting details block |
| `mcp_queue` | list[dict] | `enqueue_action()` | `hitl_panel.render()`; Tab 3 |
| `chat_history` | list[dict] | `faq_engine` | Tab 1 chat display |
| `pulse_generated` | bool | `pipeline_orchestrator` | Tab 2 "Start Call" guard |
| `call_completed` | bool | `voice_agent` | Tab 2 status display |
| `analytics_data` | dict | `generate_analytics()` | Dashboard charts |

**Session restore on page reload:** `data/pulse_latest.json`, `fee_latest.json`, `analytics_latest.json` are loaded back into session keys when the dashboard HTML exists but `pulse_generated` is False.

---

## 8. Security & Compliance Architecture

### PII Scrubbing (Two-Pass)

```
Raw Review Text
    │
    ▼
Pass 1 — Regex:
    +91-XXXXXXXXXX / 10-digit mobile → [REDACTED]
    user@domain.com → [REDACTED]
    AAAAA9999A (PAN format) → [REDACTED]
    │
    ▼
Pass 2 — spaCy NER (en_core_web_sm):
    All PERSON entities → [REDACTED]
    │
    ▼
Audit count logged (number only, never values) → clean_text safe for AI
```

Double-scrub: quote extractor runs a second PII pass on each extracted quote.
Voice agent input: `scrub_pii()` runs on every user transcript.
Compliance guard: `check_and_gate()` blocks any PII or investment advice in agent output.

### Safety Architecture Summary

| Threat | Mitigation | Location |
|---|---|---|
| Investment advice | 4 regex patterns (hard-coded, locked) + LLM compliance guard | `safety_filter.py`, `compliance_guard.py` |
| PII disclosure | Input scrubber + output guard | `pii_scrubber.py`, `compliance_guard.py` |
| Hallucination | RAG grounding + ALLOWED_DOMAINS filter | `llm_fusion.py`, `retriever.py` |
| Wrong fund data | Fund slug reranking in retriever | `retriever.py` |
| Auto-send | `execute()` only callable from Approve button handler | `hitl_panel.py`, `mcp_client.py` |
| Duplicate actions | `enqueue_action()` deduplicates pending same-type+source | `mcp_client.py` |

---

## 9. MCP Action Lifecycle

```
Voice Agent books appointment
    │
    ▼
enqueue_action() × 4
    │  Deduplicates: removes existing pending of same type+source
    │  Appends to session["mcp_queue"] with status="pending"
    │  Persisted to data/mcp_state.json
    │
    ▼
Tab 3 — HITL Panel renders 4 pending cards
    │
    ├── User clicks Approve
    │       │
    │       ▼
    │   MCPClient.execute(action)
    │       ├── mock:  write to _mock_store + mcp_state.json
    │       └── live:
    │               email_draft   → Gmail SMTP send
    │               notes_append  → Google Docs append
    │               sheet_entry   → Google Sheets append row
    │               calendar_hold → acknowledged (background thread already ran)
    │
    └── User clicks Reject → status="rejected"; no execution

"Clear Completed" button → removes approved/rejected entries; persists pending only
```

---

## 10. Deployment

### Local (Demo)

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env   # fill in API keys
python scripts/ingest_corpus.py   # one-time corpus build (~5 min)
streamlit run app.py   # → http://localhost:8501
```

Required `.env` keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (or use MiniLM fallback), `GROQ_API_KEY`, `SARVAM_API_KEY`, `MCP_MODE=mock`.

For live MCP: `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_CALENDAR_ID`, `GOOGLE_SHEET_ID`, `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `ADVISOR_EMAIL`.

### Cloud (Production)

Deploy to HuggingFace Spaces or Render.com. ChromaDB requires persistent disk — configure `data/chroma/` as a mounted volume or migrate to Chroma Cloud.

---

## 11. Key Deviations from v1.0 Architecture (Apr 22, 2026)

| Area | v1.0 Plan | v2.0 Actual |
|---|---|---|
| Module paths | `pillar_a/`, `pillar_b/`, `pillar_c/`, `evals/` | `phase5_pillar_a_faq/`, `phase3_review_pillar_b/`, `phase4_voice_pillar_b/`, `phase7_pillar_c_hitl/`, `phase8_eval_suite/` |
| MCP actions from M2 | notes_append + email_draft enqueued by pipeline | None — M2 pipeline enqueues no HITL actions |
| MCP actions from M3 | 3 (calendar, notes, email) | 4 (calendar, notes, email, **sheet_entry**) |
| Voice FSM states | 7 states | 8 states (added explicit WAITLIST handling) |
| Booking code format | NL-[A-Z][0-9]{3} | NL-XXXX (4 safe chars: A-Z,2-9, excludes 0/O/1/I) |
| Waitlist code format | WL-[A-Z][0-9]{3} | NL-WXXX (NL prefix with W marker) |
| Retriever MAX_DISTANCE | 0.75 | **1.2** (cosine; tuned for fund corpus density) |
| Notes entry content | booking fields only | booking fields + **M2 top_3_themes + pulse snippet + fee_scenario** |
| Email subject | "Weekly Pulse + Fee Explainer — {date}" | "Pre-Booking Alert: {topic_label} — {date} @ {slot}" |
| enqueue_action | Simple append | **Deduplicates** pending same-type+source before append |
| HITL panel | 3 action types | 4 action types + **Clear Completed** button |
| email_builder.py | Separate file in pillar_c/ | Email built inline in `voice_agent.py::_complete_booking()` |

---

*This architecture document (v2.0) is the authoritative reference for the system as built. The code is the ultimate source of truth. For phase-level implementation details see `phase*/architecture/architecture.md`.*
