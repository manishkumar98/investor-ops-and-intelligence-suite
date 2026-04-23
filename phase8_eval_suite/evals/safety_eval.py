import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from phase5_pillar_a_faq.safety_filter import is_safe


def run_safety_eval() -> dict:
    tests = json.loads((Path(__file__).parent / "adversarial_tests.json").read_text())
    results = []
    for t in tests:
        safe, _ = is_safe(t["prompt"])
        passed = not safe  # passed = True means the prompt was correctly REFUSED
        results.append({
            "id":     t["id"],
            "prompt": t["prompt"],
            "passed": passed,
            "expected": t["expected"],
        })
    score = sum(r["passed"] for r in results)
    return {
        "results": results,
        "score":   score,
        "total":   len(tests),
        "passed":  score == len(tests),
    }


if __name__ == "__main__":
    result = run_safety_eval()
    for r in result["results"]:
        status = "PASS ✓" if r["passed"] else "FAIL ✗"
        print(f"  {r['id']}: {status} — {r['prompt'][:60]}")
    print(f"\nSafety Score: {result['score']}/{result['total']}")
