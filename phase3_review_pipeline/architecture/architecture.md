# Phase 3 Architecture — Review Intelligence Pipeline

## Pipeline Flow

```
reviews_sample.csv
        │
        ▼
┌──────────────────────────────────────┐
│  STEP 1: PII Scrubber                │
│  pii_scrubber.py                     │
│                                      │
│  Pass 1 — Regex:                     │
│    phone  \+?91[\s-]?\d{10}          │
│    email  [\w.+-]+@[\w-]+\.[\w.]+    │
│    PAN    [A-Z]{5}\d{4}[A-Z]         │
│    → replace all with [REDACTED]     │
│                                      │
│  Pass 2 — spaCy NER:                 │
│    nlp = en_core_web_sm              │
│    PERSON entities → [REDACTED]      │
│                                      │
│  Output: clean_reviews: list[dict]   │
│  Audit: {redaction_count: int}       │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  STEP 2: Theme Clusterer (LLM)       │
│  model: claude-sonnet-4-6            │
│                                      │
│  Prompt → JSON response:             │
│  {themes: [{label, count, ids}],     │
│   top_3: [str, str, str]}            │
│                                      │
│  → session["top_theme"] = top_3[0]  │
│  → session["top_3_themes"] = top_3  │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  STEP 3: Quote Extractor             │
│  For each of top_3 themes:           │
│    filter reviews by theme ids       │
│    pick highest-rated review         │
│    re-run PII scrubber on quote      │
│  Output: 3 PII-free quotes           │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  STEP 4: Pulse Writer (LLM)          │
│  model: claude-sonnet-4-6            │
│                                      │
│  Constraints enforced in prompt:     │
│    ≤250 words                        │
│    exactly 3 action ideas            │
│                                      │
│  Post-check:                         │
│    assert word_count ≤ 250           │
│    assert action_count == 3          │
│    retry once if fails               │
│                                      │
│  → session["weekly_pulse"] = pulse   │
│  → session["pulse_generated"] = True │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  STEP 5: Fee Explainer (LLM)         │
│  Uses fee_corpus retrieved chunks    │
│  ≤6 bullets, 2 URLs, last_checked   │
│  → session["fee_bullets"]            │
│  → session["fee_sources"]            │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  STEP 6: MCP Queue Enqueue           │
│  Appends to session["mcp_queue"]:    │
│   {type:"notes_append", status:"pending", payload:{...}}
│   {type:"email_draft",  status:"pending", payload:{...}}
└──────────────────────────────────────┘
```

## Key Interfaces

```python
# pillar_b/pii_scrubber.py
def scrub(text: str) -> tuple[str, int]:
    """Returns (clean_text, redaction_count)"""

# pillar_b/review_pipeline.py
def run_pipeline(csv_path: str, session: dict) -> dict:
    """
    Returns: {
        themes: list[dict],
        top_3: list[str],
        quotes: list[dict],
        pulse: str,
        word_count: int,
        fee_bullets: list[str],
        fee_sources: list[str],
    }
    Side-effects: writes to session state, appends to mcp_queue
    """
```
