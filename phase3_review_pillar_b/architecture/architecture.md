# Phase 3 Architecture — Review Intelligence Pipeline

## What This Phase Does

Phase 3 is where the system reads the voice of the customer. A product manager uploads a CSV file of recent INDMoney app reviews, and the pipeline automatically transforms that raw, messy data into structured intelligence: the top themes users are complaining about, representative user quotes, a polished 250-word weekly pulse note, and a fee explanation tuned to what users care about most this week.

More importantly, this phase writes the `top_theme` and `weekly_pulse` into shared session state. Those two values flow forward into everything else — the voice agent reads `top_theme` to personalise its greeting, and the advisor email includes `weekly_pulse` as market context. If Phase 3 doesn't run, the voice agent uses a generic greeting and the email has no market context.

**The pipeline runs in 6 linear steps, each feeding the next:**

1. **PII Scrubbing** — Remove all personal information before any AI sees it
2. **Theme Clustering** — Group reviews into themes using Claude
3. **Quote Extraction** — Pick the best representative quote per theme
4. **Pulse Writing** — Write the ≤250-word weekly note with exactly 3 action ideas
5. **Fee Explaining** — Generate a fee context bullet list based on the top theme
6. **MCP Queue** — Queue 2 outbound actions (notes entry + email draft) for human approval

---

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
│  Zero-shot prompt: group reviews     │
│  into max 5 themes, rank top 3       │
│                                      │
│  Expected JSON response:             │
│  {themes: [{label, count, ids}],     │
│   top_3: [str, str, str]}            │
│                                      │
│  Defensive parse: extract {...}      │
│  substring; fallback on failure      │
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
│    pick review with highest rating   │
│    re-run PII scrubber on quote      │
│  Output: 3 PII-free quotes           │
│  [{theme, quote, rating}]            │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  STEP 4: Pulse Writer (LLM)          │
│  model: claude-sonnet-4-6            │
│                                      │
│  Constraints in prompt:              │
│    ≤250 words total                  │
│    exactly 3 numbered action ideas   │
│                                      │
│  Retry loop (max 3 attempts):        │
│    check word_count ≤ 250            │
│    check action_count == 3           │
│    (regex: r"^\d+\." on each line)   │
│                                      │
│  On 3rd failure:                     │
│    hard-truncate to 250 words        │
│    assert action lines exist         │
│                                      │
│  → session["weekly_pulse"] = pulse   │
│  → session["pulse_generated"] = True │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  STEP 5: Fee Explainer (LLM + RAG)   │
│  Map top_theme → fee scenario        │
│  Query fee_corpus (top 4 chunks)     │
│  Claude: generate ≤6 fee bullets     │
│  → session["fee_bullets"]            │
│  → session["fee_sources"]            │
└────────────┬─────────────────────────┘
             │
             ▼
┌──────────────────────────────────────┐
│  STEP 6: MCP Queue Enqueue           │
│  enqueue_action() x2:                │
│    {type:"notes_append", status:"pending", ...}
│    {type:"email_draft",  status:"pending", ...}
│  → session["mcp_queue"] (+2 items)   │
│  These show up in Tab 3 for approval │
└──────────────────────────────────────┘
```

---

## Key Interfaces

```python
# pillar_b/pii_scrubber.py
def scrub(text: str) -> tuple[str, int]:
    """
    Runs regex + spaCy NER passes.
    Returns (clean_text, redaction_count).
    redaction_count is the total replacements made (for audit log).
    """

# pillar_b/pipeline_orchestrator.py  (was review_pipeline.py in early design)
def run_pipeline(csv_path: str, session: dict) -> dict:
    """
    Runs all 6 steps in order.
    Returns: {
        themes:      list[dict],    # [{label, count, review_ids}]
        top_3:       list[str],     # theme labels
        quotes:      list[dict],    # [{theme, quote, rating}]
        pulse:       str,           # ≤250 words
        word_count:  int,
        fee_bullets: list[str],
        fee_sources: list[str],
    }
    Side-effects: writes 7 keys to session, appends 2 items to mcp_queue
    """
