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
This fetches 30+ official SBI MF / AMFI / SEBI pages, chunks them, embeds them with OpenAI `text-embedding-3-small`, and stores them in ChromaDB under `data/chroma/`.

> **Important:** The embedding model is locked at first ingest. Do not switch `OPENAI_API_KEY` between ingests without deleting `data/chroma/` first.

### 4. Run the app
```bash
streamlit run app.py
```

---

## Architecture

```
app.py  (single entry point)
├── Tab 1 — Smart-Sync FAQ       → pillar_a/faq_engine.py
├── Tab 2 — Review Pulse & Voice → pillar_b/pipeline_orchestrator.py + voice_agent.py
└── Tab 3 — Approval Center      → pillar_c/hitl_panel.py
```

| Pillar | Modules | Adapted From |
|---|---|---|
| pillar_a (FAQ) | url_loader, chunker, embedder, ingest, safety_filter, query_router, retriever, llm_fusion, faq_engine | M1 RAG chatbot |
| pillar_b (Review + Voice) | pii_scrubber, theme_clusterer, pulse_writer, fee_explainer, pipeline_orchestrator, intent_classifier, slot_filler, booking_engine, voice_agent | M2 review pipeline + M3 voice agent |
| pillar_c (HITL) | mcp_client, email_builder, hitl_panel | New (M2/M3 approval gate migrated to Streamlit) |

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

## 3-Scene Demo Flow

**Scene 1 — Review Pulse (~1 min):**
1. Open Tab 2 → Upload `data/reviews_sample.csv`
2. Click "▶ Run Pipeline"
3. Review: top 3 themes, 3 user quotes, weekly pulse, fee bullets

**Scene 2 — Voice Booking (~2 min):**
1. Click "▶ Start Call" (enabled after pulse generated)
2. Agent greeting mentions top theme from pulse
3. Book a call: topic → time preference → slot selection → confirm
4. Booking code appears (NL-XXXX format)

**Scene 3 — FAQ + Approval (~2 min):**
1. Tab 1 → Ask: "What is the exit load for SBI ELSS and how does the expense ratio work?"
2. See 6-bullet answer with sbimf.com / amfiindia.com source citations
3. Tab 3 → Expand calendar_hold action → click Approve → green ✓ badge
4. Expand email_draft → view advisor email with pulse context + fee bullets → Approve

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
| `MCP_MODE` | No | `mock` | `mock` (no HTTP) or `live` (POST to MCP server) |
| `MCP_SERVER_URL` | No | `http://localhost:3000` | Live MCP server base URL |
| `SECURE_BASE_URL` | No | `https://app.example.com` | Base URL for booking completion links |
| `ROUTER_MODE` | No | `keyword` | FAQ query routing: `keyword` or `llm` |

---

## Source Manifest

All 30+ official URLs used for corpus ingestion are listed in `SOURCE_MANIFEST.md`.

---

## Project Structure

```
investor_ops-and-intelligence_suit/
├── app.py                          # Main entry point
├── config.py                       # Env vars + SESSION_KEYS
├── session_init.py                 # Idempotent session initialiser
├── SOURCE_MANIFEST.md              # 30+ official URLs
├── .env.example                    # Template for credentials
├── requirements.txt                # Python dependencies
│
├── pillar_a/                       # Smart-Sync FAQ (M1 adapted)
│   ├── url_loader.py
│   ├── chunker.py
│   ├── embedder.py
│   ├── ingest.py
│   ├── safety_filter.py
│   ├── query_router.py
│   ├── retriever.py
│   ├── llm_fusion.py
│   └── faq_engine.py
│
├── pillar_b/                       # Review Pipeline + Voice (M2+M3 adapted)
│   ├── pii_scrubber.py
│   ├── theme_clusterer.py
│   ├── quote_extractor.py
│   ├── pulse_writer.py
│   ├── fee_explainer.py
│   ├── pipeline_orchestrator.py
│   ├── intent_classifier.py
│   ├── slot_filler.py
│   ├── booking_engine.py
│   └── voice_agent.py
│
├── pillar_c/                       # HITL Approval Center (new)
│   ├── mcp_client.py
│   ├── email_builder.py
│   └── hitl_panel.py
│
├── evals/                          # Evaluation suite (Phase 8)
│   ├── golden_dataset.json
│   ├── adversarial_tests.json
│   ├── safety_eval.py
│   ├── ux_eval.py
│   ├── rag_eval.py
│   └── report_generator.py
│
├── scripts/
│   └── ingest_corpus.py
│
└── data/
    ├── reviews_sample.csv
    ├── mock_calendar.json
    └── chroma/                     # Created by ingest_corpus.py
```

---

## Known Limits

- Voice input is text-based in demo mode. Audio ASR via `whisper-1` requires microphone access.
- TTS audio (`tts-1`) requires a valid `OPENAI_API_KEY`. Text responses display even without audio.
- Corpus quality depends on URL accessibility at ingest time. Some SBI MF PDFs may require re-running `--force` after the pages update.
- The LLM relevance judge in RAG evals is self-evaluation (Claude judging Claude). For production, use a different model or human judges.
