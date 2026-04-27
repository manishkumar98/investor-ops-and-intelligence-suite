# Investor Ops & Intelligence Suite
### INDMoney — AI Bootcamp Capstone

A unified three-pillar dashboard that merges a RAG FAQ chatbot (M1), a review intelligence pipeline (M2), and a voice appointment scheduler (M3) into a single Streamlit application.

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in ANTHROPIC_API_KEY and OPENAI_API_KEY
```

### 3. Ingest the corpus
```bash
python scripts/ingest_corpus.py
```
Fetches 30+ official SBI MF / INDMoney pages, extracts structured fund fields (AUM, NAV, exit load, expense ratio, etc.) into `data/fund_snapshot.json`, chunks the text, embeds with OpenAI `text-embedding-3-small` (fallback: `all-MiniLM-L6-v2`), and stores in ChromaDB under `data/chroma/`. Also ingests pre-scraped local files from `data/raw/`.

Use `--force` to re-fetch even if the source list hasn't changed.

> **Important:** The embedding model is locked at first ingest. Do not switch `OPENAI_API_KEY` between ingests without deleting `data/chroma/` first.

### 4. Run the app
```bash
streamlit run app.py
```

---

## Architecture

```
app.py  (single entry point)
├── Tab 1 — Smart-Sync Knowledge Base      → phase5_pillar_a_faq/faq_engine.py
├── Tab 2 — Insight-Driven Optimization    → phase3_review_pillar_b/pipeline_orchestrator.py
│                                            + phase4_voice_pillar_b/voice_agent.py
└── Tab 3 — Super-Agent MCP Workflow       → phase7_pillar_c_hitl/hitl_panel.py
```

| Phase | Pillar | Modules | Adapted From |
|---|---|---|---|
| Phase 2 | Corpus (Pillar A) | url_loader, chunker, embedder, ingest, structured_extractor | M1 RAG corpus build |
| Phase 5 | FAQ (Pillar A) | safety_filter, query_router, retriever, llm_fusion, faq_engine | M1 RAG chatbot |
| Phase 3 | Review (Pillar B) | pii_scrubber, theme_clusterer, quote_extractor, pulse_writer, fee_explainer, pipeline_orchestrator | M2 review pipeline |
| Phase 4 | Voice (Pillar B) | intent_classifier, slot_filler, booking_engine, voice_agent | M3 voice agent |
| Phase 7 | HITL (Pillar C) | mcp_client, email_builder, hitl_panel | New — approval gate |

---

## Key Technical Decisions

| Decision | Choice | Reason |
|---|---|---|
| LLM | `claude-sonnet-4-6` | Capstone requirement (all M1/M2/M3 used Groq) |
| Embeddings | OpenAI `text-embedding-3-small` (1536 dim) | Better quality than ChromaDB default (M1) |
| TTS | OpenAI `tts-1`, voice=alloy | Replaces Google Cloud TTS from M3 |
| ASR | OpenAI `whisper-1` | Replaces Google/Deepgram from M3 |
| Voice FSM | 7 states | Reduced from M3's 16 states per capstone spec |
| MCP approvals | Streamlit HITL panel | Replaces M2 terminal Y/N and M3 auto-execute |
| Calendar | Mock JSON | Replaces M3's live Google Calendar API |

---

## Complete User Flow

### Prerequisites (one-time)
```bash
python scripts/ingest_corpus.py   # build ChromaDB corpus
streamlit run app.py              # launch the app
```

---

### Step 1 — App loads (automatic)
- NAV ticker appears at the top with live fund prices
- HuggingFace embedding model pre-warms silently in the background
- Sidebar shows corpus status (FAQ + Fee chunk counts) and pending approvals count

---

### Step 2 — Tab 2 · Insight-Driven Optimization — Run the Pipeline
> Must do this before starting a voice call; Tab 1 works independently at any time.

1. Click **▶ Run Pipeline**
2. System scrapes INDMoney reviews → Claude analyzes them → generates the **Weekly Pulse** (top themes, quotes, sentiment)
3. Sidebar updates: *"Top theme: Nominee Updates"*
4. Dashboard HTML appears: review analytics, sentiment breakdown, action recommendations, fee context bullets

---

### Step 3 — Tab 1 · Smart-Sync Knowledge Base — Ask a question (anytime)

1. Type a factual question, e.g. *"What is the exit load for SBI ELSS and why was I charged it?"*
2. System searches **both** M1 (FAQ corpus) and M2 (Fee corpus) simultaneously
3. Returns a **6-bullet answer**: exit load %, expense ratio, lock-in rules, redemption terms
4. Source citations from `sbimf.com` (M2 official) and `indmoney.com` (M1 FAQ)

---

### Step 4 — Tab 2 · Insight-Driven Optimization — Start a Voice Call

1. Click **▶ Start Call** (enabled after pipeline has run)
2. Agent delivers a **theme-aware greeting**: *"I see many users are asking about Nominee Updates today — I can help you book a call for that!"*
3. User speaks their topic → preferred date/time → agent confirms a slot
4. Booking confirmed → agent speaks the booking code (NL-XXXX format)
5. **Behind the scenes (automatic, no approval needed):**
   - Google Calendar event created immediately (background thread)
   - Google Sheets row logged immediately (background thread)
6. Terminal banner appears: *"✓ Appointment booked! Code: NL-XXXX — Check the Super-Agent MCP Workflow tab"*
7. Sidebar **Pending Approvals** counter jumps to **3**

---

### Step 5 — Tab 3 · Super-Agent MCP Workflow — Review & Approve
> Nothing reaches the advisor's inbox until you approve it here.

1. **Market Context card** at the top shows the Weekly Pulse snippet (M2 data) that will be injected into the advisor email
2. Three pending actions appear in the HITL panel:

| Action | What it is | Approval effect |
|---|---|---|
| 📅 Calendar Hold | Slot details for the advisor | Acknowledged — event already in Google Calendar |
| 📝 Notes Entry | Booking record (topic, slot, code) | Acknowledged — row already in Google Sheets |
| ✉️ Email Draft | Full advisor email with Market Context + Fee Context | Fires email to advisor (`manish98ad@gmail.com`) |

3. For the **Email Draft**: fill in Client Name + Client Email → click **✓ Approve & Send Email**
   - Advisor email fires to `manish98ad@gmail.com` with subject *"Advisor Pre-Booking: [Topic] — [Date]"*
   - Email body includes the Market Context snippet (from Weekly Pulse) so the advisor sees current customer sentiment before the meeting
   - Client confirmation email fires to the client address you entered
4. All three actions flip to **Approved** — queue clears

---

### Flow summary

```
Tab 1 (anytime)              Tab 2 (start here)              Tab 3 (final gate)
────────────────             ──────────────────              ──────────────────
Ask FAQ question      ←→     Run Pipeline                →   Market Context card
  ↓                            (M2 Weekly Pulse)               (M2 snippet preview)
