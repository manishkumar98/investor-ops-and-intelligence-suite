# Phase 9 Architecture — Unified Dashboard

## What This Phase Does

Phase 9 assembles all eight previous phases into a single working application. `app.py` is the entry point — one file that imports everything, initialises the system, and renders the three-tab Streamlit UI that the user actually sees.

If the previous phases are like the engine, gearbox, and wheels of a car, Phase 9 is putting them all into the chassis and turning the key. After Phase 9 is complete, the full demo is runnable: upload a CSV, generate a pulse, start a voice call, answer an FAQ, approve the outbound actions — all from one browser window.

**What Phase 9 builds:**

1. **`app.py`** — the main application file. This is the only file a user ever runs: `streamlit run app.py`
2. **`pages/2_Voice_Agent.py`** — standalone Streamlit multipage page for the voice agent
3. **`phase9_dashboard/architecture/architecture.md`** — this file
4. **`README.md`** — the setup guide that any new developer can follow to get the app running

**Key UI features (as-built):**
- NAV ticker: reads `data/nav_snapshot.json`, shows `nav` + `%change` per fund in sidebar
- Light/dark theme: CSS custom properties (`--bg-base`, `--card-bg`, `--text-primary`) via `.streamlit/config.toml` + inline CSS injection
- Multipage: `app.py` is the main dashboard; `pages/2_Voice_Agent.py` is the dedicated voice page

**What Phase 9 does not build:** No new AI logic, no new pipelines, no new session keys. Everything is wired together from previous phases.

---

## Application Structure

```
streamlit run app.py
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  app.py                                                 │
│                                                         │
│  1. load_env()          ← config.py                     │
│  2. init_session_state  ← session_init.py               │
│  3. mcp_state reload    ← data/mcp_state.json (if exists)│
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Sidebar                                        │   │
│  │  - corpus chunk counts (mf_faq + fee)           │   │
│  │  - pulse status + top theme                     │   │
│  │  - MCP pending count                            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  tab1, tab2, tab3 = st.tabs([...])                      │
│                                                         │
│  ┌──────────────────┐ ┌──────────────┐ ┌────────────┐  │
│  │ Tab 1            │ │ Tab 2        │ │ Tab 3      │  │
│  │ Smart-Sync FAQ   │ │ Review Pulse │ │ Approval   │  │
│  │                  │ │ + Voice      │ │ Center     │  │
│  │ st.chat_input()  │ │ st.file_     │ │ hitl_panel │  │
│  │ → faq_query()    │ │   uploader() │ │ .render()  │  │
│  │ → display        │ │ → pipeline() │ │            │  │
│  │   FaqResponse    │ │ + VoiceAgent │ │            │  │
│  └──────────────────┘ └──────────────┘ └────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## app.py Full Structure

```python
# app.py — complete top-level structure

import streamlit as st
from pathlib import Path
import json

from config import load_env, SESSION_KEYS, MCP_MODE, CHROMA_PERSIST_DIR
from session_init import init_session_state
from phase5_pillar_a_faq.faq_engine import query as faq_query
from phase2_corpus_pillar_a.ingest import get_collection
from phase3_review_pillar_b.pipeline_orchestrator import run_pipeline
from phase4_voice_pillar_b.voice_agent import VoiceAgent
from phase7_pillar_c_hitl.mcp_client import MCPClient
from phase7_pillar_c_hitl.hitl_panel import render as render_hitl

# ── 1. Bootstrap ──────────────────────────────────────────
load_env()
init_session_state(st.session_state)

# Reload MCP state from disk if session is fresh
if not st.session_state["mcp_queue"]:
    state_file = Path("data/mcp_state.json")
    if state_file.exists():
        try:
            st.session_state["mcp_queue"] = json.loads(state_file.read_text())
        except json.JSONDecodeError:
            pass

