"""Phase 1 eval — Foundation gate checklist (runs without external APIs)."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CHECKS = []

def check(label: str):
    def decorator(fn):
        CHECKS.append((label, fn))
        return fn
    return decorator


@check("ENV: ANTHROPIC_API_KEY set")
def _():
    return bool(os.getenv("ANTHROPIC_API_KEY"))

@check("ENV: OPENAI_API_KEY set")
def _():
    return bool(os.getenv("OPENAI_API_KEY"))

@check("ENV: MCP_MODE is mock or live")
def _():
    return os.getenv("MCP_MODE", "mock") in ("mock", "live")

@check("FILE: data/mock_calendar.json exists")
def _():
    return (ROOT / "data" / "mock_calendar.json").exists()

@check("FILE: mock_calendar.json has ≥4 slots")
def _():
    p = ROOT / "data" / "mock_calendar.json"
    if not p.exists():
        return False
    data = json.loads(p.read_text())
    slots = data.get("available_slots") or data.get("slots", [])
    return len(slots) >= 4

@check("FILE: data/reviews_sample.csv exists")
def _():
    return (ROOT / "data" / "reviews_sample.csv").exists()

@check("DIR: phase1_foundation/tests/ exists")
def _():
    return (ROOT / "phase1_foundation" / "tests").is_dir()

@check("DIR: data/ is writable")
def _():
    test_file = ROOT / "data" / ".write_test"
    try:
        test_file.write_text("ok")
        test_file.unlink()
        return True
    except Exception:
        return False


def run() -> dict:
    results = []
    for label, fn in CHECKS:
        try:
            passed = bool(fn())
        except Exception as e:
            passed = False
        results.append({"check": label, "passed": passed})
    return results


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    results = run()
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print(f"\n{'='*50}")
    print(f"Phase 1 Foundation Eval  —  {passed}/{total} checks passed")
    print(f"{'='*50}")
    for r in results:
        icon = "✓" if r["passed"] else "✗"
        print(f"  {icon}  {r['check']}")

    sys.exit(0 if passed == total else 1)
