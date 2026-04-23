import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import anthropic

from phase5_pillar_a_faq.faq_engine import query
from session_init import init_session_state

ALLOWED_DOMAINS = ["sbimf.com", "amfiindia.com", "sebi.gov.in"]

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
        f'Reply with JSON only: {{"relevant": true or false, "reason": "one sentence"}}'
    )
    try:
        msg = _get_judge().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(msg.content[0].text.strip())
    except Exception as exc:
        return {"relevant": None, "reason": f"LLM judge unavailable: {exc}"}


def run_rag_eval() -> dict:
    questions = json.loads((Path(__file__).parent / "golden_dataset.json").read_text())
    session: dict = {}
    init_session_state(session)

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