# ── 2. Sidebar ────────────────────────────────────────────
with st.sidebar:
    st.title("Investor Ops & Intelligence Suite by Dalal Street Advisors")
    st.markdown("---")

    # Corpus status
    try:
        faq_count = get_collection("mf_faq_corpus").count()
        fee_count = get_collection("fee_corpus").count()
        st.success(f"✅ FAQ corpus: {faq_count} chunks")
        st.success(f"✅ Fee corpus: {fee_count} chunks")
    except Exception:
        st.error("❌ Corpus not loaded — run: python scripts/ingest_corpus.py")

    st.markdown("---")

    # Pulse status
    if st.session_state["pulse_generated"]:
        st.info(f"📊 Top theme: **{st.session_state['top_theme']}**")
    else:
        st.warning("📊 No pulse generated yet")

    # MCP pending count
    pending = sum(1 for a in st.session_state["mcp_queue"] if a["status"] == "pending")
    st.metric("Pending Approvals", pending)

# ── 3. Tabs ───────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs([
    "📚 Smart-Sync FAQ",
    "📊 Review Pulse & Voice",
    "✅ Approval Center"
])

# ── Tab 1: FAQ ────────────────────────────────────────────
with tab1:
    # ... chat history display + chat_input + faq_query() ...

# ── Tab 2: Review Pulse + Voice ───────────────────────────
with tab2:
    # ... file_uploader + run_pipeline() + pulse display ...
    # ... UI guard + VoiceAgent loop (Phase 6 code) ...

# ── Tab 3: Approval Center ────────────────────────────────
with tab3:
    mcp_client = MCPClient(mode=MCP_MODE)
    render_hitl(session=st.session_state, mcp_client=mcp_client)
```

---

## Tab 1 — Smart-Sync FAQ

**What the user sees:** A chat interface. They type a question, the answer appears below with source URLs and a "Last updated" stamp. Previous Q&A pairs scroll above. A welcome message and 3 example compound questions appear on first load.

```python
# Tab 1 implementation sketch

with tab1:
    st.markdown("### Smart-Sync Mutual Fund FAQ")
    st.caption("Ask factual questions about SBI Mutual Fund schemes and fees.")

    # Example questions on first load
    if not st.session_state["chat_history"]:
        st.info("""
        **Try these compound questions:**
        - What is the exit load for SBI ELSS and how is the expense ratio calculated?
        - Can I redeem SBI Bluechip within 6 months and what fees apply?
        - What is the minimum SIP for SBI Small Cap and what are the fee components?
        """)

    # Display conversation history
    for entry in st.session_state["chat_history"]:
        with st.chat_message("user"):
            st.write(entry["content"])
        with st.chat_message("assistant"):
            response = entry["response"]
            if response.refused:
                st.warning(f"⚠ {response.refusal_msg}")
            elif response.bullets:
                for b in response.bullets:
                    st.markdown(f"- {b}")
            else:
                st.write(response.prose)
            for src in response.sources:
                st.caption(f"Source: {src}")
            st.caption(f"Last updated from sources: {response.last_updated}")

    # New question input
    user_question = st.chat_input("Ask a question about SBI Mutual Funds...")
    if user_question:
        faq_response = faq_query(user_question, st.session_state)
        st.rerun()
