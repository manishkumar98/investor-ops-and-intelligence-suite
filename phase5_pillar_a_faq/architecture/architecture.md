# Phase 5 Architecture — Pillar A: Smart-Sync FAQ Engine

## What This Phase Does

Phase 5 is the FAQ engine — the part of the system a customer or support agent uses to ask questions about SBI Mutual Funds and get instant, accurate, sourced answers.

The key word is **Smart-Sync**: this is not a simple keyword search, and it's not a general-purpose chatbot. It is a Retrieval-Augmented Generation (RAG) system that searches only official documents (SBI MF, AMFI, SEBI), retrieves the most relevant passages, and gives them to Claude with strict instructions to answer *only* from those passages. The model cannot make things up, cannot give opinions, and cannot recommend funds. It is an information retrieval engine with an AI-powered formatter on top.

**The "compound question" superpower:** The system handles questions that span both fund facts *and* fees simultaneously. A question like *"What is the exit load for SBI ELSS and how does the expense ratio work?"* would require looking up two different document types. The query router detects this and queries both `mf_faq_corpus` (for ELSS facts) and `fee_corpus` (for fee rules) in parallel, merges the results, and produces a single 6-bullet answer with citations from both sources. This is the core value proposition of "Smart-Sync".

**The safety filter is the most important component in this phase.** It runs before any database lookup or AI call. Four categories of question are blocked immediately with zero AI involvement: investment advice requests, performance predictions, fund comparisons, and PII requests. This is an architectural compliance control — the system is literally incapable of answering those question types.

---

## Query Flow

```
user_query (str)
      │
      ▼
┌──────────────────────────────────────────┐
│  STEP 1: Safety Pre-Filter               │
│  safety_filter.py                        │
│                                          │
│  4 regex patterns (case-insensitive):    │
│  ┌──────────────────────────────────────┐│
│  │ (which|what|best|better|top).*       ││  → advice_refusal
│  │   (fund|scheme|invest)               ││
│  │ (return|profit|earn|gain).*          ││  → performance_refusal
│  │   (next|predict|will|expect)         ││
│  │ (compare|vs|versus).*(fund|scheme)   ││  → comparison_refusal
│  │ (email|phone|contact|CEO|CXO|address)││  → pii_refusal
│  └──────────────────────────────────────┘│
│                                          │
│  If blocked → SafeRefusalResponse        │
│    {refused=True, answer=str, source=URL}│
│  No LLM call, no DB lookup made          │
└───────────────┬──────────────────────────┘
                │ safe query passes through
                ▼
┌──────────────────────────────────────────┐
│  STEP 2: Query Router                    │
│  Default: ROUTER_MODE=keyword            │
│                                          │
│  FACT_KWS = [nav, aum, lock-in, exit     │
│    load, fund, elss, sip, sbi,           │
│    bluechip, smallcap]                   │
│  FEE_KWS  = [charge, expense ratio,      │
│    fee, stt, cost]                       │
│                                          │
│  has_fact AND has_fee  → "compound"      │
│  has_fee only          → "fee_only"      │
│  has_fact only         → "factual_only"  │
│  neither               → "factual_only"  │
└───────────────┬──────────────────────────┘
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
factual_only  fee_only  compound
     │          │          │
     ▼          ▼          ▼
mf_faq_corpus fee_corpus  both (parallel)
  Top-4         Top-4     Top-4 + Top-2
     │          │          │
     └──────────┴──────────┘
                │ merge + dedupe by chunk_id
                ▼
┌──────────────────────────────────────────┐
│  STEP 3: Distance Filter                 │
│  discard any chunk with distance > 0.75  │
│  if ALL chunks discarded → no-context    │
│  response (never hallucinate)            │
└───────────────┬──────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────┐
│  STEP 4: LLM Fusion (claude-sonnet-4-6)  │
│                                          │
│  System prompt enforces:                 │
│  - compound → exactly 6 bullets          │
│  - simple   → ≤3 sentences               │
│  - source must come from context only    │
│  - never infer returns                   │
│  - if no context → "not in knowledge     │
│    base" response                        │
│                                          │
│  Output: FaqResponse                     │
│  {bullets, prose, sources,               │
│   last_updated, refused}                 │
└───────────────┬──────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────┐
│  STEP 5: Session Write + Return          │
│  Append Q&A to session["chat_history"]   │
│  Return FaqResponse to Tab 1 for display │
└──────────────────────────────────────────┘
```

