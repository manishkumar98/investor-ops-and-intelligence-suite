# Product Requirements Document
## Investor Ops & Intelligence Suite
**Version:** 2.0 (As-Built)
**Date:** April 27, 2026
**Author:** Chief Product Officer
**Status:** Implemented — reflects actual built system

---

## 1. Executive Summary

The **Investor Ops & Intelligence Suite** is a unified AI-powered operations platform built for **INDMoney**. It consolidates three previously siloed AI capabilities — a Mutual Fund FAQ chatbot (M1), a Review Intelligence & Fee Explainer workflow (M2), and an AI Voice Appointment Scheduler (M3) — into a single, coherent product dashboard.

The platform closes the loop between *customer signals* (app reviews), *knowledge delivery* (FAQ + fee explainer), and *human escalation* (voice scheduling + advisor briefing), while enforcing strict regulatory compliance (no PII, no investment advice) and maintaining a Human-in-the-Loop approval gate on all outbound actions.

**Deadline:** May 3, 2026, 11:59 PM IST

---

## 2. Problem Statement

### Organizational Pain Points

| Problem | Current State | Impact |
|---|---|---|
| Repetitive MF FAQ queries flood support | No self-serve knowledge base tied to official sources | High support cost; compliance risk if agents give opinions |
| Product insights from reviews are not acted on | Reviews read manually; no structured weekly pulse | Slow iteration; unaddressed user themes persist for weeks |
| Advisor booking is phone-heavy and inefficient | No AI pre-qualification; PII collected verbally | Compliance risk; advisor prep is zero-context |
| Advisor emails lack customer sentiment context | Advisors go into calls cold | Lower conversion; misaligned conversation |

### Root Cause
The tools exist in isolation. Each milestone solves one problem but cannot communicate with the others, leaving a **gap between customer insight, knowledge delivery, and human escalation.**

---

## 3. Product Vision

> "Give every Fintech user instant, accurate, officially-sourced answers — and seamlessly connect them to a human advisor who is already briefed on what the market is feeling this week."

---

## 4. Target Users & Personas

### Persona 1: Retail Investor (Priya, 31)
- Mid-level professional investing in SIPs via INDMoney
- Questions like "What is the exit load for SBI ELSS?" or "Why was I charged an expense ratio this month?"
- Wants quick, trustworthy answers without calling support
- Will book a call if her question is complex

### Persona 2: Support/Product Manager (Rohit, 34)
- Reviews weekly app feedback; generates internal update emails
- Needs structured, actionable insight with no manual aggregation
- Reviews AI-generated MCP actions in the Approval Center before any action executes

### Persona 3: Financial Advisor (Ananya, 38)
- Receives pre-booked slots from the voice agent
- Needs context on the current top user theme (e.g., "Nominee updates trending this week") before the call
- Cannot rely on generic notes — needs structured, actionable pre-call briefs with booking code, market context, and fee context

---

## 5. Product Scope

### In Scope
- All three pillars described below (Pillar A, B, C)
- Evaluation Suite (RAG Eval, Safety Eval, UX Eval)
- Single-entry-point dashboard (Streamlit)
- MCP workflow with Human-in-the-Loop approval gates
- Booking code state persistence across M2 and M3
- Google Sheets, Google Calendar, and Gmail integration (live mode, toggled via `.env`)

### Out of Scope (v1.0)
- Real PAN/KYC verification
- Portfolio performance analytics or return computation
- Multi-AMC support beyond SBI Mutual Fund
- Real-time market data feeds

---

## 6. Feature Requirements

### Pillar A — Smart-Sync Knowledge Base (M1 + M2)

**Goal:** Unified search that answers compound questions spanning fund facts AND fee logic.

#### FA-1: Unified Search Interface
| ID | Requirement | Priority | Status |
|---|---|---|---|
| FA-1.1 | Single search box that simultaneously queries the M1 RAG corpus (SBI MF factsheets) and the M2 Fee Explainer knowledge base | P0 | ✅ Done |
| FA-1.2 | Response must include source citation(s) with URL(s) and "Last updated from sources: {date}" | P0 | ✅ Done |
| FA-1.3 | Complex compound answers must follow the 6-bullet structured format; simple factual queries ≤ 3 sentences | P0 | ✅ Done |
| FA-1.4 | System must refuse opinion-based or investment advice queries with a polite, facts-only message | P0 | ✅ Done |
| FA-1.5 | Safety filter blocks 4 categories: investment advice, performance prediction, fund comparison, PII requests | P0 | ✅ Done |
| FA-1.6 | UI displays welcome line and example questions on load | P1 | ✅ Done |
| FA-1.7 | No PII accepted or stored (PAN, Aadhaar, phone, email) | P0 | ✅ Done |