6-bullet answer              Start Voice Call
with source links              (M3 briefed by M2)          →   3 pending actions:
from M1 + M2                   Theme-aware greeting             📅 Calendar Hold
                               Booking confirmed                📝 Notes Entry
                               ↓                                ✉️ Email Draft
                             3 actions enqueued          →      ↓
                                                             Approve all 3
                                                             Email → manish98ad@gmail.com
                                                             (with Market Context inside)
```

---

## Sample Queries (M1 Tested)

See [docs/sample_queries.md](docs/sample_queries.md) for verified Q&A pairs tested end-to-end on 2026-04-24, covering:
- Expense ratio, exit load, minimum SIP, lock-in, riskometer, benchmark
- Capital gains statement download with fund-specific CAMS links
- Known gaps and how to fix them

---

## Running Evals

```bash
python phase8_eval_suite/evals/run_evals.py
```

Expected output:
- Safety: 3/3 PASS (hard gate — failure = exit code 1)
- UX: 3/3 PASS
- RAG: ≥4/5 faithful, ≥4/5 relevant
- `EVALS_REPORT.md` generated in project root

---

## Environment Variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | All LLM calls (claude-sonnet-4-6) |
| `OPENAI_API_KEY` | Yes | — | Embeddings (text-embedding-3-small) + TTS (tts-1) + ASR (whisper-1) |
| `CHROMA_PERSIST_DIR` | No | `./data/chroma` | ChromaDB storage path |
| `MCP_MODE` | No | `live` | `mock` (in-memory only) or `live` (SMTP email + Google APIs) |
| `MCP_SERVER_URL` | No | `http://localhost:3000` | Live MCP server base URL |
| `SECURE_BASE_URL` | No | `https://app.example.com` | Base URL for booking completion links |
| `ADVISOR_EMAIL` | No | `GMAIL_ADDRESS` | Recipient for advisor pre-booking emails (e.g. `manish98ad@gmail.com`) |
| `GMAIL_ADDRESS` | No | — | Gmail account used for sending emails |
| `GMAIL_APP_PASSWORD` | No | — | Gmail app password (16-char, no spaces) |
| `ROUTER_MODE` | No | `keyword` | FAQ query routing: `keyword` or `llm` |