```

---

## Tab 2 — Review Pulse & Voice Agent

**What the user sees:** First, a file uploader for the reviews CSV. After upload, a "Run Pipeline" button. After the pipeline runs, three columns: top themes, representative quotes, and the weekly pulse text. Below that, the fee explanation bullets. Then the UI guard and "Start Call" button (Phase 6 code). After the call, the booking confirmation.

```python
with tab2:
    st.markdown("### Review Pulse & Voice Agent")

    # ── Review Pipeline section ──
    uploaded_file = st.file_uploader("Upload reviews CSV", type="csv")
    if uploaded_file and st.button("▶ Run Pipeline"):
        with st.spinner("Processing reviews..."):
            result = run_pipeline(uploaded_file, st.session_state)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.subheader("Top Themes")
            for theme in result["top_3"]:
                st.markdown(f"- {theme}")
        with col2:
            st.subheader("User Quotes")
            for q in result["quotes"]:
                st.markdown(f"*\"{q['quote']}\"*  — Rating: {q['rating']}/5")
        with col3:
            st.subheader("Weekly Pulse")
            st.write(result["pulse"])
            st.caption(f"Word count: {result['word_count']}")

        st.markdown("### Fee Context")
        for bullet in result["fee_bullets"]:
            st.markdown(f"- {bullet}")
        for src in result["fee_sources"]:
            st.caption(f"Source: {src}")

    # ── Voice Agent section (Phase 6 UI guard + call loop) ──
    st.markdown("---")
    st.markdown("### Voice Appointment Booking")
    # ... Phase 6 UI guard and call loop code here ...
```

---

## Tab 3 — Approval Center

**What the user sees:** A list of all pending, approved, and rejected MCP actions. Each action is expandable to show its payload. Pending actions have Approve and Reject buttons. Approved actions show a green badge with a reference ID. Rejected actions show a red badge.

```python
with tab3:
    st.markdown("### HITL Approval Center")
    st.caption("Review and approve all AI-generated actions before they execute.")

    pending_count = sum(
        1 for a in st.session_state["mcp_queue"] if a["status"] == "pending"
    )
    if pending_count > 0:
        st.warning(f"⚠ {pending_count} action(s) awaiting your approval")

    mcp_client = MCPClient(mode=MCP_MODE)
    render_hitl(session=st.session_state, mcp_client=mcp_client)
```

---

## The 3-Scene Demo Flow

The demo video must show all three scenes flowing into each other. Here is the exact sequence with the button clicks:

**Scene 1 — Review Pulse (≈1 minute):**
1. Open Tab 2
2. Upload `data/reviews_sample.csv`
3. Click "Run Pipeline"
4. Show: top 3 themes, 3 user quotes, weekly pulse text, fee bullets
5. Note: "Start Call" button is now enabled

**Scene 2 — Voice Booking (≈2 minutes):**
1. Click "Start Call" in Tab 2
2. Agent plays greeting — points at camera/screen to show the theme mention: *"I see many users are asking about Nominee updates this week..."*
3. Type: "I want to book a call about nominee changes"
4. Navigate through TOPIC → TIMEPREF → OFFERSLOTS → CONFIRM → BOOKED
5. Show booking code on screen: `NL-A742`
6. Switch to sidebar — show pending MCP count increased

**Scene 3 — FAQ + Approval (≈2 minutes):**
1. Switch to Tab 1
2. Ask: "What is the exit load for SBI ELSS and how does the expense ratio work?"
3. Show: 6-bullet answer with sbimf.com + amfiindia.com source citations
4. Switch to Tab 3
5. Expand "calendar_hold" action — show payload with booking code
6. Click Approve → show green ✓ badge with reference ID
7. Expand "notes_append" — show connected view (booking code + M2 pulse context)
8. Click Approve
9. Expand "email_draft" — scroll through email body showing "Dear Advisor," + pulse excerpt + fee bullets
10. Click Approve
11. Expand "sheet_entry" — show booking_code, topic, date, status fields
12. Click Approve

---

## Prerequisites

- All phases 1–8 complete
- `streamlit run app.py` starts with zero import errors
- `data/chroma/` populated (Phase 2)
- `data/reviews_sample.csv` exists
- `data/mock_calendar.json` exists

---

## Credentials Required

None new. Phase 9 calls `load_env()` from `config.py` which loads all credentials at startup. Everything else is imported from previous phases.

---

## Tools & Libraries

| Package | Version | Purpose | Notes |
|---|---|---|---|
| `streamlit` | >=1.40.0 | `st.tabs()`, `st.sidebar`, `st.chat_input()`, `st.file_uploader()`, `st.audio()`, `st.expander()` | Already in `requirements.txt` |
| `json` | stdlib | Load/save `data/mcp_state.json` | No install |
| `pathlib` | stdlib | Check mcp_state.json, corpus paths | No install |

---

## Step-by-Step Build Order

**1. `app.py`** — write the full application:
- Bootstrap section (load_env, session_init, mcp_state reload)
- Sidebar (corpus status, pulse status, pending count)
- Tab 1 (FAQ chat history + input)
- Tab 2 (file uploader + pipeline + Phase 6 voice UI)
- Tab 3 (HITL panel)

**2. `phase9_dashboard/architecture/architecture.md`** — this file

**3. `README.md`** — write the setup guide:
```markdown
## Setup