#### FA-2: Corpus Management
| ID | Requirement | Priority | Status |
|---|---|---|---|
| FA-2.1 | Corpus covers official SBI Mutual Fund pages (ELSS Tax Saver, Large Cap, Small Cap) + SEBI + AMFI | P0 | ✅ Done |
| FA-2.2 | Fee corpus covers exit load, expense ratio, STT — sourced from `amfiindia.com` and `sbimf.com` | P1 | ✅ Done |
| FA-2.3 | Allowed source domains: sbimf.com, amfiindia.com, sebi.gov.in, indmoney.com, camsonline.com, mfcentral.com | P0 | ✅ Done |

---

### Pillar B — Insight-Driven Agent Optimization (M2 + M3)

**Goal:** Voice agent is briefed by the current week's review pulse — users hear relevant theme mentions during greeting.

#### PB-1: Weekly Review Pulse Pipeline
| ID | Requirement | Priority | Status |
|---|---|---|---|
| PB-1.1 | Accept a CSV of app reviews (columns: review_id, review_text, rating; optional: date, source) | P0 | ✅ Done |
| PB-1.2 | Cluster reviews into max 5 themes; identify top 3 | P0 | ✅ Done — 2-pass LLM for large datasets |
| PB-1.3 | Extract 3 real user quotes (PII-masked with [REDACTED]) | P0 | ✅ Done — double-scrub pass |
| PB-1.4 | Generate ≤ 250-word weekly pulse note with retry loop (max 3); hard-truncate on failure | P0 | ✅ Done |
| PB-1.5 | Generate exactly 3 action ideas from themes | P0 | ✅ Done |
| PB-1.6 | Generate fee explanation (≤ 6 bullets) based on top theme, sourced from fee_corpus RAG | P0 | ✅ Done |
| PB-1.7 | Generate analytics: keyword cloud, sentiment distribution, rating distribution | P1 | ✅ Done |

#### PB-2: Theme-Aware Voice Agent
| ID | Requirement | Priority | Status |
|---|---|---|---|
| PB-2.1 | Voice agent reads the current top theme from M2 Weekly Pulse before initiating a call | P0 | ✅ Done |
| PB-2.2 | Greeting script proactively mentions the top theme | P0 | ✅ Done |
| PB-2.3 | Agent handles 5 intents: book_new, reschedule, cancel, what_to_prepare, check_availability | P0 | ✅ Done |
| PB-2.4 | Intent classification chain: Groq llama-3.3-70b → Claude Haiku → rule-based keyword fallback | P0 | ✅ Done |
| PB-2.5 | Disclaimer delivered at start of every call | P0 | ✅ Done |
| PB-2.6 | No PII collected on the call; secure link provided post-call to complete details | P0 | ✅ Done |
| PB-2.7 | 8-state FSM: GREET → INTENT → TOPIC → TIMEPREF → OFFERSLOTS → CONFIRM → BOOKED / WAITLIST | P0 | ✅ Done |
| PB-2.8 | 6 bookable topics: KYC/Onboarding, SIP/Mandates, Statements/Tax, Withdrawals, Account Changes, Fee Inquiry | P0 | ✅ Done |
| PB-2.9 | TTS: Sarvam AI bulbul:v2 (primary), gTTS fallback | P0 | ✅ Done |
| PB-2.10 | STT: Groq Whisper primary, Google Cloud Speech fallback; browser-side VAD | P0 | ✅ Done |

---

### Pillar C — Super-Agent MCP Workflow / HITL Approval Center

**Goal:** All outbound system actions require human approval before execution; advisor email includes M2 market context and M3 booking details.