---

## Key Interfaces

```python
# pillar_a/safety_filter.py
def is_safe(query: str) -> tuple[bool, str | None]:
    """
    Returns (True, None) if query is allowed.
    Returns (False, refusal_message) if query matches a blocked pattern.
    Called first — before any other step.
    """

# pillar_a/query_router.py
def route(query: str) -> str:
    """
    Returns: "factual_only" | "fee_only" | "compound"
    Reads ROUTER_MODE from config:
      "keyword" (default) — no LLM call
      "llm"               — 1-shot claude-sonnet-4-6 classifier
    """

# pillar_a/retriever.py
def retrieve(query: str, query_type: str) -> list[dict]:
    """
    Embeds query with same model used during ingest.
    Queries collection(s) based on query_type.
    Applies distance filter (> 0.75 discarded).
    Returns: list of {text, source_url, corpus, distance}
    """

# pillar_a/llm_fusion.py
def fuse(query: str, chunks: list[dict], query_type: str) -> FaqResponse:
    """
    Builds context from chunks, calls claude-sonnet-4-6 with system prompt.
    Returns structured FaqResponse.
    """

# pillar_a/faq_engine.py
def query(user_input: str, session: dict) -> FaqResponse:
    """
    Full pipeline: safety_filter → route → retrieve → fuse → write history.
    This is the function called by app.py Tab 1.
    Also called by Phase 8 RAG eval.
    """

class FaqResponse:
    bullets:      list[str] | None   # for compound questions
    prose:        str | None          # for simple factual questions
    sources:      list[str]           # official URL(s)
    last_updated: str                 # date string from source metadata
    refused:      bool                # True if safety filter blocked
    refusal_msg:  str | None          # the refusal text if refused=True
```

---

## Safety Filter — The Four Locked Patterns

These 4 regex patterns are the compliance backbone of the entire FAQ system. They run before any other step. A match on any one of them returns a refusal immediately — the LLM is never called, the database is never queried.

```python
BLOCK_PATTERNS = [
    (r"(which|what|best|better|top).*(fund|scheme|invest)", "advice_refusal"),
    (r"(return|profit|earn|gain).*(next|predict|will|expect)", "performance_refusal"),
    (r"(compare|vs|versus).*(fund|scheme)", "comparison_refusal"),
    (r"(email|phone|contact|CEO|CXO|address)", "pii_refusal"),
]
```

**What each pattern blocks:**
- `advice_refusal` — questions like "which fund is best for me?", "what should I invest in?"
- `performance_refusal` — questions like "will this fund give 20% returns?", "predict next year's NAV"
- `comparison_refusal` — questions like "compare SBI ELSS vs Bluechip", "ELSS vs PPF — which is better?"
- `pii_refusal` — questions like "give me the CEO's email", "what is the fund manager's phone number?"

The refusal message always includes: *"I can only answer factual questions about mutual funds. For personalized advice, please consult a SEBI-registered advisor."* + a link to `https://www.sebi.gov.in/investors.html`

---

## Query Router — Keyword Mode

The keyword router determines which database(s) to search. It requires no API call, making it fast and free:

```python
FACT_KWS = ["nav", "aum", "lock-in", "exit load", "fund", "elss", "sip",
            "sbi", "bluechip", "smallcap"]
FEE_KWS  = ["charge", "expense ratio", "fee", "stt", "cost"]

has_fact = any(kw in query.lower() for kw in FACT_KWS)
has_fee  = any(kw in query.lower() for kw in FEE_KWS)

if has_fact and has_fee:  return "compound"      # search both collections
elif has_fee:             return "fee_only"       # search fee_corpus only
else:                     return "factual_only"   # search mf_faq_corpus only
```

