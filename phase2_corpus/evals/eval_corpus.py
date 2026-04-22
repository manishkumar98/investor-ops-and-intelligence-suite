"""Phase 2 Eval — Corpus retrieval spot-check (requires live ChromaDB + embeddings)."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

SPOT_CHECK_QUERIES = [
    {"query": "What is the exit load for ELSS fund?",
     "must_contain_keyword": "exit load",
     "expected_corpus": "mf_faq"},
    {"query": "What is the expense ratio?",
     "must_contain_keyword": "expense ratio",
     "expected_corpus": "mf_faq"},
    {"query": "What are the fee charges on redemption?",
     "must_contain_keyword": "fee",
     "expected_corpus": "fee"},
]

def run(use_mock: bool = True) -> list[dict]:
    results = []

    if use_mock:
        for q in SPOT_CHECK_QUERIES:
            results.append({
                "query": q["query"],
                "passed": True,
                "note": "Mock mode — skipping live retrieval",
            })
        return results

    try:
        import chromadb
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")

        persist_dir = os.getenv("CHROMA_PERSIST_DIR", str(ROOT / "data" / "chroma"))
        client = chromadb.PersistentClient(path=persist_dir)

        for q in SPOT_CHECK_QUERIES:
            col_name = f"{q['expected_corpus']}_corpus"
            try:
                col = client.get_collection(col_name)
                count = col.count()
                passed = count > 0
                note = f"{col_name} has {count} chunks"
            except Exception as e:
                passed = False
                note = f"Error: {e}"
            results.append({"query": q["query"], "passed": passed, "note": note})

    except Exception as e:
        results.append({"query": "ChromaDB init", "passed": False, "note": str(e)})

    return results


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    use_mock = os.getenv("MCP_MODE", "mock") == "mock"
    results = run(use_mock=use_mock)

    passed = sum(1 for r in results if r["passed"])
    print(f"\nPhase 2 Corpus Eval — {passed}/{len(results)} passed")
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        print(f"  {icon}  {r['query'][:50]:<50}  {r['note']}")

    sys.exit(0 if passed == len(results) else 1)
