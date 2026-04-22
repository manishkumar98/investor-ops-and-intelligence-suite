# Phase 5 Architecture — Pillar A: Smart-Sync FAQ Engine

## Query Flow

```
user_query (str)
      │
      ▼
┌──────────────────────────────────────────┐
│  STEP 1: Safety Pre-Filter               │
│  safety_filter.py                        │
│                                          │
│  Blocked patterns (regex, case-insensitive):
│  ┌──────────────────────────────────────┐│
│  │ should i (buy|sell|invest)           ││  → advice_refusal
│  │ which fund.*(better|best)            ││  → comparison_refusal
│  │ give.*\d+%.*return                   ││  → performance_refusal
│  │ (email|phone|contact).*ceo           ││  → pii_refusal
│  │ pan|aadhaar|account number           ││  → pii_refusal
│  └──────────────────────────────────────┘│
│                                          │
│  If blocked → SafeRefusalResponse        │
│    {refused=True, answer=str, source=URL}│
│  No LLM call made                        │
└───────────────┬──────────────────────────┘
                │ safe query
                ▼
┌──────────────────────────────────────────┐
│  STEP 2: Query Router (LLM 1-shot)       │
│                                          │
│  → "factual_only"  : fund facts only     │
│  → "fee_only"      : fee/charges only    │
│  → "compound"      : facts + fees        │
│  → "adversarial"   : backstop refusal    │
└───────────────┬──────────────────────────┘
                │
     ┌──────────┼──────────┐
     ▼          ▼          ▼
factual_only  fee_only  compound
     │          │          │
     ▼          ▼          ▼
mf_faq_corpus  fee_corpus  both (parallel)
Top-4          Top-4       Top-4 + Top-2
     │          │          │
     └──────────┴──────────┘
                │
                ▼
┌──────────────────────────────────────────┐
│  STEP 3: Distance Filter                 │
│  discard chunks with distance > 0.75     │
│  merge + dedupe by chunk_id              │
└───────────────┬──────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────┐
│  STEP 4: LLM Fusion (claude-sonnet-4-6)  │
│                                          │
│  System prompt rules:                    │
│  - compound → exactly 6 bullets          │
│  - simple   → ≤3 sentences               │
│  - source must come from context only    │
│  - never infer returns                   │
│  - if no context → "not in knowledge base"
│                                          │
│  Output: FaqResponse                     │
│  {bullets, prose, sources, last_updated, │
│   refused}                               │
└───────────────┬──────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────┐
│  STEP 5: Renderer + Session Write        │
│  Append to session["chat_history"]       │
│  Render: bullets / prose / refusal box  │
│  Always show source URLs + last_updated  │
└──────────────────────────────────────────┘
```

## Key Interfaces

```python
# pillar_a/safety_filter.py
def check(query: str) -> tuple[bool, str]:
    """Returns (is_safe, refusal_message_or_empty_string)"""

# pillar_a/rag_engine.py
def classify_query(query: str) -> str:
    """Returns: factual_only | fee_only | compound | adversarial"""

def retrieve(query: str, query_type: str) -> list[dict]:
    """Returns list of {text, source_url, distance} filtered by threshold"""

def answer(query: str, session: dict) -> FaqResponse:
    """Full pipeline: filter → classify → retrieve → fuse → return"""

class FaqResponse:
    bullets:      list[str] | None
    prose:        str | None
    sources:      list[str]
    last_updated: str
    refused:      bool
    refusal_msg:  str | None
```