```

---

## Fee Scenario Mapping

The fee explainer determines which fee topic to explain based on the top theme. This mapping is applied in `fee_explainer.py`:

```python
FEE_SCENARIO_MAP = {
    "Fee Transparency":  "expense_ratio",
    "SIP Failures":      "expense_ratio",
    "Exit Load":         "exit_load",
    # Default for all other themes:
    "_default":          "exit_load",
}
```

If the top theme is "Nominee Updates" or "KYC Issues" (neither of which is in the map), the `_default` value applies and the fee explainer explains exit loads. This ensures the fee explainer always produces output regardless of the theme.

---

## Prerequisites

- Phase 1 complete: `config.py` and `session_init.py` working
- Phase 2 complete: `fee_corpus` is populated (fee_explainer queries it in Step 5)
- `ANTHROPIC_API_KEY` valid with available quota
- spaCy model downloaded: `python -m spacy download en_core_web_sm`
- `data/reviews_sample.csv` exists with columns: `review_id, date, rating, review_text, source`

---

## Credentials Required

| Env Var | Required? | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Theme clustering (Step 2), pulse writing (Step 4), fee explanation (Step 5) — all use `claude-sonnet-4-6` |
| `CHROMA_PERSIST_DIR` | Yes | Fee explainer reads from `fee_corpus` collection |

**No `OPENAI_API_KEY` needed in this phase.** The fee explainer queries the already-embedded `fee_corpus` using the existing embeddings from Phase 2. No new embeddings are generated here.

---

## Tools & Libraries

| Package | Version | Purpose | Notes |
|---|---|---|---|
| `pandas` | >=2.2.0 | `pd.read_csv(csv_path)` — load and validate reviews CSV | Already in `requirements.txt` |
| `spacy` | >=3.7.0 | NER for detecting PERSON entities; `nlp = spacy.load("en_core_web_sm")` | Run `python -m spacy download en_core_web_sm` after install |
| `anthropic` | >=0.40.0 | `anthropic.Anthropic().messages.create(model="claude-sonnet-4-6", ...)` | Already in `requirements.txt` |
| `re` | stdlib | Regex PII patterns (phone, email, PAN); pulse action-line counting | No install |
| `json` | stdlib | Parse LLM's JSON response in theme clusterer | No install |
| `chromadb` | >=0.5.0 | Fee explainer queries `fee_corpus` collection | Already in `requirements.txt` |

### spaCy Model Note

`en_core_web_sm` is a ~12MB NLP model downloaded separately:
```bash
python -m spacy download en_core_web_sm
```
If it is not installed when `pii_scrubber.py` is first called, catch the `OSError` and fall back to regex-only mode with a warning:
```
WARNING: spaCy en_core_web_sm not found. Running PII scrubber in regex-only mode (PERSON names may not be detected).
```
Regex-only mode is acceptable — it catches the structured PII types (phones, emails, PANs). It misses person names, which is why the spaCy pass exists. The fallback must not crash the pipeline.

---

## Inputs

| Input | Format | Source |
|---|---|---|
| `data/reviews_sample.csv` | Columns: `review_id, date, rating (1–5), review_text, source` | Uploaded via Tab 2 file uploader or pre-existing in `data/` |
| `fee_corpus` ChromaDB collection | Vector embeddings from Phase 2 | `pillar_a/ingest.py::get_collection("fee_corpus")` |
| `session: dict` | Streamlit `st.session_state` | Passed in by `pipeline_orchestrator.py` |

---

## Step-by-Step Build Order

**1. `pillar_b/pii_scrubber.py`**
Function: `scrub(text: str) -> tuple[str, int]`
- Pass 1 — regex substitution on 3 patterns (phone, email, PAN). Count each match.
- Pass 2 — `nlp = spacy.load("en_core_web_sm")`; for each `ent` in `doc.ents` where `ent.label_ == "PERSON"`, replace with `[REDACTED]`
- Return `(clean_text, total_redaction_count)`
- The `total_redaction_count` is logged to console. It is never stored, never returned in the API response, never written to session.

**2. `pillar_b/theme_clusterer.py`**
Function: `cluster(reviews: list[dict]) -> dict`
- Build a single string of all `review_text` values (one per line)
- Send to `claude-sonnet-4-6` with zero-shot JSON prompt:
  ```
  You are a product analyst. Cluster these reviews into at most 5 themes.
  Return JSON: {"themes": [{"label": str, "count": int, "review_ids": [int]}], "top_3": [str, str, str]}
  ```
- **Defensive JSON parse:**
  ```python
  start = raw.find("{")
  end   = raw.rfind("}") + 1
  try:
      result = json.loads(raw[start:end])
  except (ValueError, IndexError):
      result = {"themes": [{"label": "General Feedback", "count": len(reviews), "review_ids": []}],
                "top_3":  ["General Feedback", "General Feedback", "General Feedback"]}
  ```
  The pipeline must not crash on malformed LLM output. The fallback single-theme response is acceptable — it means the pulse will have generic content, which is better than no pulse.

**3. `pillar_b/quote_extractor.py`**
Function: `extract(clean_reviews: list[dict], themes: list[dict], top_3: list[str]) -> list[dict]`
- For each of the 3 top theme labels, find its theme dict, get its `review_ids`
- Filter `clean_reviews` to those IDs; sort by `rating` descending; pick the first (highest rated)
- Run `pii_scrubber.scrub()` on the selected quote text one more time (double safety)
- Return `[{"theme": str, "quote": str, "rating": int}]`

**4. `pillar_b/pulse_writer.py`**
Function: `write(themes: list[dict], quotes: list[dict]) -> str`
- Build prompt with themes summary + 3 quotes
- Call `claude-sonnet-4-6` with pulse-writing prompt:
  ```
  Write a ≤250-word weekly product pulse for INDMoney.
  Include the top 3 themes, 3 user quotes, and exactly 3 numbered action ideas.
  Be concise and use plain business English. No investment advice.
  ```
- **Retry loop (max 3):**
  ```python
  for attempt in range(3):
      pulse = call_llm(prompt)
      word_count    = len(pulse.split())
      action_count  = len(re.findall(r"^\d+\.", pulse, re.MULTILINE))
      if word_count <= 250 and action_count == 3:
          return pulse
  # 3rd failure: hard truncate
  pulse = " ".join(pulse.split()[:250])
  # log: WARNING: Pulse truncated after 3 retries
  return pulse
  ```

**5. `pillar_b/fee_explainer.py`**
Function: `explain(scenario: str, session: dict) -> dict`
- Map `session["top_theme"]` → fee scenario using `FEE_SCENARIO_MAP`
- Call `get_collection("fee_corpus").query(...)` with top-4 chunks
- Send chunks + scenario to `claude-sonnet-4-6`:
  ```
  Explain {scenario} in ≤6 bullets using only the provided context.
  End with: Source: {url} | Last checked: {date}
  No investment advice.
  ```
- Return `{"bullets": list[str], "sources": list[str], "checked": str}`
- **If `fee_corpus` is empty:** return hardcoded placeholder:
  ```python
  {"bullets": ["Fee information is being updated."],
   "sources": ["https://www.amfiindia.com"],
   "checked": datetime.utcnow().date().isoformat()}
  ```

**6. `pillar_b/pipeline_orchestrator.py`**
Function: `run_pipeline(csv_path: str, session: dict) -> dict`
- Validate CSV has required columns; raise `ValueError` if not
- Call Steps 1–5 in order
- After Step 5, call `enqueue_action()` twice (imported from `pillar_c/mcp_client.py`):
  ```python
  from pillar_c.mcp_client import enqueue_action

  enqueue_action(session, type="notes_append",
      payload={"doc_title": "Advisor Pre-Bookings",
               "entry": {"date": today, "top_theme": session["top_theme"],
                         "pulse_summary": session["weekly_pulse"][:100]}},
      source="m2_pipeline")

  enqueue_action(session, type="email_draft",
      payload=build_email(session),   # from pillar_c/email_builder.py
      source="m2_pipeline")
  ```
- Write all session keys; return full result dict

---

## Outputs & Downstream Dependencies

Everything Phase 3 writes to `session` is consumed by later phases. If Phase 3 doesn't run, those later phases either fail or degrade silently.

| Session Key Written | Value | Consumed By | Risk if Missing |
|---|---|---|---|
| `session["weekly_pulse"]` | ≤250-word pulse text | Phase 7 email builder | Advisor email has no market context |
| `session["top_theme"]` | Top-1 theme label (e.g. "Nominee Updates") | Phase 4 GREET state | Voice agent uses generic greeting — fails UX eval |
| `session["top_3_themes"]` | List of 3 theme labels | Phase 9 Tab 2 display | UI shows nothing in themes section |
| `session["fee_bullets"]` | ≤6 fee bullet strings | Phase 7 email builder | Email has no fee explanation section |
| `session["fee_sources"]` | 2 official source URLs | Phase 7 email builder | Email has no source citations |
| `session["pulse_generated"]` | `True` | Phase 6 UI guard | "Start Call" button stays disabled |
| `session["mcp_queue"]` | +2 pending actions appended | Phase 7 HITL panel | Approval center shows 2 fewer items |

---

## Error Cases

**CSV missing required columns:**
```python
required = {"review_id", "date", "rating", "review_text", "source"}
missing = required - set(df.columns)
if missing:
    raise ValueError(f"CSV missing required columns: {missing}")