#### PC-1: Post-Booking MCP Actions (M3 Voice Agent — triggered once per confirmed booking)
| ID | Requirement | Priority | Status |
|---|---|---|---|
| PC-1.1 | On call confirmation, generate Booking Code (format: NL-XXXX, 4 safe characters) | P0 | ✅ Done |
| PC-1.2 | MCP Calendar Hold: enqueue "Advisor Q&A — {Topic} — {Code}" calendar entry | P0 | ✅ Done |
| PC-1.3 | MCP Notes/Doc Entry: enqueue {date, topic, slot, booking_code, top_3_themes, pulse_snippet, fee_scenario} | P0 | ✅ Done |
| PC-1.4 | MCP Email Draft: enqueue advisor email with subject "Pre-Booking Alert: {topic} — {date} @ {slot}" | P0 | ✅ Done |
| PC-1.5 | MCP Google Sheet Entry: enqueue row {booking_code, topic_key, topic_label, slot_start_ist, date, status, call_id} | P0 | ✅ Done |
| PC-1.6 | Email body structure: greeting, meeting details block, market context (M2 pulse top themes + 120-word snippet), fee context, disclaimer, closing | P0 | ✅ Done |
| PC-1.7 | All 4 MCP actions are approval-gated; execution only via human Approve click | P0 | ✅ Done |
| PC-1.8 | HITL Approval Center: single panel listing all 4 pending actions with Approve/Reject per action | P0 | ✅ Done |
| PC-1.9 | Deduplication: enqueuing a new action of same type+source supersedes any existing pending action of that type | P0 | ✅ Done |
| PC-1.10 | "Clear Completed" button removes approved/rejected entries from queue; preserves pending actions | P1 | ✅ Done |

#### PC-2: State Persistence & Cross-Pillar Connection
| ID | Requirement | Priority | Status |
|---|---|---|---|
| PC-2.1 | Booking Code (M3) is visible in the Notes/Doc entry alongside M2 pulse themes and fee context — proves M2↔M3 connection | P0 | ✅ Done |
| PC-2.2 | Weekly Pulse from M2 persists in session state so M3 voice agent greeting and advisor email can reference it | P0 | ✅ Done |
| PC-2.3 | MCP queue persisted to `data/mcp_state.json`; reloaded on app restart | P0 | ✅ Done |

---

### Pillar D — Evaluation Suite

**Goal:** Prove the integrated system works via three mandatory evaluation types.

#### PD-1: Retrieval Accuracy Eval (RAG Eval)
| ID | Requirement | Priority | Status |
|---|---|---|---|
| PD-1.1 | Golden Dataset: 5 compound Q&A pairs (SBI ELSS, Large Cap, Small Cap, expense ratio, fees) | P0 | ✅ Done |
| PD-1.2 | Faithfulness: sources must be from allowed domains only | P0 | ✅ Done |
| PD-1.3 | Relevance: LLM-judged (claude-sonnet-4-6 as judge) — does answer address the question? | P0 | ✅ Done |
| PD-1.4 | Document scores in EVALS_REPORT.md | P0 | ✅ Done |

#### PD-2: Constraint Adherence Eval (Safety Eval)
| ID | Requirement | Priority | Status |
|---|---|---|---|
| PD-2.1 | 3 adversarial prompts: performance prediction, PII request, investment advice | P0 | ✅ Done |
| PD-2.2 | System refuses 100% of adversarial prompts (hard gate: 3/3 required) | P0 | ✅ Done |
| PD-2.3 | Document pass/fail results in EVALS_REPORT.md | P0 | ✅ Done |

#### PD-3: Tone & Structure Eval (UX Eval)
| ID | Requirement | Priority | Status |
|---|---|---|---|
| PD-3.1 | Weekly Pulse ≤ 250 words | P0 | ✅ Done |
| PD-3.2 | Weekly Pulse contains exactly 3 action ideas | P0 | ✅ Done |
| PD-3.3 | Voice Agent greeting mentions top theme from pulse | P0 | ✅ Done |
| PD-3.4 | PII scrubber produces [REDACTED] tokens for PII in reviews | P0 | ✅ Done |
| PD-3.5 | Booking code from M3 visible in notes_append MCP action payload | P0 | ✅ Done |
| PD-3.6 | Document all UX results in EVALS_REPORT.md | P0 | ✅ Done |

---

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Compliance** | Zero PII in any output, log, or stored state. Use [REDACTED] for all user names and contact data |
| **Safety** | System must never compute returns, compare fund performance, or give investment advice |
| **Transparency** | All FAQ answers must include source URL and "Last updated from sources: {date}" |
| **Single Entry Point** | One unified Streamlit app (`streamlit run app.py`) giving access to all three pillars |
| **Human-in-the-Loop** | All 4 MCP actions (calendar hold, notes, email draft, sheet entry) require explicit approval before execution |
| **State Persistence** | Booking Code from M3 must be traceable in Notes/Doc entry alongside M2 pulse context |
| **Response Length** | Factual answers ≤ 3 sentences; structured answers ≤ 6 bullets; Weekly Pulse ≤ 250 words |
| **Source Quality** | Only official public pages (AMC, SEBI, AMFI, INDMoney); no third-party blogs |
| **Deduplication** | Only one pending MCP action of each type per source at any time |

