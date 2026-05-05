import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import anthropic

from phase5_pillar_a_faq.faq_engine import query
from session_init import init_session_state

ALLOWED_DOMAINS = ["sbimf.com", "amfiindia.com", "sebi.gov.in", "indmoney.com", "groww.in"]

_judge_client = None


def _get_judge():
    global _judge_client
    if _judge_client is None:
        _judge_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    return _judge_client


def check_faithfulness(response) -> bool:
    if response.refused:
        return True  # refusals are always faithful
    if not response.sources:
        # No sources means retriever returned nothing (KB empty / no match).
        # The LLM will have replied with the NOT_IN_KB fallback — that is
        # technically faithful (no hallucinated URLs), so we pass it here.
        # The relevance check will catch it as not-relevant.
        prose = response.prose or ""
        if "not available in our knowledge base" in prose.lower() or "amfiindia.com" in prose:
            return True
        return False
    return all(
        any(domain in url for domain in ALLOWED_DOMAINS)
        for url in response.sources
    )


def check_relevance(question: str, response) -> dict:
    if response.refused:
        return {"relevant": False, "reason": "response was refused"}

    answer_text = "\n".join(response.bullets or [response.prose or ""])
    if not answer_text.strip():
        return {"relevant": False, "reason": "empty answer"}

    prompt = (
        f"Does this answer directly and specifically address the question?\n"
        f"Question: {question}\n"
        f"Answer: {answer_text}\n\n"
        f'Reply with JSON only, no markdown fences: {{"relevant": true, "reason": "one sentence"}}'
    )
    try:
        msg = _get_judge().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except Exception as exc:
        return {"relevant": None, "reason": f"LLM judge unavailable: {exc}"}


def _kb_preflight() -> list[str]:
    """Return warning strings for any empty KB collections."""
    warnings = []
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from phase2_corpus_pillar_a.ingest import get_collection
        for name in ("mf_faq_corpus", "fee_corpus"):
            try:
                col = get_collection(name)
                count = col.count()
                if count == 0:
                    warnings.append(f"[PREFLIGHT] '{name}' is empty — sync KB before running evals")
                else:
                    print(f"[PREFLIGHT] '{name}': {count} chunks ✓")
            except Exception as e:
                warnings.append(f"[PREFLIGHT] '{name}' unavailable: {e}")
    except ImportError as e:
        warnings.append(f"[PREFLIGHT] could not import ingest: {e}")
    return warnings


def run_rag_eval() -> dict:
    questions = json.loads((Path(__file__).parent / "golden_dataset.json").read_text())
    session: dict = {}
    init_session_state(session)

    for w in _kb_preflight():
        print(w)

    results = []
    for q in questions:
        response = query(q["question"], session)
        faithful = check_faithfulness(response)
        relevance_data = check_relevance(q["question"], response)
        relevant = relevance_data.get("relevant")
        results.append({
            "id":         q["id"],
            "question":   q["question"][:60],
            "faithful":   faithful,
            "relevant":   relevant,
            "reason":     relevance_data.get("reason", ""),
            "sources":    response.sources,
        })
        print(f"  {q['id']}: faithful={faithful} relevant={relevant}")

    faith_score = sum(1 for r in results if r["faithful"])
    rel_score   = sum(1 for r in results if r["relevant"] is True)
    return {
        "results":      results,
        "faithfulness": faith_score,
        "relevance":    rel_score,
        "total":        len(questions),
    }


if __name__ == "__main__":
    result = run_rag_eval()
    print(f"\nFaithfulness: {result['faithfulness']}/{result['total']}")
    print(f"Relevance:    {result['relevance']}/{result['total']}")