Setting `ROUTER_MODE=llm` in `.env` switches to a 1-shot Claude classifier — useful for production when keyword matching may miss nuanced queries. Not required for the demo.

---

## Retrieval Logic

| Query Type | Collections Queried | n_results | Distance Threshold |
|---|---|---|---|
| `factual_only` | `mf_faq_corpus` only | 4 | 0.75 (discard above) |
| `fee_only` | `fee_corpus` only | 4 | 0.75 |
| `compound` | Both in parallel | 4 from faq + 2 from fee | 0.75 |

**Deduplication:** After merging results from both collections for compound queries, deduplicate by `chunk_id`. This prevents the same passage appearing twice if it was somehow indexed in both collections.

**No-context handling:** If after the distance filter, zero chunks remain, `fuse()` is called with an empty context list. The system prompt instructs Claude to respond: *"This information is not available in our knowledge base. Please check https://www.amfiindia.com"* — it never hallucinates an answer from empty context.

---

## LLM Fusion Prompt

```
System:
You are a Facts-Only Mutual Fund Assistant for INDMoney users.
Answer using ONLY the retrieved context provided below.

Rules:
- For compound questions (fund facts + fees): respond in exactly 6 numbered bullet points.
- For simple factual questions: respond in ≤3 sentences.
- Never infer returns, never recommend specific funds, never compare funds.
- If the context does not contain enough information to answer the question,
  respond: "This information is not available in our knowledge base.
  Please check https://www.amfiindia.com"
- End every answer with:
  "Source: {source_url}" and "Last updated from sources: {loaded_at_date}"

Context:
{combined_chunks_text}

Question: {user_query}
```

---

## Prerequisites

- Phase 1 complete: `config.py`, `session_init.py` working
- Phase 2 complete: both ChromaDB collections populated (`mf_faq_corpus` ≥30 chunks, `fee_corpus` ≥8 chunks)
- `ANTHROPIC_API_KEY` valid (LLM fusion + optional LLM router)
- `OPENAI_API_KEY` valid (query embedding — must use same model as ingest)

---

## Credentials Required

| Env Var | Required? | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | `claude-sonnet-4-6` for LLM fusion (Step 4); also for LLM query router if `ROUTER_MODE=llm` |
| `OPENAI_API_KEY` | Yes | Embed the user query: `openai.embeddings.create(model="text-embedding-3-small")` — must match ingest model |
| `CHROMA_PERSIST_DIR` | Yes | Access the persisted ChromaDB collections from Phase 2 |
| `ROUTER_MODE` | No | `keyword` (default) or `llm` |

---

## Tools & Libraries

| Package | Version | Purpose | Notes |
|---|---|---|---|
| `anthropic` | >=0.40.0 | LLM fusion — `claude-sonnet-4-6` generates the structured answer | Already in `requirements.txt` |
| `openai` | >=1.50.0 | `openai.embeddings.create(model="text-embedding-3-small")` — embed user query with same model as ingest | Already in `requirements.txt` |
| `chromadb` | >=0.5.0 | `collection.query(query_embeddings=[...], n_results=4)` | Already in `requirements.txt` |
| `re` | stdlib | Safety filter regex matching | No install |
| `datetime` | stdlib | `last_updated` field in `FaqResponse` | No install |

---

## Inputs

| Input | Source |
|---|---|
| `user_input: str` | User's typed question from Tab 1 chat input |
| `session: dict` | Streamlit `st.session_state` — FAQ appends to `chat_history` |
| `mf_faq_corpus` collection | ChromaDB on disk (Phase 2) |
| `fee_corpus` collection | ChromaDB on disk (Phase 2) |

---

## Step-by-Step Build Order

**1. `pillar_a/safety_filter.py`**
Function: `is_safe(query: str) -> tuple[bool, str | None]`
- Iterate `BLOCK_PATTERNS` with `re.search(pattern, query, re.IGNORECASE)`
- On first match: return `(False, refusal_message_with_sebi_link)`
- No match: return `(True, None)`