---

## 8. Success Metrics

| Metric | Target |
|---|---|
| RAG Faithfulness Score | ≥ 4/5 questions answered within source bounds |
| RAG Relevance Score | ≥ 4/5 questions directly address the scenario |
| Safety Eval Pass Rate | 3/3 adversarial prompts correctly refused |
| Weekly Pulse Word Count | ≤ 250 words on every test run |
| Weekly Pulse Action Ideas | Exactly 3 per pulse |
| Voice Agent Theme Mention | Top theme appears in agent greeting in 100% of test runs |
| PII Leak Rate | 0% — absolute zero |
| HITL Gate Adherence | 100% of MCP actions pass through approval gate |
| Booking Code Persistence | Booking Code visible in Notes/Doc 100% of the time |
| M2↔M3 Connection | Notes entry contains both booking_code (M3) and top_3_themes (M2) |

---

## 9. Deliverables Checklist

| Deliverable | Format | Status |
|---|---|---|
| GitHub Repository | Public link | ✅ Done |
| Evals Report | EVALS_REPORT.md Markdown table | ✅ Done |
| Source Manifest | SOURCE_MANIFEST.md | ✅ Done |
| Deployed App Link | Streamlit / HuggingFace | ⏳ Pending |
| Demo Video | 5-minute MP4 | ⏳ Pending |

### Demo Video Must Show:
1. Review CSV processed into a Weekly Pulse (M2 pipeline)
2. Voice call booked using that Pulse context — theme-aware greeting demonstrated (M3)
3. Smart-Sync FAQ answering a complex fee + fund fact question (Pillar A)
4. Approval Center showing all 4 MCP actions; Approve clicked (Pillar C)

---

## 10. Locked Implementation Decisions (Apr 22, 2026)

| # | Question | Decision |
|---|---|---|
| 1 | UI framework | **Streamlit** — `streamlit run app.py` |
| 2 | LLM | **Claude claude-sonnet-4-6** for all AI tasks |
| 3 | MCP mode | **Mock by default** (`MCP_MODE=mock`); live mode wired (Google Calendar + Sheets + Gmail SMTP). Toggle via `.env` |
| 4 | AMC scope | **SBI Mutual Fund** — SBI ELSS Tax Saver Fund, SBI Large Cap Fund, SBI Small Cap Fund + 5 more SBI schemes |
| 5 | Voice TTS | **Sarvam AI bulbul:v2** (primary); gTTS fallback |
| 6 | Voice STT | **Groq Whisper** (primary); Google Cloud Speech fallback; browser-side VAD |
| 7 | Intent classification | **Groq llama-3.3-70b** → Claude Haiku → keyword rules |
| 8 | Platform | **INDMoney** — all product copy, personas, and corpus scoped to INDMoney users |
| 9 | Embeddings | **OpenAI text-embedding-3-small** (1536-dim) if key set; else all-MiniLM-L6-v2 (384-dim). Cannot mix after first ingest |
| 10 | MCP actions per booking | **4 actions** — calendar_hold, notes_append, email_draft, sheet_entry |

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Google Calendar / Sheets API unavailable in demo | Medium | High | `MCP_MODE=mock` is default; identical interface; zero external dependencies in mock mode |
| Voice agent latency too high for demo | Medium | Medium | Pre-record call snippet; use local TTS if cloud latency spikes |
| RAG corpus retrieves wrong source for compound questions | Medium | High | Fund reranking in retriever (+3 text match, +2 URL match); golden dataset eval validates before demo |
| PII accidentally included in review CSV quotes | Low | Critical | Double-scrub: regex (phase1) + spaCy NER (phase2) before any AI sees review text |
| Weekly Pulse > 250 words | Low | Medium | Retry loop (max 3); hard truncation on 3rd failure; word count assertion in UX eval |
| ChromaDB embedding dimension mismatch | Low | High | Cannot mix embedding models; must delete data/chroma/ and re-ingest if model changes |

---

*This PRD (v2.0) reflects the system as actually built and deployed locally. Version 1.0 was the initial planning document dated Apr 22, 2026. Any deviations from v1.0 are documented in this version as implemented behavior.*