```
Raise before any processing starts. Never partially process a bad CSV.

**spaCy model not found:**
Catch `OSError` in `pii_scrubber.py`. Fall back to regex-only mode with a logged warning. Do not raise — the pipeline must continue.

**LLM returns non-JSON (theme clusterer):**
The defensive parse extracts the `{...}` substring. If that also fails, use the single-theme fallback. Log: `WARNING: Theme clusterer returned non-JSON. Using fallback single-theme response.`

**Pulse exceeds 250 words after 3 retries:**
Hard-truncate to first 250 words. Log: `WARNING: Pulse truncated to 250 words after 3 LLM retries.` The downstream system must still receive a pulse — a truncated one is better than `None`.

**`fee_corpus` empty:**
Fee explainer returns the hardcoded placeholder with AMFI URL. Log: `WARNING: fee_corpus is empty. Returning placeholder fee explanation.`

**`build_email` called before `booking_code` is set:**
This happens if `pipeline_orchestrator.py` tries to build the email draft before Phase 4 has run. `email_builder.py` should handle `None` booking_code gracefully — build a partial email with `"TBD"` for the booking code, since the voice call hasn't happened yet at this point.

---

## Phase Gate

```bash
pytest phase3_review_pipeline/tests/test_pipeline.py -v
# Expected: all tests pass
# Tests: scrub() removes PII, cluster() returns valid JSON fallback,
#        pulse word count ≤ 250, action count == 3, session keys written

python phase3_review_pipeline/evals/eval_pipeline.py
# Expected:
#   Pulse word count: X ≤ 250  ✓
#   Action ideas: 3            ✓
#   PII in output: 0 detected  ✓
```