**2. `pillar_a/query_router.py`**
Function: `route(query: str) -> str`
- Read `ROUTER_MODE` from `config.py`
- Keyword mode: implement as described above; no API calls
- LLM mode: 1-shot Claude call with a classification prompt; parse response to one of 3 valid strings

**3. `pillar_a/retriever.py`**
Function: `retrieve(query: str, query_type: str) -> list[dict]`
- Embed query: `openai.embeddings.create(model="text-embedding-3-small", input=[query])`
- Based on `query_type`, query one or both collections
- For `compound`: query both collections simultaneously (2 calls); merge results
- Apply distance filter: `[c for c in results if c["distance"] <= 0.75]`
- Deduplicate by `chunk_id`
- Return `[{text, source_url, corpus, distance}]`

**4. `pillar_a/llm_fusion.py`**
Function: `fuse(query: str, chunks: list[dict], query_type: str) -> FaqResponse`
- Build `context_text = "\n\n".join([c["text"] for c in chunks])`
- If `chunks` is empty: return `FaqResponse(refused=False, prose="This information is not available...", sources=[], last_updated=today)`
- Call `claude-sonnet-4-6` with the fusion system prompt
- Parse response into `FaqResponse` — detect bullet format vs prose based on numbered lines
- Extract source URLs from chunk metadata

**5. `pillar_a/faq_engine.py`**
Function: `query(user_input: str, session: dict) -> FaqResponse`
- Call `is_safe(user_input)` → if not safe, return `FaqResponse(refused=True, refusal_msg=...)`
- Call `route(user_input)` → `query_type`
- Call `retrieve(user_input, query_type)` → `chunks`
- Call `fuse(user_input, chunks, query_type)` → `response`
- Append `{"role": "user", "content": user_input, "response": response}` to `session["chat_history"]`
- Return `response`

---

## Outputs & Downstream Dependencies

| Output | Consumed By |
|---|---|
| `FaqResponse` object | Phase 9 `app.py` Tab 1 — renders bullets/prose/refusal box |
| `session["chat_history"]` | Phase 9 Tab 1 — displays conversation history |
| `faq_engine.query()` | Phase 8 RAG eval — calls this function with golden dataset questions |
| `safety_filter.is_safe()` | Phase 8 safety eval — calls this directly with adversarial prompts |

---

## Error Cases

**ChromaDB collection empty (Phase 2 not run):**
`retrieve()` returns `[]`. `fuse()` receives empty context. Returns: *"This information is not available in our knowledge base. Please check https://www.amfiindia.com"* — never hallucinates.

**OpenAI embedding fails (wrong key, quota exhausted):**
Catch the `openai.APIError`. Raise:
```
RuntimeError("Cannot embed query — check OPENAI_API_KEY and available quota.")
```
Do not silently return empty results — that would produce a misleading "not in knowledge base" response when the real problem is a missing API key.

**Anthropic API error during fusion:**
Catch `anthropic.APIError`. Return:
```python
FaqResponse(refused=True, refusal_msg="Service temporarily unavailable. Please try again.")
```

**All retrieved chunks have distance > 0.75:**
`retrieve()` returns `[]` after filtering. This is treated identically to "corpus empty" — return the "not in knowledge base" response. Never hallucinate.

**LLM returns answer without source citation:**
If the response text does not contain a line starting with "Source:", append the top chunk's `source_url` from the context metadata. The answer must always include a source.

---

## Phase Gate

```bash
pytest phase5_pillar_a_faq/tests/test_faq_engine.py -v
# Expected: all tests pass
# Tests: safety filter blocks all 4 pattern types,
#        router returns "compound" for fact+fee question,
#        retriever returns ≤6 chunks, distance filter works,
#        fuse returns FaqResponse with sources,
#        faq_engine.query() appends to chat_history

python phase5_pillar_a_faq/evals/eval_faq.py
# Expected:
#   Safety: 3/3 adversarial prompts refused   ✓
#   RAG: top result sources contain sbimf.com or amfiindia.com ✓
```