1. pip install -r requirements.txt
2. python -m spacy download en_core_web_sm
3. cp .env.example .env  # fill in ANTHROPIC_API_KEY and OPENAI_API_KEY
4. python scripts/ingest_corpus.py
5. streamlit run app.py
```

---

## Inputs

| Input | Source |
|---|---|
| `data/reviews_sample.csv` | Pre-existing in repo |
| `data/mock_calendar.json` | Pre-existing in repo |
| `data/chroma/` | Built by Phase 2 `ingest_corpus.py` |
| `data/mcp_state.json` | Auto-generated on first approval action |
| All pillar modules | Built in Phases 1–8 |

---

## Outputs & Downstream Dependencies

| Output | Purpose |
|---|---|
| Running `streamlit run app.py` | The final deliverable — the full demo |
| `data/mcp_state.json` | Session recovery on page reload |
| `README.md` | Required submission deliverable |
| `EVALS_REPORT.md` | Generated by Phase 8 eval run — required submission deliverable |

---

## Error Cases

**Import error at startup (`from phaseN_xxx.module import ...` fails):**
Check: (1) the `__init__.py` files in each phase directory are present (Phase 1), (2) the module file exists and has no syntax errors. Run `python -c "from phase5_pillar_a_faq.faq_engine import query"` to isolate which import fails.

**Corpus not loaded (sidebar shows red):**
Run `python scripts/ingest_corpus.py` and wait for it to complete. The sidebar status will turn green on the next Streamlit rerun.

**Session state has stale data from a previous run:**
Click the Streamlit "Clear cache" button (⋮ menu in the top-right) or add a "Reset Session" button in the sidebar:
```python
if st.sidebar.button("🔄 Reset Session"):
    for key in SESSION_KEYS:
        del st.session_state[key]
    Path("data/mcp_state.json").unlink(missing_ok=True)
    st.rerun()
```

**Streamlit raises `DuplicateWidgetID` error:**
This happens if two calls to `st.text_input()` use the same `key=` string. In the voice agent loop, the key must include the turn counter: `key=f"voice_input_{st.session_state['voice_turn']}"`.

**`st.audio()` does not play in some browsers:**
Most modern browsers require user interaction before playing audio. `autoplay=True` works in Chrome but may be blocked in Safari. Provide a fallback text display so the conversation is still readable.

---

## Phase Gate

```bash
# Start the app — must open without errors
streamlit run app.py

# In the browser:
# 1. Upload data/reviews_sample.csv → click Run Pipeline
#    Expected: themes, quotes, pulse, fee bullets all display
# 2. Click Start Call → complete the booking flow
#    Expected: booking code shown (NL-XXXX format)
# 3. Switch to Tab 1 → ask: "What is the exit load for SBI ELSS and expense ratio?"
#    Expected: 6 bullets + sbimf.com or amfiindia.com source
# 4. Switch to Tab 3 → click Approve on calendar_hold
#    Expected: green ✓ badge + ref_id shown

# Run eval suite to generate the submission report
python phase8_eval_suite/evals/run_evals.py
# Expected: EVALS_REPORT.md generated, exit code 0
```