---

## Utility Scripts

```bash
# Health check (API key, ChromaDB, corpus freshness, disk)
python scripts/health_monitor.py

# Backup chroma + snapshots to data/backups/ (keeps last 5)
python scripts/backup_data.py
```

## Source Manifest

All 30+ official URLs used for corpus ingestion are listed in `SOURCE_MANIFEST.md`. Add new URLs with prefix `mf_faq:` or `fee:` then re-run `ingest_corpus.py --force`.

---

## Project Structure

```
investor_ops-and-intelligence_suit/
├── app.py                          # Main entry point (Streamlit)
├── config.py                       # Env vars + SESSION_KEYS
├── session_init.py                 # Idempotent session initialiser
├── SOURCE_MANIFEST.md              # 30+ official URLs for ingest
├── requirements.txt                # Python dependencies
│
├── phase1_foundation/              # Infrastructure (config, session, ChromaDB init)
│   ├── prd/ architecture/ tests/ evals/
│
├── phase2_corpus_pillar_a/         # Corpus ingestion (M1 RAG build)
│   ├── url_loader.py               # Fetch + collapse page text
│   ├── chunker.py                  # Text chunker + structured chunk builder
│   ├── embedder.py                 # OpenAI / local sentence-transformer embedder
│   ├── ingest.py                   # Full ingest pipeline → ChromaDB + fund_snapshot.json
│   ├── structured_extractor.py     # Regex field extractor (14 named slots per fund)
│   └── prd/ architecture/ tests/ evals/
│
├── phase3_review_pillar_b/         # Review pipeline (M2 adapted)
│   ├── pii_scrubber.py
│   ├── theme_clusterer.py
│   ├── quote_extractor.py
│   ├── pulse_writer.py
│   ├── fee_explainer.py
│   ├── pipeline_orchestrator.py
│   └── prd/ architecture/ tests/ evals/
│
├── phase4_voice_pillar_b/          # Voice agent (M3 adapted)
│   ├── intent_classifier.py
│   ├── slot_filler.py
│   ├── booking_engine.py
│   ├── voice_agent.py
│   └── prd/ architecture/ tests/ evals/
│
├── phase5_pillar_a_faq/            # FAQ engine (M1 chatbot)
│   ├── safety_filter.py            # Pre-filter: blocks advice/PII before retrieval
│   ├── query_router.py             # Routes to mf_faq / fee / both collections
│   ├── retriever.py                # Embeds query, retrieves + distance-filters chunks
│   ├── llm_fusion.py               # Claude fusion → FaqResponse (bullets/prose/sources)
│   ├── faq_engine.py               # Pipeline orchestrator (safety→route→retrieve→fuse)
│   └── prd/ architecture/ tests/ evals/
│
├── phase7_pillar_c_hitl/           # HITL approval center
│   ├── mcp_client.py
│   ├── email_builder.py
│   ├── hitl_panel.py
│   └── prd/ architecture/ tests/ evals/
│
├── phase8_eval_suite/              # Evaluation suite
│   └── evals/
│       ├── run_evals.py
│       ├── safety_eval.py
│       ├── rag_eval.py
│       ├── ux_eval.py
│       ├── report_generator.py
│       ├── golden_dataset.json
│       └── adversarial_tests.json
│
├── scripts/
│   ├── ingest_corpus.py            # CLI: python scripts/ingest_corpus.py [--force]
│   ├── health_monitor.py           # 7-check health monitor → data/system_state.json
│   └── backup_data.py              # Backs up chroma + snapshots (keeps last 5)
│
└── data/
    ├── chroma/                     # ChromaDB (created by ingest)
    ├── raw/                        # Pre-scraped Playwright txt files
    ├── fund_snapshot.json          # Structured fields for all funds (written on ingest)
    ├── nav_snapshot.json           # NAV + prev_nav for ticker display
    ├── system_state.json           # Last ingest / backup / health-check timestamps
    ├── reviews_sample.csv          # Sample reviews for pipeline demo
    ├── mock_calendar.json          # Mock appointment slots
    └── mcp_state.json              # MCP action queue
```

---

## Known Limits

- Voice input is text-based in demo mode. Audio ASR via `whisper-1` requires microphone access.
- TTS audio (`tts-1`) requires a valid `OPENAI_API_KEY`. Text responses display even without audio.
- Corpus quality depends on URL accessibility at ingest time. Some SBI MF PDFs may require re-running `--force` after the pages update.
- The LLM relevance judge in RAG evals is self-evaluation (Claude judging Claude). For production, use a different model or human judges.
